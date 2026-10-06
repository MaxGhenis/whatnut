"""Forward Monte Carlo model: numpy-based uncertainty propagation.

Replaces bayesian_model.py. No PyMC, no MCMC — this model samples from
priors directly because there is no likelihood function (no data to update
against). The paper calls this "Monte Carlo uncertainty propagation".

For each of N samples:
  1. Sample nutrient-pathway betas from Normal priors
  2. Compute expected log-RR: X @ beta (nutrient matrix x coefficients)
  3. Apply Jensen correction so E[RR] is HR-centered on exp(X @ mu)
     (mirrors optiqal's hr-centered lognormal parameterization)
  4. Sample causal_fraction ~ Beta(alpha, beta) and shrink the log-RR
  5. Convert to RR

The canonical model deliberately has no uncalibrated per-nut random effect or
hand-curated whole-nut multiplier. Those layers changed intervals and rankings
without an estimable likelihood and overlapped the nutrient evidence.

Returns arrays of RR samples per nut per pathway.
"""

import hashlib
from dataclasses import dataclass

import numpy as np
from scipy.special import betaincinv

from whatnut.config import (
    NUT_IDS,
    NUTRIENTS,
    PATHWAYS,
    get_confounding_prior,
    get_nutrient_matrix,
    get_pathway_priors,
)

RNG_ALGORITHM = "numpy-pcg64-named-streams-v1"


def _named_rng(seed: int, stream_name: str) -> np.random.Generator:
    """Return a deterministic RNG whose state depends only on its name and seed.

    Named streams prevent a change in one uncertainty family from advancing the
    random state used by another.  This is essential for one-way sensitivity
    analysis and makes adding a new draw family less likely to perturb every
    committed result.
    """
    digest = hashlib.blake2s(stream_name.encode(), digest_size=8).digest()
    stream_words = np.frombuffer(digest, dtype="<u4").astype(np.uint32).tolist()
    seed_words = [seed & 0xFFFFFFFF, (seed >> 32) & 0xFFFFFFFF]
    return np.random.default_rng(np.random.SeedSequence([*seed_words, *stream_words]))


def _causal_fraction_from_quantiles(
    quantiles: np.ndarray,
    alpha: float,
    beta: float,
) -> np.ndarray:
    """Transform shared uniforms into Beta draws for paired sensitivities."""
    epsilon = np.finfo(np.float64).eps
    bounded = np.clip(np.asarray(quantiles, dtype=np.float64), epsilon, 1 - epsilon)
    return np.asarray(betaincinv(alpha, beta, bounded), dtype=np.float64)


@dataclass
class ModelSamples:
    """Output of forward Monte Carlo sampling.

    Attributes:
        rr: dict mapping pathway -> (n_samples, n_nuts) array of relative risks
        causal_fraction: (n_samples,) array of sampled causal fractions
        causal_quantiles: shared uniforms underlying causal-fraction draws
        pre_confounding_log_rr: structural log-RR draws before causal shrinkage
        nut_ids: list of nut IDs (column order)
        n_samples: number of Monte Carlo samples
    """

    rr: dict[str, np.ndarray]
    causal_fraction: np.ndarray
    causal_quantiles: np.ndarray
    pre_confounding_log_rr: dict[str, np.ndarray]
    nut_ids: list[str]
    n_samples: int


def sample_model(
    n_samples: int = 10_000,
    seed: int = 42,
    nut_ids: list[str] | None = None,
    confounding_alpha: float | None = None,
    confounding_beta: float | None = None,
    hr_centered: bool = True,
    action_kind: str = "gross_addition",
) -> ModelSamples:
    """Run forward Monte Carlo sampling from priors.

    Args:
        n_samples: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.
        nut_ids: Nut IDs to include (default: all configured nuts).
        confounding_alpha: Override confounding prior alpha.
        confounding_beta: Override confounding prior beta.
        hr_centered: When True, apply a Jensen correction at the per-nut
            aggregate level so E[RR] equals exp(X @ mu). Mirrors optiqal's
            hr-centered lognormal parameterization. The numerical effect at
            current prior SDs is small (<0.3pp on RR) but the correction is
            the methodologically correct interpretation of the per-unit
            log_mean priors when they are sourced from meta-analysis point
            estimates.
        action_kind: Explicit modeled action. Evidence contrasts that do not
            apply to this action are structurally excluded rather than sampled
            as independent additive effects.

    Returns:
        ModelSamples with pathway-specific RR arrays.
    """
    if isinstance(n_samples, bool) or not isinstance(n_samples, (int, np.integer)):
        raise ValueError("n_samples must be an integer.")
    n_samples = int(n_samples)
    if n_samples < 1:
        raise ValueError("n_samples must be positive.")
    if isinstance(seed, bool) or not isinstance(seed, (int, np.integer)):
        raise ValueError("seed must be an integer.")
    seed = int(seed)
    if not 0 <= seed <= np.iinfo(np.uint64).max:
        raise ValueError("seed must be between 0 and 2**64 - 1.")
    if not isinstance(hr_centered, bool):
        raise ValueError("hr_centered must be a boolean.")
    if action_kind != "gross_addition":
        raise ValueError(
            "Only gross_addition is implemented; substitution requires a "
            "displaced-food nutrient contrast."
        )

    if nut_ids is None:
        nut_ids = list(NUT_IDS)
    else:
        nut_ids = list(nut_ids)
    if not nut_ids or len(set(nut_ids)) != len(nut_ids):
        raise ValueError("nut_ids must be nonempty and unique.")
    n_nutrients = len(NUTRIENTS)

    # Load priors
    conf_prior = get_confounding_prior()
    c_alpha = confounding_alpha if confounding_alpha is not None else conf_prior.alpha
    c_beta = confounding_beta if confounding_beta is not None else conf_prior.beta
    for label, value in (("confounding_alpha", c_alpha), ("confounding_beta", c_beta)):
        if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
            raise ValueError(f"{label} must be a positive finite value.")

    # Nutrient matrix: (n_nuts, n_nutrients)
    X = get_nutrient_matrix(nut_ids)

    # Draw shared causal quantiles on their own stream. Alternative Beta priors
    # transform these same ranks, while every structural draw remains identical.
    causal_quantiles = _named_rng(seed, "causal_fraction_quantiles").random(n_samples)
    causal_fraction = _causal_fraction_from_quantiles(
        causal_quantiles,
        float(c_alpha),
        float(c_beta),
    )

    rr_by_pathway: dict[str, np.ndarray] = {}
    pre_confounding_log_rr: dict[str, np.ndarray] = {}

    for pathway in PATHWAYS:
        priors = get_pathway_priors(pathway)

        # Prior means and sds: (n_nutrients,)
        mu = np.array(
            [
                priors[n].mean if action_kind in priors[n].applicable_actions else 0.0
                for n in NUTRIENTS
            ]
        )
        sigma = np.array(
            [
                priors[n].sd if action_kind in priors[n].applicable_actions else 0.0
                for n in NUTRIENTS
            ]
        )

        # Sample betas: (n_samples, n_nutrients)
        beta = _named_rng(seed, f"{pathway}:nutrient_coefficients").normal(
            mu[np.newaxis, :],
            sigma[np.newaxis, :],
            size=(n_samples, n_nutrients),
        )

        # Expected log-RR: (n_samples, n_nuts) = (n_samples, n_nutrients) @ (n_nutrients, n_nuts)
        expected_log_rr = beta @ X.T

        true_log_rr = expected_log_rr

        if hr_centered:
            # Jensen correction (pre-adjustment): shift log-RR so that the
            # pre-adjustment aggregate satisfies E[RR] == exp(X @ mu)
            # rather than exp(X @ mu + aggregate_variance / 2).
            # Per-nut nutrient variance (deterministic): sum(sigma_j^2 * x_j^2).
            nutrient_var = (sigma**2) @ (X.T**2)  # shape (n_nuts,)
            jensen_shift = 0.5 * nutrient_var[None, :]
            true_log_rr = true_log_rr - jensen_shift

        # Apply confounding adjustment
        pre_confounding_log_rr[pathway] = true_log_rr.copy()
        causal_log_rr = true_log_rr * causal_fraction[:, np.newaxis]

        # Convert to RR
        rr_by_pathway[pathway] = np.exp(causal_log_rr)

    return ModelSamples(
        rr=rr_by_pathway,
        causal_fraction=causal_fraction,
        causal_quantiles=causal_quantiles,
        pre_confounding_log_rr=pre_confounding_log_rr,
        nut_ids=nut_ids,
        n_samples=n_samples,
    )


def summarize_rr(samples: ModelSamples) -> dict[str, dict[str, dict]]:
    """Summarize RR distributions.

    Returns:
        Nested dict: pathway -> nut_id -> {mean, median, ci_lower, ci_upper}
    """
    summary = {}
    for pathway in PATHWAYS:
        rr = samples.rr[pathway]
        pathway_summary = {}
        for j, nut_id in enumerate(samples.nut_ids):
            vals = rr[:, j]
            pathway_summary[nut_id] = {
                "mean": float(np.mean(vals)),
                "median": float(np.median(vals)),
                "ci_lower": float(np.percentile(vals, 2.5)),
                "ci_upper": float(np.percentile(vals, 97.5)),
            }
        summary[pathway] = pathway_summary
    return summary


__all__ = [
    "ModelSamples",
    "RNG_ALGORITHM",
    "sample_model",
    "summarize_rr",
]
