"""End-to-end analysis pipeline: model -> lifecycle -> results.

Usage:
    python -m whatnut.pipeline --generate   # Generate data/results.json
    python -m whatnut.pipeline              # Print summary
"""

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.stats import beta as beta_dist

from whatnut.config import (
    NUT_IDS,
    PATHWAYS,
    get_confounding_prior,
    get_mortality_curve,
    get_nut,
    get_quality_curve,
    load_constants,
)
from whatnut.lifecycle import LifecycleResult, run_lifecycle, run_lifecycle_vectorized
from whatnut.model import ModelSamples, sample_model


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

    # QALYs (discounted)
    qaly_mean: float
    qaly_ci_lower: float
    qaly_ci_upper: float

    # QALYs (undiscounted)
    qaly_undiscounted_mean: float

    # Probability of positive benefit
    p_positive: float
    p_negative: float

    # Cost-effectiveness
    annual_cost: float
    icer_median: float
    icer_ci_lower: float
    icer_ci_upper: float | None  # None when the 2.5th-percentile QALY is ≤ 0

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

    # Per-nut results
    nuts: dict[str, NutAnalysis]

    # Aggregate
    cvd_contribution_mean: float
    cancer_contribution_mean: float
    other_contribution_mean: float

    def to_dict(self) -> dict:
        """Serialize to JSON-compatible dict."""
        d = {
            "seed": self.seed,
            "n_samples": self.n_samples,
            "start_age": self.start_age,
            "qaly_discount_rate": self.qaly_discount_rate,
            "cost_discount_rate": self.cost_discount_rate,
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
                "p_positive": na.p_positive,
                "p_negative": na.p_negative,
                "annual_cost": na.annual_cost,
                "icer_median": na.icer_median,
                "icer_ci_lower": na.icer_ci_lower,
                "icer_ci_upper": na.icer_ci_upper,
                "rr_cvd": na.rr_cvd,
                "rr_cancer": na.rr_cancer,
                "rr_other": na.rr_other,
                "cvd_contribution": na.cvd_contribution,
                "cancer_contribution": na.cancer_contribution,
                "other_contribution": na.other_contribution,
            }
        return d


def run_analysis(
    n_samples: int = 10_000,
    seed: int = 42,
    start_age: int = 40,
    qaly_discount_rate: float = 0.0,
    cost_discount_rate: float = 0.03,
    confounding_alpha: float | None = None,
    confounding_beta: float | None = None,
) -> AnalysisResults:
    """Run full analysis: model sampling -> lifecycle -> summary.

    Args:
        n_samples: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.
        start_age: Age at start of nut consumption.
        qaly_discount_rate: Annual discount rate for life years and QALYs.
        cost_discount_rate: Annual discount rate for costs.
        confounding_alpha: Beta prior alpha for causal fraction (default: from priors.yaml).
        confounding_beta: Beta prior beta for causal fraction (default: from priors.yaml).

    Returns:
        AnalysisResults with every number needed for the paper.
    """
    # Use confounding prior from config when not overridden
    conf_prior = get_confounding_prior()
    if confounding_alpha is None:
        confounding_alpha = conf_prior.alpha
    if confounding_beta is None:
        confounding_beta = conf_prior.beta

    # Derive 95% CI from the actual Beta(alpha, beta) parameters rather
    # than relying on the YAML hints; keeps the paper in sync with priors.
    confounding_ci_lower = float(beta_dist.ppf(0.025, confounding_alpha, confounding_beta))
    confounding_ci_upper = float(beta_dist.ppf(0.975, confounding_alpha, confounding_beta))

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
        qalys_disc = vec.qalys_gained_discounted
        qalys_undisc = vec.qalys_gained
        life_years = vec.life_years_gained
        icers = vec.cost_per_qaly

        # Summarize
        icer_finite = icers[np.isfinite(icers) & (icers > 0)]
        icer_upper = (
            float(np.percentile(icer_finite, 97.5))
            if len(icer_finite) > 0 and np.percentile(qalys_disc, 2.5) > 0
            else None
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
            life_years_mean=round(float(np.mean(life_years)), 2),
            life_years_ci_lower=round(float(np.percentile(life_years, 2.5)), 3),
            life_years_ci_upper=round(float(np.percentile(life_years, 97.5)), 3),
            qaly_mean=round(float(np.mean(qalys_disc)), 2),
            qaly_ci_lower=round(float(np.percentile(qalys_disc, 2.5)), 3),
            qaly_ci_upper=round(float(np.percentile(qalys_disc, 97.5)), 3),
            qaly_undiscounted_mean=round(float(np.mean(qalys_undisc)), 2),
            p_positive=round(float(np.mean(qalys_disc > 0)), 2),
            p_negative=round(float(np.mean(qalys_disc < 0)), 2),
            annual_cost=round(nut_profile.annual_cost, 2),
            icer_median=round(float(np.median(icer_finite)), 0) if len(icer_finite) > 0 else float("inf"),
            icer_ci_lower=round(float(np.percentile(icer_finite, 2.5)), 0) if len(icer_finite) > 0 else 0,
            icer_ci_upper=round(icer_upper, 0) if icer_upper is not None else None,
            rr_cvd=round(rr_cvd_mean, 4),
            rr_cancer=round(rr_cancer_mean, 4),
            rr_other=round(rr_other_mean, 4),
            cvd_contribution=round(mean_result.cvd_contribution, 2),
            cancer_contribution=round(mean_result.cancer_contribution, 2),
            other_contribution=round(mean_result.other_contribution, 2),
        )
        nut_analyses[nut_id] = na

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
        confounding_alpha=confounding_alpha,
        confounding_beta=confounding_beta,
        confounding_mean=confounding_mean,
        confounding_ci_lower=round(confounding_ci_lower, 4),
        confounding_ci_upper=round(confounding_ci_upper, 4),
        baseline_life_years=round(baseline_life_years, 2),
        baseline_qalys=round(baseline_qalys, 2),
        average_quality_weight=round(average_quality_weight, 3),
        e_value=round(e_value, 2),
        constants=load_constants(),
        nuts=nut_analyses,
        cvd_contribution_mean=round(float(np.mean(all_cvd)), 2),
        cancer_contribution_mean=round(float(np.mean(all_cancer)), 2),
        other_contribution_mean=round(float(np.mean(all_other)), 2),
    )


def _e_value(hr: float) -> float:
    """VanderWeele (2017) E-value for a protective hazard ratio.

    Returns the minimum RR that an unmeasured confounder would need with
    both exposure and outcome to fully explain an observed HR.
    """
    rr = 1.0 / hr if hr < 1 else hr
    return rr + math.sqrt(rr * (rr - 1.0))


def generate_results_json(results: AnalysisResults, path: Path | None = None) -> Path:
    """Write results to JSON file."""
    if path is None:
        path = Path(__file__).parent / "data" / "results.json"
    with open(path, "w") as f:
        json.dump(results.to_dict(), f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Whatnut analysis pipeline")
    parser.add_argument(
        "--generate",
        action="store_true",
        help="Generate data/results.json",
    )
    parser.add_argument("--n-samples", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    print(f"Running analysis (n={args.n_samples}, seed={args.seed})...")
    results = run_analysis(n_samples=args.n_samples, seed=args.seed)

    if args.generate:
        path = generate_results_json(results)
        print(f"Results written to {path}")
    else:
        print(f"\n{'Nut':12s} {'LY':>6s} {'QALY':>6s} {'P(>0)':>6s} {'ICER':>10s}")
        print("-" * 44)
        for nid in sorted(results.nuts, key=lambda k: results.nuts[k].qaly_mean, reverse=True):
            na = results.nuts[nid]
            print(
                f"{nid:12s} {na.life_years_mean:6.2f} {na.qaly_mean:6.2f} "
                f"{na.p_positive:6.2f} ${na.icer_median:>9,.0f}"
            )
        print(f"\nPathway contributions: CVD {results.cvd_contribution_mean:.0%}, "
              f"Cancer {results.cancer_contribution_mean:.0%}, "
              f"Other {results.other_contribution_mean:.0%}")


if __name__ == "__main__":
    main()
