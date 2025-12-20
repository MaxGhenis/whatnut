"""Pre-computed simulation results for presentation layer.

This module stores canonical results from the Monte Carlo simulation,
allowing notebooks to display results without re-running computation.

Results are generated with seed=42 for reproducibility.
"""

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


def get_results() -> PrecomputedResults:
    """Get canonical pre-computed results."""
    return RESULTS


if __name__ == "__main__":
    # Regenerate and print results for updating RESULTS constant
    print("Generating fresh results...")
    fresh = _generate_results()
    print(f"\nCategory effect: {fresh.category_effect_median} QALYs")
    print(f"95% CI: {fresh.category_effect_ci_95}")
    print("\nNut results:")
    for n in fresh.nuts:
        print(f"  {n.nut_id}: {n.median} ({n.ci_95[0]}-{n.ci_95[1]})")
