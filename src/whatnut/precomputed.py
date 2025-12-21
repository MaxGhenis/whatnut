"""Pre-computed simulation results for presentation layer.

DEPRECATED: This module is deprecated. Use paper_results.py instead.
paper_results.py is the single source of truth for all paper values
and is directly imported by the paper via MyST executable code cells.

This module stores canonical results from the lifecycle CEA model,
allowing notebooks to display results without re-running computation.

Results are generated with seed=42 for reproducibility.
"""

import warnings
warnings.warn(
    "precomputed.py is deprecated. Use paper_results.py instead.",
    DeprecationWarning,
    stacklevel=2
)

from dataclasses import dataclass
import numpy as np


@dataclass
class PrecomputedNutResult:
    """Pre-computed results for a single nut type."""

    nut_id: str
    median: float
    mean: float
    sd: float
    ci_95: tuple[float, float]
    ci_80: tuple[float, float]
    p_positive: float
    p_gt_1_year: float
    evidence_strength: str


@dataclass
class PrecomputedLifecycleResult:
    """Pre-computed lifecycle CEA results for a single nut type."""

    nut_id: str
    annual_cost: float
    qaly_median: float
    qaly_ci_95: tuple[float, float]
    icer_median: float  # Cost per QALY
    icer_ci_95: tuple[float, float]
    evidence_strength: str


@dataclass
class PrecomputedResults:
    """All pre-computed simulation results."""

    n_simulations: int
    seed: int
    category_effect_median: float
    category_effect_ci_95: tuple[float, float]
    nuts: list[PrecomputedNutResult]

    def get_nut(self, nut_id: str) -> PrecomputedNutResult:
        """Get results for a specific nut."""
        for nut in self.nuts:
            if nut.nut_id == nut_id:
                return nut
        raise ValueError(f"Unknown nut: {nut_id}")

    def to_dataframe(self):
        """Convert to pandas DataFrame for display."""
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "Nut": n.nut_id.capitalize(),
                    "Median QALYs": n.median,
                    "95% CI": f"[{n.ci_95[0]:.1f}, {n.ci_95[1]:.1f}]",
                    "P(positive)": f"{n.p_positive:.1%}",
                    "P(>1 QALY)": f"{n.p_gt_1_year:.1%}",
                    "Evidence": n.evidence_strength,
                }
                for n in self.nuts
            ]
        )


@dataclass
class PrecomputedLifecycleResults:
    """All pre-computed lifecycle CEA results."""

    n_simulations: int
    seed: int
    start_age: int
    discount_rate: float
    hazard_ratio: float
    confounding_adjustment: float
    category_effect_qaly: float  # Discounted QALYs for generic nut
    category_effect_ci_95: tuple[float, float]
    nuts: list[PrecomputedLifecycleResult]

    def get_nut(self, nut_id: str) -> PrecomputedLifecycleResult:
        """Get lifecycle results for a specific nut."""
        for nut in self.nuts:
            if nut.nut_id == nut_id:
                return nut
        raise ValueError(f"Unknown nut: {nut_id}")

    def to_dataframe(self):
        """Convert to pandas DataFrame for display."""
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "Nut": n.nut_id.capitalize(),
                    "Annual Cost": f"${n.annual_cost:,.0f}",
                    "QALYs (discounted)": f"{n.qaly_median:.2f}",
                    "95% CI": f"[{n.qaly_ci_95[0]:.2f}, {n.qaly_ci_95[1]:.2f}]",
                    "Cost/QALY": f"${n.icer_median:,.0f}",
                    "Evidence": n.evidence_strength,
                }
                for n in self.nuts
            ]
        )


def _generate_results() -> PrecomputedResults:
    """Generate results from simulation (for updating cached values)."""
    from whatnut.simulation import MonteCarloSimulation, SimulationParams
    from whatnut.nuts import get_nut

    sim = MonteCarloSimulation(seed=42)
    params = SimulationParams(n_simulations=10000)
    result = sim.run(params)

    nuts = []
    for r in result.results:
        nut_info = get_nut(r.nut_id)
        nuts.append(
            PrecomputedNutResult(
                nut_id=r.nut_id,
                median=round(r.median, 2),
                mean=round(r.mean, 2),
                sd=round(r.sd, 2),
                ci_95=(round(r.ci_95[0], 1), round(r.ci_95[1], 1)),
                ci_80=(round(r.ci_80[0], 1), round(r.ci_80[1], 1)),
                p_positive=round(r.p_positive, 3),
                p_gt_1_year=round(r.p_gt_1_year, 3),
                evidence_strength=nut_info.evidence_strength,
            )
        )

    return PrecomputedResults(
        n_simulations=params.n_simulations,
        seed=42,
        category_effect_median=round(result.category_effect.median, 2),
        category_effect_ci_95=(
            round(result.category_effect.ci_95[0], 1),
            round(result.category_effect.ci_95[1], 1),
        ),
        nuts=nuts,
    )


def _generate_lifecycle_results() -> PrecomputedLifecycleResults:
    """Generate lifecycle CEA results (for updating cached values)."""
    from whatnut.lifecycle import LifecycleCEA, LifecycleParams, NUT_COSTS
    from whatnut.nuts import NUTS, get_nut

    model = LifecycleCEA(seed=42)
    base_params = LifecycleParams(start_age=40, annual_cost=250)

    # Run Monte Carlo for category effect
    cat_mc = model.run_monte_carlo(base_params, n_simulations=10000)

    # Run for each nut
    nuts = []
    for nut in NUTS:
        if nut.id not in NUT_COSTS:
            continue

        cost_data = NUT_COSTS[nut.id]
        params = LifecycleParams(
            start_age=40,
            annual_cost=cost_data.annual_cost_28g,
            nut_adjustment=nut.adjustment_factor.mean,
            nut_adjustment_sd=nut.adjustment_factor.sd,
        )
        mc = model.run_monte_carlo(params, n_simulations=10000)

        nuts.append(
            PrecomputedLifecycleResult(
                nut_id=nut.id,
                annual_cost=cost_data.annual_cost_28g,
                qaly_median=round(mc["qaly_median"], 3),
                qaly_ci_95=(
                    round(mc["qaly_ci_95"][0], 3),
                    round(mc["qaly_ci_95"][1], 3),
                ),
                icer_median=round(mc["icer_median"]),
                icer_ci_95=(
                    round(mc["icer_ci_95"][0]),
                    round(mc["icer_ci_95"][1]),
                ),
                evidence_strength=nut.evidence_strength,
            )
        )

    return PrecomputedLifecycleResults(
        n_simulations=10000,
        seed=42,
        start_age=40,
        discount_rate=0.03,
        hazard_ratio=0.78,
        confounding_adjustment=0.80,
        category_effect_qaly=round(cat_mc["qaly_median"], 3),
        category_effect_ci_95=(
            round(cat_mc["qaly_ci_95"][0], 3),
            round(cat_mc["qaly_ci_95"][1], 3),
        ),
        nuts=nuts,
    )


# Canonical results (seed=42, n=10000)
# These are the authoritative values used in the paper
RESULTS = PrecomputedResults(
    n_simulations=10000,
    seed=42,
    category_effect_median=2.54,
    category_effect_ci_95=(1.0, 4.5),
    nuts=[
        PrecomputedNutResult(
            nut_id="walnut",
            median=2.89,
            mean=2.95,
            sd=1.21,
            ci_95=(1.2, 5.1),
            ci_80=(1.6, 4.3),
            p_positive=0.998,
            p_gt_1_year=0.943,
            evidence_strength="strong",
        ),
        PrecomputedNutResult(
            nut_id="pistachio",
            median=2.72,
            mean=2.79,
            sd=1.18,
            ci_95=(1.0, 4.8),
            ci_80=(1.5, 4.1),
            p_positive=0.996,
            p_gt_1_year=0.921,
            evidence_strength="strong",
        ),
        PrecomputedNutResult(
            nut_id="macadamia",
            median=2.58,
            mean=2.67,
            sd=1.25,
            ci_95=(0.9, 4.9),
            ci_80=(1.3, 4.1),
            p_positive=0.991,
            p_gt_1_year=0.892,
            evidence_strength="moderate",
        ),
        PrecomputedNutResult(
            nut_id="almond",
            median=2.52,
            mean=2.58,
            sd=1.05,
            ci_95=(1.1, 4.4),
            ci_80=(1.4, 3.8),
            p_positive=0.997,
            p_gt_1_year=0.918,
            evidence_strength="strong",
        ),
        PrecomputedNutResult(
            nut_id="pecan",
            median=2.52,
            mean=2.61,
            sd=1.22,
            ci_95=(0.8, 4.8),
            ci_80=(1.3, 4.0),
            p_positive=0.989,
            p_gt_1_year=0.885,
            evidence_strength="moderate",
        ),
        PrecomputedNutResult(
            nut_id="peanut",
            median=2.38,
            mean=2.43,
            sd=1.02,
            ci_95=(1.0, 4.2),
            ci_80=(1.3, 3.6),
            p_positive=0.995,
            p_gt_1_year=0.897,
            evidence_strength="strong",
        ),
        PrecomputedNutResult(
            nut_id="cashew",
            median=2.24,
            mean=2.33,
            sd=1.15,
            ci_95=(0.7, 4.4),
            ci_80=(1.1, 3.7),
            p_positive=0.978,
            p_gt_1_year=0.834,
            evidence_strength="limited",
        ),
    ],
)


# Lifecycle CEA results (seed=42, n=10000)
# Generated with proper lifecycle model and discounting
LIFECYCLE_RESULTS = PrecomputedLifecycleResults(
    n_simulations=10000,
    seed=42,
    start_age=40,
    discount_rate=0.03,
    hazard_ratio=0.78,
    confounding_adjustment=0.80,
    category_effect_qaly=0.417,
    category_effect_ci_95=(0.148, 0.747),
    nuts=[
        PrecomputedLifecycleResult(
            nut_id="peanut",
            annual_cost=101.25,
            qaly_median=0.41,
            qaly_ci_95=(0.15, 0.74),
            icer_median=5949,
            icer_ci_95=(3300, 16400),
            evidence_strength="strong",
        ),
        PrecomputedLifecycleResult(
            nut_id="almond",
            annual_cost=247.50,
            qaly_median=0.42,
            qaly_ci_95=(0.15, 0.75),
            icer_median=13879,
            icer_ci_95=(7800, 38000),
            evidence_strength="strong",
        ),
        PrecomputedLifecycleResult(
            nut_id="walnut",
            annual_cost=270.00,
            qaly_median=0.48,
            qaly_ci_95=(0.17, 0.85),
            icer_median=13347,
            icer_ci_95=(7500, 37000),
            evidence_strength="strong",
        ),
        PrecomputedLifecycleResult(
            nut_id="cashew",
            annual_cost=292.50,
            qaly_median=0.41,
            qaly_ci_95=(0.14, 0.73),
            icer_median=17187,
            icer_ci_95=(9500, 48000),
            evidence_strength="limited",
        ),
        PrecomputedLifecycleResult(
            nut_id="pistachio",
            annual_cost=315.00,
            qaly_median=0.46,
            qaly_ci_95=(0.16, 0.82),
            icer_median=16476,
            icer_ci_95=(9100, 45000),
            evidence_strength="strong",
        ),
        PrecomputedLifecycleResult(
            nut_id="pecan",
            annual_cost=360.00,
            qaly_median=0.42,
            qaly_ci_95=(0.15, 0.76),
            icer_median=20188,
            icer_ci_95=(11000, 56000),
            evidence_strength="moderate",
        ),
        PrecomputedLifecycleResult(
            nut_id="macadamia",
            annual_cost=630.00,
            qaly_median=0.43,
            qaly_ci_95=(0.15, 0.77),
            icer_median=34699,
            icer_ci_95=(19000, 96000),
            evidence_strength="moderate",
        ),
    ],
)


def get_results() -> PrecomputedResults:
    """Get canonical pre-computed results (legacy undiscounted model)."""
    return RESULTS


def get_lifecycle_results() -> PrecomputedLifecycleResults:
    """Get canonical lifecycle CEA results (discounted, with cost-effectiveness)."""
    return LIFECYCLE_RESULTS


if __name__ == "__main__":
    # Regenerate and print results for updating constants
    print("Generating lifecycle CEA results...")
    fresh = _generate_lifecycle_results()
    print(f"\nCategory effect: {fresh.category_effect_qaly} QALYs (discounted)")
    print(f"95% CI: {fresh.category_effect_ci_95}")
    print("\nNut results (sorted by ICER):")
    for n in sorted(fresh.nuts, key=lambda x: x.icer_median):
        print(
            f"  {n.nut_id:12} | ${n.annual_cost:>6.0f}/yr | "
            f"{n.qaly_median:.3f} QALYs | ${n.icer_median:>6,}/QALY"
        )
