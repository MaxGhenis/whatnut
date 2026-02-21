"""End-to-end analysis pipeline: model -> lifecycle -> results.

Usage:
    python -m whatnut.pipeline --generate   # Generate data/results.json
    python -m whatnut.pipeline              # Print summary
"""

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from whatnut.config import NUT_IDS, PATHWAYS, get_nut
from whatnut.lifecycle import LifecycleResult, run_lifecycle
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

    # Cost-effectiveness
    annual_cost: float
    icer_median: float
    icer_ci_lower: float
    icer_ci_upper: float | None  # None if dominated in lower tail

    # Pathway-specific RRs (posterior means)
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
    discount_rate: float
    confounding_alpha: float
    confounding_beta: float
    confounding_mean: float

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
            "discount_rate": self.discount_rate,
            "confounding_alpha": self.confounding_alpha,
            "confounding_beta": self.confounding_beta,
            "confounding_mean": self.confounding_mean,
            "cvd_contribution_mean": self.cvd_contribution_mean,
            "cancer_contribution_mean": self.cancer_contribution_mean,
            "other_contribution_mean": self.other_contribution_mean,
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
    discount_rate: float = 0.03,
    confounding_alpha: float = 2.5,
    confounding_beta: float = 2.5,
) -> AnalysisResults:
    """Run full analysis: model sampling -> lifecycle -> summary.

    Args:
        n_samples: Number of Monte Carlo draws.
        seed: Random seed for reproducibility.
        start_age: Age at start of nut consumption.
        discount_rate: Annual discount rate for QALYs and costs.
        confounding_alpha: Beta prior alpha for causal fraction.
        confounding_beta: Beta prior beta for causal fraction.

    Returns:
        AnalysisResults with every number needed for the paper.
    """
    # Step 1: Sample RRs from model
    samples = sample_model(
        n_samples=n_samples,
        seed=seed,
        confounding_alpha=confounding_alpha,
        confounding_beta=confounding_beta,
    )

    confounding_mean = confounding_alpha / (confounding_alpha + confounding_beta)
    nut_analyses: dict[str, NutAnalysis] = {}

    # Step 2: Run lifecycle for each nut, for each sample
    for j, nut_id in enumerate(samples.nut_ids):
        nut_profile = get_nut(nut_id)

        qalys_disc = np.empty(n_samples)
        qalys_undisc = np.empty(n_samples)
        life_years = np.empty(n_samples)
        icers = np.empty(n_samples)

        for i in range(n_samples):
            rr_cvd = samples.rr["cvd"][i, j]
            rr_cancer = samples.rr["cancer"][i, j]
            rr_other = samples.rr["other"][i, j]

            result = run_lifecycle(
                rr_cvd=rr_cvd,
                rr_cancer=rr_cancer,
                rr_other=rr_other,
                annual_cost=nut_profile.annual_cost,
                start_age=start_age,
                discount_rate=discount_rate,
            )

            qalys_disc[i] = result.qalys_gained_discounted
            qalys_undisc[i] = result.qalys_gained
            life_years[i] = result.life_years_gained
            icers[i] = result.cost_per_qaly

        # Summarize
        icer_finite = icers[np.isfinite(icers) & (icers > 0)]
        icer_upper = (
            float(np.percentile(icer_finite, 97.5))
            if len(icer_finite) > 0 and np.percentile(qalys_disc, 2.5) > 0
            else None
        )

        # Compute pathway contributions from mean RRs (stable, no ratio blow-up)
        rr_cvd_mean = float(np.mean(samples.rr["cvd"][:, j]))
        rr_cancer_mean = float(np.mean(samples.rr["cancer"][:, j]))
        rr_other_mean = float(np.mean(samples.rr["other"][:, j]))

        mean_result = run_lifecycle(
            rr_cvd=rr_cvd_mean,
            rr_cancer=rr_cancer_mean,
            rr_other=rr_other_mean,
            annual_cost=nut_profile.annual_cost,
            start_age=start_age,
            discount_rate=discount_rate,
        )

        na = NutAnalysis(
            nut_id=nut_id,
            name=nut_id.capitalize(),
            evidence=nut_profile.evidence,
            life_years_mean=round(float(np.mean(life_years)), 2),
            life_years_ci_lower=round(float(np.percentile(life_years, 2.5)), 2),
            life_years_ci_upper=round(float(np.percentile(life_years, 97.5)), 2),
            qaly_mean=round(float(np.mean(qalys_disc)), 2),
            qaly_ci_lower=round(float(np.percentile(qalys_disc, 2.5)), 2),
            qaly_ci_upper=round(float(np.percentile(qalys_disc, 97.5)), 2),
            qaly_undiscounted_mean=round(float(np.mean(qalys_undisc)), 2),
            p_positive=round(float(np.mean(qalys_disc > 0)), 2),
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
        discount_rate=discount_rate,
        confounding_alpha=confounding_alpha,
        confounding_beta=confounding_beta,
        confounding_mean=confounding_mean,
        nuts=nut_analyses,
        cvd_contribution_mean=round(float(np.mean(all_cvd)), 2),
        cancer_contribution_mean=round(float(np.mean(all_cancer)), 2),
        other_contribution_mean=round(float(np.mean(all_other)), 2),
    )


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
