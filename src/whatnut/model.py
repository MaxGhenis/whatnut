"""Forward Monte Carlo model: numpy-based uncertainty propagation.

Replaces bayesian_model.py. No PyMC, no MCMC — this model samples from
priors directly because there is no likelihood function (no data to update
against). The paper calls this "Monte Carlo uncertainty propagation".

For each of N samples:
  1. Sample nutrient-pathway betas from Normal priors
  2. Compute expected log-RR: X @ beta (nutrient matrix x coefficients)
  3. Add hierarchical deviation: expected + tau * z, z ~ N(0,1)
  4. Apply Jensen correction so E[RR] is HR-centered on exp(X @ mu)
     (mirrors optiqal's hr-centered lognormal parameterization)
  5. Apply tiered publication-bias shrinkage on the nut-specific adjustment
  6. Sample causal_fraction ~ Beta(alpha, beta) and shrink the log-RR
  7. Convert to RR

Returns arrays of RR samples per nut per pathway.
"""

from dataclasses import dataclass

import numpy as np

from whatnut.config import (
    NUTRIENTS,
    NUT_IDS,
    PATHWAYS,
    get_confounding_prior,
    get_nut,
    get_nutrient_matrix,
    get_pathway_priors,
    get_study_quality_shrinkage,
    get_tau_prior,
)


@dataclass
class ModelSamples:
    """Output of forward Monte Carlo sampling.

    Attributes:
        rr: dict mapping pathway -> (n_samples, n_nuts) array of relative risks
        causal_fraction: (n_samples,) array of sampled causal fractions
        nut_ids: list of nut IDs (column order)
        n_samples: number of Monte Carlo samples
    """

    rr: dict[str, np.ndarray]
    causal_fraction: np.ndarray
    nut_ids: list[str]
    n_samples: int


def sample_model(
    n_samples: int = 10_000,
    seed: int = 42,
    nut_ids: list[str] | None = None,
    confounding_alpha: float | None = None,
    confounding_beta: float | None = None,
    hr_centered: bool = True,
) -> ModelSamples:
    """Run forward Monte Carlo sampling from priors.

    Args:
        n_samples: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.
        nut_ids: Nut IDs to include (default: all 7).
        confounding_alpha: Override confounding prior alpha.
        confounding_beta: Override confounding prior beta.
        hr_centered: When True, apply a Jensen correction at the per-nut
            aggregate level so E[RR] equals exp(X @ mu). Mirrors optiqal's
            hr-centered lognormal parameterization. The numerical effect at
            current prior SDs is small (<0.3pp on RR) but the correction is
            the methodologically correct interpretation of the per-unit
            log_mean priors when they are sourced from meta-analysis point
            estimates.

    Returns:
        ModelSamples with pathway-specific RR arrays.
    """
    rng = np.random.default_rng(seed)

    if nut_ids is None:
        nut_ids = list(NUT_IDS)
    n_nuts = len(nut_ids)
    n_nutrients = len(NUTRIENTS)

    # Load priors
    conf_prior = get_confounding_prior()
    tau_prior = get_tau_prior()
    shrinkage = get_study_quality_shrinkage()
    c_alpha = confounding_alpha if confounding_alpha is not None else conf_prior.alpha
    c_beta = confounding_beta if confounding_beta is not None else conf_prior.beta

    # Nutrient matrix: (n_nuts, n_nutrients)
    X = get_nutrient_matrix(nut_ids)

    # Sample confounding fraction: (n_samples,)
    causal_fraction = rng.beta(c_alpha, c_beta, n_samples)

    rr_by_pathway: dict[str, np.ndarray] = {}

    for pathway in PATHWAYS:
        priors = get_pathway_priors(pathway)

        # Prior means and sds: (n_nutrients,)
        mu = np.array([priors[n].mean for n in NUTRIENTS])
        sigma = np.array([priors[n].sd for n in NUTRIENTS])

        # Sample betas: (n_samples, n_nutrients)
        beta = rng.normal(
            mu[np.newaxis, :],
            sigma[np.newaxis, :],
            size=(n_samples, n_nutrients),
        )

        # Expected log-RR: (n_samples, n_nuts) = (n_samples, n_nutrients) @ (n_nutrients, n_nuts)
        expected_log_rr = beta @ X.T

        # Hierarchical deviation: tau * z
        tau = np.abs(rng.normal(0, tau_prior.sigma, size=(n_samples, 1)))
        z = rng.standard_normal(size=(n_samples, n_nuts))
        true_log_rr = expected_log_rr + tau * z

        if hr_centered:
            # Jensen correction (pre-adjustment): shift log-RR so that the
            # pre-adjustment aggregate satisfies E[RR] == exp(X @ mu)
            # rather than exp(X @ mu + aggregate_variance / 2).
            # Per-nut nutrient variance (deterministic): sum(sigma_j^2 * x_j^2)
            nutrient_var = (sigma**2) @ (X.T**2)  # shape (n_nuts,)
            # Sample-specific tau variance: tau is HalfNormal, so tau^2
            tau_var = tau**2  # shape (n_samples, 1)
            jensen_shift = 0.5 * (nutrient_var[None, :] + tau_var)
            true_log_rr = true_log_rr - jensen_shift
            # Note: the subsequent a-multiplication and causal-fraction
            # shrinkage re-introduce a small Jensen gap of order
            # 0.5 * Var(a) * (X @ mu)^2 + 0.5 * (a_mean^2 - a_mean) * nutrient_var
            # that is not corrected here. At current prior SDs the residual
            # gap is under 0.15pp on RR (worst case walnut CVD); documented
            # in docs/appendix.md.

        # Apply nut-specific pathway adjustments (exponent on RR scale)
        # RR_adjusted = RR_true^a, i.e., log(RR_adjusted) = a * log(RR_true)
        #
        # Before sampling, shrink the adjustment mean toward the null
        # (a=1.0) by the evidence-tier publication-bias factor. This is the
        # tiered pub-bias layer imported from optiqal: strong evidence
        # retains 85% of the nut-specific edge, moderate 70%, limited 50%.
        # Following optiqal, only the central estimate is shrunk; adj.sd is
        # left alone so uncertainty reflects replication risk, not the
        # shrinkage itself.
        for k, nid in enumerate(nut_ids):
            nut = get_nut(nid)
            if pathway in nut.pathway_adjustments:
                adj = nut.pathway_adjustments[pathway]
                retention = shrinkage.retention(nut.evidence)
                shrunk_mean = 1.0 + (adj.mean - 1.0) * retention
                a = rng.normal(shrunk_mean, adj.sd, size=n_samples)
                true_log_rr[:, k] *= a

        # Apply confounding adjustment
        causal_log_rr = true_log_rr * causal_fraction[:, np.newaxis]

        # Convert to RR
        rr_by_pathway[pathway] = np.exp(causal_log_rr)

    return ModelSamples(
        rr=rr_by_pathway,
        causal_fraction=causal_fraction,
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
