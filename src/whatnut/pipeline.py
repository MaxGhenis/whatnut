"""End-to-end analysis pipeline: model -> lifecycle -> results.

Usage:
    python -m whatnut.pipeline --generate   # Generate data/results.json
    python -m whatnut.pipeline              # Print summary
"""

import argparse
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_dist

from whatnut.artifact import RESULTS_SCHEMA_VERSION, write_results_artifact
from whatnut.config import (
    get_confounding_prior,
    get_mortality_curve,
    get_nut,
    get_quality_curve,
    load_constants,
)
from whatnut.decision import (
    DEFAULT_WILLINGNESS_TO_PAY,
    SINGLE_NUT_ADDITION_DECISION,
    summarize_cost_effectiveness,
    summarize_mutually_exclusive_nmb,
    validate_willingness_to_pay,
)
from whatnut.lifecycle import run_lifecycle, run_lifecycle_vectorized
from whatnut.model import sample_model
from whatnut.provenance import methodology_provenance
from whatnut.reference_case import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    UNDISCOUNTED_QALY_DISCOUNT_RATE,
    consumer_reference_case,
    validate_discount_rate,
)


@dataclass
class NutAnalysis:
    """Analysis results for a single nut."""

    nut_id: str
    name: str
    evidence: str

    # Life years (undiscounted)
    life_years_mean: float
    life_years_ci_lower: float
    life_years_ci_upper: float

    # Mortality-derived QALYs under the primary reference case.
    qaly_mean: float
    qaly_ci_lower: float
    qaly_ci_upper: float

    # Mortality-derived QALYs under the 0% health-discount sensitivity.
    qaly_undiscounted_mean: float
    qaly_undiscounted_ci_lower: float
    qaly_undiscounted_ci_upper: float

    # Signed expected contributions from Monte Carlo draws. These sum to the
    # unrounded expected primary-case QALY gain.
    expected_upside: float
    expected_downside: float

    # Probability of positive benefit
    p_positive: float
    p_negative: float

    # Cost-effectiveness
    annual_cost: float
    lifetime_cost_mean: float
    icer_expected: float | None
    icer_undiscounted_expected: float | None
    p_nmb_positive: float
    p_nmb_positive_undiscounted: float
    p_optimal: float
    expected_net_monetary_benefit: float
    expected_net_monetary_benefit_undiscounted: float
    nut_alternative_rank: int

    # Pathway-specific RRs (Monte Carlo expected RRs; not a true posterior
    # because the model has no likelihood — see docs/index.md Methods).
    rr_cvd: float
    rr_cancer: float
    rr_other: float

    # Pathway contributions
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float


@dataclass
class AnalysisResults:
    """Complete analysis output — every number the paper needs."""

    # Parameters
    seed: int
    n_samples: int
    start_age: int
    qaly_discount_rate: float
    cost_discount_rate: float
    undiscounted_qaly_discount_rate: float
    undiscounted_cost_discount_rate: float
    willingness_to_pay: float
    confounding_alpha: float
    confounding_beta: float
    confounding_mean: float
    confounding_ci_lower: float
    confounding_ci_upper: float

    # Baseline metrics
    baseline_life_years: float
    baseline_qalys: float
    average_quality_weight: float

    # E-value for HR=0.78 (Aune 2016 all-cause)
    e_value: float

    # Narrative constants loaded from data/constants.yaml so values in the
    # paper text never drift from a single source of truth.
    constants: dict
    reference_case: dict
    decision_context: dict
    decision_summary: dict
    model_interval: dict
    methodology_provenance: dict
    sensitivity_results: dict

    # Per-nut results
    nuts: dict[str, NutAnalysis]

    # Aggregate
    cvd_contribution_mean: float
    cancer_contribution_mean: float
    other_contribution_mean: float

    def to_dict(self) -> dict:
        """Serialize a complete schema-1.0.0 artifact dictionary."""
        if not self.sensitivity_results:
            self.sensitivity_results = _materialize_sensitivities(
                base_nuts=self.nuts,
                n_samples=self.n_samples,
                seed=self.seed,
                start_age=self.start_age,
                qaly_discount_rate=self.qaly_discount_rate,
                cost_discount_rate=self.cost_discount_rate,
                willingness_to_pay=self.willingness_to_pay,
                confounding_alpha=self.confounding_alpha,
                confounding_beta=self.confounding_beta,
            )
        d = {
            "schema_version": RESULTS_SCHEMA_VERSION,
            "seed": self.seed,
            "n_samples": self.n_samples,
            "start_age": self.start_age,
            "qaly_discount_rate": self.qaly_discount_rate,
            "cost_discount_rate": self.cost_discount_rate,
            "undiscounted_qaly_discount_rate": self.undiscounted_qaly_discount_rate,
            "undiscounted_cost_discount_rate": self.undiscounted_cost_discount_rate,
            "willingness_to_pay": self.willingness_to_pay,
            "confounding_alpha": self.confounding_alpha,
            "confounding_beta": self.confounding_beta,
            "confounding_mean": self.confounding_mean,
            "confounding_ci_lower": self.confounding_ci_lower,
            "confounding_ci_upper": self.confounding_ci_upper,
            "baseline_life_years": self.baseline_life_years,
            "baseline_qalys": self.baseline_qalys,
            "average_quality_weight": self.average_quality_weight,
            "e_value": self.e_value,
            "cvd_contribution_mean": self.cvd_contribution_mean,
            "cancer_contribution_mean": self.cancer_contribution_mean,
            "other_contribution_mean": self.other_contribution_mean,
            "constants": self.constants,
            "reference_case": self.reference_case,
            "decision_context": self.decision_context,
            "decision_summary": self.decision_summary,
            "model_interval": self.model_interval,
            "methodology_provenance": self.methodology_provenance,
            "sensitivity_results": self.sensitivity_results,
            "nuts": {},
        }
        for nid, na in self.nuts.items():
            d["nuts"][nid] = {
                "name": na.name,
                "evidence": na.evidence,
                "life_years_mean": na.life_years_mean,
                "life_years_ci_lower": na.life_years_ci_lower,
                "life_years_ci_upper": na.life_years_ci_upper,
                "qaly_mean": na.qaly_mean,
                "qaly_ci_lower": na.qaly_ci_lower,
                "qaly_ci_upper": na.qaly_ci_upper,
                "qaly_undiscounted_mean": na.qaly_undiscounted_mean,
                "qaly_undiscounted_ci_lower": na.qaly_undiscounted_ci_lower,
                "qaly_undiscounted_ci_upper": na.qaly_undiscounted_ci_upper,
                "expected_upside": na.expected_upside,
                "expected_downside": na.expected_downside,
                "p_positive": na.p_positive,
                "p_negative": na.p_negative,
                "annual_cost": na.annual_cost,
                "lifetime_cost_mean": na.lifetime_cost_mean,
                "icer_expected": na.icer_expected,
                "icer_undiscounted_expected": na.icer_undiscounted_expected,
                "p_nmb_positive": na.p_nmb_positive,
                "p_nmb_positive_undiscounted": na.p_nmb_positive_undiscounted,
                "p_optimal": na.p_optimal,
                "expected_net_monetary_benefit": na.expected_net_monetary_benefit,
                "expected_net_monetary_benefit_undiscounted": (
                    na.expected_net_monetary_benefit_undiscounted
                ),
                "nut_alternative_rank": na.nut_alternative_rank,
                "rr_cvd": na.rr_cvd,
                "rr_cancer": na.rr_cancer,
                "rr_other": na.rr_other,
                "cvd_contribution": na.cvd_contribution,
                "cancer_contribution": na.cancer_contribution,
                "other_contribution": na.other_contribution,
            }
        return d


def _validated_integer(
    value: int,
    *,
    label: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    """Validate integer-valued analysis inputs without silent coercion."""
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{label} must be an integer.")
    value = int(value)
    if value < minimum or (maximum is not None and value > maximum):
        range_text = f"at least {minimum}"
        if maximum is not None:
            range_text = f"between {minimum} and {maximum}"
        raise ValueError(f"{label} must be {range_text}.")
    return value


def _validated_positive_float(value: float, *, label: str) -> float:
    """Validate a finite, strictly positive scalar parameter."""
    try:
        value = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a positive finite value.") from error
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"{label} must be a positive finite value.")
    return value


def _finite_rounded(value: float, digits: int = 0) -> float | None:
    """Represent undefined or non-finite ratios as JSON null."""
    return round(value, digits) if np.isfinite(value) else None


def run_analysis(
    n_samples: int = 10_000,
    seed: int = 42,
    start_age: int = 40,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
    willingness_to_pay: float = DEFAULT_WILLINGNESS_TO_PAY,
    confounding_alpha: float | None = None,
    confounding_beta: float | None = None,
    include_sensitivities: bool = False,
) -> AnalysisResults:
    """Run full analysis: model sampling -> lifecycle -> summary.

    Args:
        n_samples: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.
        start_age: Age at start of nut consumption.
        qaly_discount_rate: Primary annual discount rate for life years and QALYs.
        cost_discount_rate: Annual discount rate for costs.
        willingness_to_pay: Illustrative USD value per mortality-derived QALY.
        confounding_alpha: Beta prior alpha for causal fraction
            (default: from priors.yaml).
        confounding_beta: Beta prior beta for causal fraction
            (default: from priors.yaml).

    Returns:
        AnalysisResults with every number needed for the paper.
    """
    n_samples = _validated_integer(n_samples, label="n_samples", minimum=1)
    seed = _validated_integer(
        seed,
        label="seed",
        minimum=0,
        maximum=np.iinfo(np.uint64).max,
    )
    start_age = _validated_integer(
        start_age,
        label="start_age",
        minimum=0,
        maximum=109,
    )
    if not isinstance(include_sensitivities, bool):
        raise ValueError("include_sensitivities must be a boolean.")
    qaly_discount_rate = validate_discount_rate(qaly_discount_rate, label="QALY")
    cost_discount_rate = validate_discount_rate(cost_discount_rate, label="cost")
    willingness_to_pay = validate_willingness_to_pay(willingness_to_pay)
    undiscounted_qaly_discount_rate = UNDISCOUNTED_QALY_DISCOUNT_RATE
    # The named sensitivity changes health discounting only. Costs retain the
    # caller's primary rate so custom runs remain a one-way sensitivity.
    undiscounted_cost_discount_rate = cost_discount_rate
    constants = dict(load_constants())

    # Use confounding prior from config when not overridden
    conf_prior = get_confounding_prior()
    if confounding_alpha is None:
        confounding_alpha = conf_prior.alpha
    if confounding_beta is None:
        confounding_beta = conf_prior.beta
    confounding_alpha = _validated_positive_float(
        confounding_alpha,
        label="confounding_alpha",
    )
    confounding_beta = _validated_positive_float(
        confounding_beta,
        label="confounding_beta",
    )

    # Derive 95% CI from the actual Beta(alpha, beta) parameters rather
    # than relying on the YAML hints; keeps the paper in sync with priors.
    confounding_ci_lower = float(
        beta_dist.ppf(0.025, confounding_alpha, confounding_beta)
    )
    confounding_ci_upper = float(
        beta_dist.ppf(0.975, confounding_alpha, confounding_beta)
    )

    # Compute baseline life years and QALYs from mortality and quality tables.
    # Survival is evaluated at the START of each age year: survival[0] = 1.0
    # (alive at start_age), survival[i] = P(alive at start of start_age+i).
    # Summing this approximates life expectancy. The sum (~39.3 at age 40)
    # runs ~0.5 years above the published CDC NVSR 72-12 ex(40)=38.83 because
    # intermediate ages use log-space anchor interpolation rather than the
    # Lx-based method CDC uses internally; documented in appendix.
    mortality = get_mortality_curve(start_age)
    quality = get_quality_curve(start_age)
    survival_raw = np.cumprod(1 - mortality)
    survival = np.insert(survival_raw[:-1], 0, 1.0)
    baseline_life_years = float(np.sum(survival))
    baseline_qalys = float(np.sum(survival * quality))
    average_quality_weight = (
        baseline_qalys / baseline_life_years if baseline_life_years > 0 else 0.0
    )
    # Scenario-dependent narrative values travel with the artifact. The YAML
    # supplies the canonical paper defaults, not immutable values for custom
    # start ages.
    constants["target_age"] = start_age
    constants["life_expectancy_approx"] = round(round(baseline_life_years, 2))

    # E-value for reference HR from Aune 2016 all-cause (HR=0.78)
    e_value = _e_value(0.78)

    # Step 1: Sample RRs from model
    samples = sample_model(
        n_samples=n_samples,
        seed=seed,
        confounding_alpha=confounding_alpha,
        confounding_beta=confounding_beta,
    )

    confounding_mean = confounding_alpha / (confounding_alpha + confounding_beta)
    nut_analyses: dict[str, NutAnalysis] = {}
    nmb_draws_by_nut: dict[str, np.ndarray] = {}

    # Step 2: Run lifecycle vectorized across all samples per nut
    for j, nut_id in enumerate(samples.nut_ids):
        nut_profile = get_nut(nut_id)

        vec = run_lifecycle_vectorized(
            rr_cvd=samples.rr["cvd"][:, j],
            rr_cancer=samples.rr["cancer"][:, j],
            rr_other=samples.rr["other"][:, j],
            annual_cost=nut_profile.annual_cost,
            start_age=start_age,
            qaly_discount_rate=qaly_discount_rate,
            cost_discount_rate=cost_discount_rate,
        )
        vec_undiscounted = run_lifecycle_vectorized(
            rr_cvd=samples.rr["cvd"][:, j],
            rr_cancer=samples.rr["cancer"][:, j],
            rr_other=samples.rr["other"][:, j],
            annual_cost=nut_profile.annual_cost,
            start_age=start_age,
            qaly_discount_rate=undiscounted_qaly_discount_rate,
            cost_discount_rate=undiscounted_cost_discount_rate,
        )
        qalys_primary = vec.qalys_gained_discounted
        qalys_undiscounted = vec_undiscounted.qalys_gained_discounted
        life_years = vec.life_years_gained
        primary_decision = summarize_cost_effectiveness(
            qalys_primary,
            vec.total_cost_discounted,
            willingness_to_pay,
        )
        undiscounted_decision = summarize_cost_effectiveness(
            qalys_undiscounted,
            vec_undiscounted.total_cost_discounted,
            willingness_to_pay,
        )
        nmb_draws_by_nut[nut_id] = (
            willingness_to_pay * qalys_primary - vec.total_cost_discounted
        )

        # Pathway contributions from the Monte Carlo mean RRs. Using the
        # expected RR (not a per-sample ratio) avoids ratio blow-up near the
        # null and matches what the paper reports as Monte Carlo expected RRs
        # (not "posterior" — this model has no likelihood).
        rr_cvd_mean = float(np.mean(samples.rr["cvd"][:, j]))
        rr_cancer_mean = float(np.mean(samples.rr["cancer"][:, j]))
        rr_other_mean = float(np.mean(samples.rr["other"][:, j]))

        mean_result = run_lifecycle(
            rr_cvd=rr_cvd_mean,
            rr_cancer=rr_cancer_mean,
            rr_other=rr_other_mean,
            annual_cost=nut_profile.annual_cost,
            start_age=start_age,
            qaly_discount_rate=qaly_discount_rate,
            cost_discount_rate=cost_discount_rate,
        )

        na = NutAnalysis(
            nut_id=nut_id,
            name=nut_id.capitalize(),
            evidence=nut_profile.evidence,
            # Means are shown at 2 decimals in the paper; CIs are stored at
            # 3 decimals so directional quantiles near zero (e.g., small
            # negative 2.5% tail) are not silently rounded to 0.00 and made
            # to look inconsistent with p_positive / p_negative.
            life_years_mean=round(float(np.mean(life_years)), 9),
            life_years_ci_lower=round(float(np.percentile(life_years, 2.5)), 9),
            life_years_ci_upper=round(float(np.percentile(life_years, 97.5)), 9),
            qaly_mean=round(primary_decision["expected_qaly"], 9),
            qaly_ci_lower=round(float(np.percentile(qalys_primary, 2.5)), 9),
            qaly_ci_upper=round(float(np.percentile(qalys_primary, 97.5)), 9),
            qaly_undiscounted_mean=round(undiscounted_decision["expected_qaly"], 9),
            qaly_undiscounted_ci_lower=round(
                float(np.percentile(qalys_undiscounted, 2.5)), 9
            ),
            qaly_undiscounted_ci_upper=round(
                float(np.percentile(qalys_undiscounted, 97.5)), 9
            ),
            expected_upside=round(primary_decision["expected_upside"], 9),
            expected_downside=round(primary_decision["expected_downside"], 9),
            p_positive=round(primary_decision["p_benefit"], 4),
            p_negative=round(primary_decision["p_harm"], 4),
            annual_cost=round(nut_profile.annual_cost, 2),
            lifetime_cost_mean=round(primary_decision["expected_cost"], 6),
            icer_expected=_finite_rounded(primary_decision["expected_cost_per_qaly"]),
            icer_undiscounted_expected=_finite_rounded(
                undiscounted_decision["expected_cost_per_qaly"]
            ),
            p_nmb_positive=round(primary_decision["p_nmb_positive"], 4),
            p_nmb_positive_undiscounted=round(
                undiscounted_decision["p_nmb_positive"], 4
            ),
            p_optimal=0.0,
            expected_net_monetary_benefit=round(
                primary_decision["expected_net_monetary_benefit"], 2
            ),
            expected_net_monetary_benefit_undiscounted=round(
                undiscounted_decision["expected_net_monetary_benefit"], 2
            ),
            nut_alternative_rank=0,
            rr_cvd=round(rr_cvd_mean, 6),
            rr_cancer=round(rr_cancer_mean, 6),
            rr_other=round(rr_other_mean, 6),
            cvd_contribution=round(mean_result.cvd_contribution, 6),
            cancer_contribution=round(mean_result.cancer_contribution, 6),
            other_contribution=round(mean_result.other_contribution, 6),
        )
        nut_analyses[nut_id] = na

    # The decision layer owns the paired all-option comparison, including a
    # zero-cost/zero-effect comparator.
    comparator_id = "no_modeled_nut_intervention"
    nut_option_ids = list(samples.nut_ids)
    all_option_decision = summarize_mutually_exclusive_nmb(
        {
            comparator_id: np.zeros(n_samples),
            **nmb_draws_by_nut,
        }
    )
    for nut_id in nut_option_ids:
        nut_analyses[nut_id].p_optimal = round(
            all_option_decision.probability_optimal[nut_id],
            4,
        )

    ranked_nut_ids = [
        option_id
        for option_id in all_option_decision.ranking
        if option_id != comparator_id
    ]
    for rank, nut_id in enumerate(ranked_nut_ids, start=1):
        nut_analyses[nut_id].nut_alternative_rank = rank

    best_nut_id = ranked_nut_ids[0]
    best_nut = nut_analyses[best_nut_id]
    recommended_option_ids = all_option_decision.recommended_option_ids
    option_labels = {
        comparator_id: "No modeled daily-nut intervention.",
        **{nut_id: nut.name for nut_id, nut in nut_analyses.items()},
    }
    recommended_labels = [
        option_labels[option_id] for option_id in recommended_option_ids
    ]
    recommended_option = (
        recommended_labels[0]
        if len(recommended_labels) == 1
        else "Tie: " + "; ".join(recommended_labels)
    )
    recommended_nut_id = (
        recommended_option_ids[0]
        if len(recommended_option_ids) == 1
        and recommended_option_ids[0] != comparator_id
        else None
    )
    decision_summary = {
        "criterion": "maximum_expected_net_monetary_benefit",
        "willingness_to_pay_usd_per_qaly": willingness_to_pay,
        "comparator_option": "No modeled daily-nut intervention.",
        "comparator_expected_net_monetary_benefit": round(
            all_option_decision.expected_nmb[comparator_id], 2
        ),
        "comparator_probability_optimal": round(
            all_option_decision.probability_optimal[comparator_id], 4
        ),
        "recommended_option_ids": list(recommended_option_ids),
        "recommended_option": recommended_option,
        "recommended_nut_id": recommended_nut_id,
        "best_nut_alternative_id": best_nut_id,
        "best_nut_alternative": best_nut.name,
        "best_nut_expected_net_monetary_benefit": (
            best_nut.expected_net_monetary_benefit
        ),
        "all_nut_interventions_have_negative_expected_nmb": all(
            all_option_decision.expected_nmb[nut_id] < 0 for nut_id in nut_analyses
        ),
        "nut_rank_scope": (
            "Conditional ordering among nut interventions by expected net "
            "monetary benefit; the comparator is evaluated separately."
        ),
        "all_option_evaluation": all_option_decision.to_dict(),
    }

    sensitivity_results = {}
    if include_sensitivities:
        sensitivity_results = _materialize_sensitivities(
            base_nuts=nut_analyses,
            n_samples=n_samples,
            seed=seed,
            start_age=start_age,
            qaly_discount_rate=qaly_discount_rate,
            cost_discount_rate=cost_discount_rate,
            willingness_to_pay=willingness_to_pay,
            confounding_alpha=confounding_alpha,
            confounding_beta=confounding_beta,
        )

    # Aggregate pathway contributions (mean across nuts)
    all_cvd = [na.cvd_contribution for na in nut_analyses.values()]
    all_cancer = [na.cancer_contribution for na in nut_analyses.values()]
    all_other = [na.other_contribution for na in nut_analyses.values()]

    return AnalysisResults(
        seed=seed,
        n_samples=n_samples,
        start_age=start_age,
        qaly_discount_rate=qaly_discount_rate,
        cost_discount_rate=cost_discount_rate,
        undiscounted_qaly_discount_rate=undiscounted_qaly_discount_rate,
        undiscounted_cost_discount_rate=undiscounted_cost_discount_rate,
        willingness_to_pay=willingness_to_pay,
        confounding_alpha=confounding_alpha,
        confounding_beta=confounding_beta,
        confounding_mean=confounding_mean,
        confounding_ci_lower=round(confounding_ci_lower, 4),
        confounding_ci_upper=round(confounding_ci_upper, 4),
        baseline_life_years=round(baseline_life_years, 2),
        baseline_qalys=round(baseline_qalys, 2),
        average_quality_weight=round(average_quality_weight, 3),
        e_value=round(e_value, 2),
        constants=constants,
        reference_case=consumer_reference_case(
            qaly_discount_rate,
            cost_discount_rate,
        ).to_dict(),
        decision_context=SINGLE_NUT_ADDITION_DECISION.to_dict(),
        decision_summary=decision_summary,
        model_interval={
            "kind": "monte_carlo_model_interval",
            "level": 0.95,
            "quantiles": [0.025, 0.975],
            "posterior": False,
        },
        methodology_provenance=methodology_provenance(),
        sensitivity_results=sensitivity_results,
        nuts=nut_analyses,
        cvd_contribution_mean=round(float(np.mean(all_cvd)), 2),
        cancer_contribution_mean=round(float(np.mean(all_cancer)), 2),
        other_contribution_mean=round(float(np.mean(all_other)), 2),
    )


def _materialize_sensitivities(
    *,
    base_nuts: dict[str, NutAnalysis],
    n_samples: int,
    seed: int,
    start_age: int,
    qaly_discount_rate: float,
    cost_discount_rate: float,
    willingness_to_pay: float,
    confounding_alpha: float,
    confounding_beta: float,
) -> dict[str, list[dict[str, object]]]:
    """Materialize the paper's confounding-prior sensitivity table."""
    scenarios = [
        (1.0, 9.0, "Very skeptical"),
        (confounding_alpha, confounding_beta, "Base case"),
        (1.5, 4.5, "Moderate"),
        (2.5, 5.0, "Optimistic"),
    ]
    rows: list[dict[str, object]] = []
    for alpha, beta, interpretation in scenarios:
        is_base = interpretation == "Base case"
        if is_base:
            scenario_nuts = base_nuts
        else:
            scenario_nuts = run_analysis(
                n_samples=n_samples,
                seed=seed,
                start_age=start_age,
                qaly_discount_rate=qaly_discount_rate,
                cost_discount_rate=cost_discount_rate,
                willingness_to_pay=willingness_to_pay,
                confounding_alpha=alpha,
                confounding_beta=beta,
                include_sensitivities=False,
            ).nuts
        rows.append(
            {
                "alpha": alpha,
                "beta": beta,
                "mean": alpha / (alpha + beta),
                "interpretation": interpretation,
                "is_base": is_base,
                "qaly_mean": {
                    "walnut": scenario_nuts["walnut"].qaly_mean,
                    "peanut": scenario_nuts["peanut"].qaly_mean,
                },
            }
        )
    return {"confounding_prior": rows}


def _e_value(hr: float) -> float:
    """VanderWeele (2017) E-value for a protective hazard ratio.

    Returns the minimum RR that an unmeasured confounder would need with
    both exposure and outcome to fully explain an observed HR.
    """
    rr = 1.0 / hr if hr < 1 else hr
    return rr + math.sqrt(rr * (rr - 1.0))


def generate_results_json(results: AnalysisResults, path: Path | None = None) -> Path:
    """Atomically write a complete, strict, versioned results artifact."""
    if path is None:
        path = Path(__file__).parent / "data" / "results.json"
    return write_results_artifact(path, results.to_dict())


def _canonical_generation_parameter_overrides(args: argparse.Namespace) -> list[str]:
    """Return CLI parameters that would make the canonical artifact noncanonical."""
    defaults = {
        "n_samples": 10_000,
        "seed": 42,
        "start_age": 40,
        "qaly_discount_rate": DEFAULT_QALY_DISCOUNT_RATE,
        "cost_discount_rate": DEFAULT_COST_DISCOUNT_RATE,
        "willingness_to_pay": DEFAULT_WILLINGNESS_TO_PAY,
    }
    return [
        f"--{name.replace('_', '-')}"
        for name, default in defaults.items()
        if getattr(args, name) != default
    ]


def main():
    parser = argparse.ArgumentParser(description="Whatnut analysis pipeline")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate data/results.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Write a generated artifact to this path. Required for a custom "
            "willingness-to-pay so the canonical paper artifact is not overwritten."
        ),
    )
    parser.add_argument("--n-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--start-age", type=int, default=40)
    parser.add_argument(
        "--qaly-discount-rate",
        type=float,
        default=DEFAULT_QALY_DISCOUNT_RATE,
        help="Primary annual discount rate for life years and QALYs.",
    )
    parser.add_argument(
        "--cost-discount-rate",
        type=float,
        default=DEFAULT_COST_DISCOUNT_RATE,
        help="Annual discount rate for costs.",
    )
    parser.add_argument(
        "--willingness-to-pay",
        type=float,
        default=DEFAULT_WILLINGNESS_TO_PAY,
        help="Illustrative USD value per mortality-derived QALY.",
    )
    args = parser.parse_args()

    if args.output is not None and not args.generate:
        parser.error("--output requires --generate")
    custom_generation_args = _canonical_generation_parameter_overrides(args)
    if args.generate and args.output is None and custom_generation_args:
        parser.error(
            "custom generation requires --output; the canonical paper artifact "
            "uses default parameters, but these were overridden: "
            + ", ".join(custom_generation_args)
        )

    print(f"Running analysis (n={args.n_samples}, seed={args.seed})...")
    results = run_analysis(
        n_samples=args.n_samples,
        seed=args.seed,
        start_age=args.start_age,
        qaly_discount_rate=args.qaly_discount_rate,
        cost_discount_rate=args.cost_discount_rate,
        willingness_to_pay=args.willingness_to_pay,
        include_sensitivities=args.generate,
    )

    if args.generate:
        path = generate_results_json(results, path=args.output)
        print(f"Results written to {path}")
    else:
        summary = results.decision_summary
        print(
            "\nDecision at "
            f"${results.willingness_to_pay:,.0f}/QALY: "
            f"{summary['recommended_option']} "
            f"(P(optimal)={summary['comparator_probability_optimal']:.1%} "
            "for the comparator)."
        )
        print(
            f"\n{'Nut rank':>8s} {'Nut':12s} {'QALY':>8s} "
            f"{'E[NMB]':>11s} {'P(opt)':>7s} {'Expected ICER':>14s}"
        )
        print("-" * 70)
        for nid in sorted(
            results.nuts,
            key=lambda key: results.nuts[key].nut_alternative_rank,
        ):
            na = results.nuts[nid]
            icer_text = (
                "undefined" if na.icer_expected is None else f"${na.icer_expected:,.0f}"
            )
            print(
                f"{na.nut_alternative_rank:8d} {nid:12s} {na.qaly_mean:8.3f} "
                f"${na.expected_net_monetary_benefit:>10,.0f} "
                f"{na.p_optimal:7.1%} "
                f"{icer_text:>14s}"
            )
        print(
            f"\nPathway contributions: CVD {results.cvd_contribution_mean:.0%}, "
            f"Cancer {results.cancer_contribution_mean:.0%}, "
            f"Other {results.other_contribution_mean:.0%}"
        )


if __name__ == "__main__":
    main()
