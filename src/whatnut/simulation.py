"""Monte Carlo simulation for QALY estimation.

Methodology:
1. Sample base hazard ratio from meta-analysis (log-normal)
2. Apply nut-specific adjustment factors (normal)
3. Convert HR to years of life gained
4. Apply quality-of-life weight (beta)
5. Apply confounding adjustment (beta)
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np

from whatnut.nuts import NUTS, get_nut


@dataclass
class SimulationParams:
    """Parameters for Monte Carlo simulation."""

    age: int = 40
    base_hr_mean: float = 0.78  # From Aune 2016 meta-analysis
    base_hr_sd: float = 0.08  # Log-space SD
    life_expectancy: float = 40.0  # Remaining years
    quality_weight_alpha: float = 17.0  # Beta distribution params for QoL
    quality_weight_beta: float = 3.0
    confounding_adjustment: float = 0.80  # Assume 20% is confounding
    n_simulations: int = 10000
    seed: Optional[int] = None

    def __post_init__(self):
        if self.age < 0 or self.age > 120:
            raise ValueError(f"Age must be 0-120, got {self.age}")
        if self.base_hr_mean >= 1.0:
            raise ValueError(f"base_hr_mean must be < 1.0 (protective), got {self.base_hr_mean}")
        if self.n_simulations < 1:
            raise ValueError(f"n_simulations must be >= 1, got {self.n_simulations}")


DEFAULT_PARAMS = SimulationParams()


@dataclass
class NutResult:
    """Simulation results for a single nut."""

    nut_id: str
    samples: np.ndarray
    median: float = 0.0
    mean: float = 0.0
    sd: float = 0.0
    ci_95: tuple[float, float] = (0.0, 0.0)
    ci_80: tuple[float, float] = (0.0, 0.0)
    p_positive: float = 0.0
    p_gt_1_year: float = 0.0

    def __post_init__(self):
        if len(self.samples) > 0:
            self.median = float(np.median(self.samples))
            self.mean = float(np.mean(self.samples))
            self.sd = float(np.std(self.samples))
            self.ci_95 = (
                float(np.percentile(self.samples, 2.5)),
                float(np.percentile(self.samples, 97.5)),
            )
            self.ci_80 = (
                float(np.percentile(self.samples, 10)),
                float(np.percentile(self.samples, 90)),
            )
            self.p_positive = float(np.mean(self.samples > 0))
            self.p_gt_1_year = float(np.mean(self.samples > 1))


@dataclass
class CategoryEffect:
    """Effect of any nut consumption vs no nuts."""

    median: float
    ci_95: tuple[float, float]


@dataclass
class SimulationResult:
    """Full simulation results."""

    params: SimulationParams
    results: list[NutResult]
    category_effect: CategoryEffect


class MonteCarloSimulation:
    """Monte Carlo simulation for nut QALY estimation."""

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)

    def run(self, params: SimulationParams) -> SimulationResult:
        """Run simulation for all nuts."""
        if params.seed is not None:
            self.rng = np.random.default_rng(params.seed)

        results = []
        category_samples = None

        for nut in NUTS:
            samples = self._simulate_nut(nut.id, params)
            nut_result = NutResult(nut_id=nut.id, samples=samples)
            results.append(nut_result)

            # Use almond as reference for category effect
            if nut.id == "almond":
                category_samples = samples

        # Sort by median (descending)
        results.sort(key=lambda r: r.median, reverse=True)

        # Category effect (any nut vs no nuts)
        if category_samples is None:
            category_samples = results[0].samples
        category_effect = CategoryEffect(
            median=float(np.median(category_samples)),
            ci_95=(
                float(np.percentile(category_samples, 2.5)),
                float(np.percentile(category_samples, 97.5)),
            ),
        )

        return SimulationResult(
            params=params,
            results=results,
            category_effect=category_effect,
        )

    def _simulate_nut(self, nut_id: str, params: SimulationParams) -> np.ndarray:
        """Run simulation for a single nut."""
        nut = get_nut(nut_id)
        if nut is None:
            raise ValueError(f"Unknown nut: {nut_id}")

        n = params.n_simulations

        # Sample base hazard ratio (log-normal)
        # If HR = 0.78, log(HR) = -0.248
        log_hr_mean = np.log(params.base_hr_mean)
        base_hr = self.rng.lognormal(log_hr_mean, params.base_hr_sd, n)

        # Sample nut-specific adjustment factor
        adj_factor = self.rng.normal(
            nut.adjustment_factor.mean,
            nut.adjustment_factor.sd,
            n,
        )

        # Apply adjustment to HR
        # Higher adjustment = lower HR = better survival
        adj_hr = np.power(base_hr, adj_factor)

        # Sample life expectancy with uncertainty
        life_exp = self.rng.normal(params.life_expectancy, 3, n)
        life_exp = np.maximum(life_exp, 1)  # At least 1 year

        # Sample quality weight (beta distribution)
        quality = self.rng.beta(
            params.quality_weight_alpha,
            params.quality_weight_beta,
            n,
        )

        # Base years of life gained (simplified Gompertz)
        # This is calibrated to match meta-analysis estimates for HR = 0.78
        base_ylg = self.rng.normal(3.2, 0.8, n)

        # Scale by hazard reduction ratio
        # Lower adj_hr = more hazard reduction = more YLG
        # Formula: YLG scales with (1 - HR), normalized to base HR
        base_hazard_reduction = 1 - 0.78  # 22% reduction at baseline
        nut_hazard_reduction = 1 - np.clip(adj_hr, 0.01, 0.99)
        ylg = base_ylg * (nut_hazard_reduction / base_hazard_reduction)

        # Quality-of-life effect (small, independent)
        qol_effect = self.rng.normal(0.02, 0.01, n)

        # Confounding adjustment (beta distribution centered on param)
        conf_alpha = params.confounding_adjustment * 10
        conf_beta = (1 - params.confounding_adjustment) * 10
        conf_adj = self.rng.beta(conf_alpha, conf_beta, n)

        # Calculate QALYs
        mortality_qalys = ylg * quality * conf_adj
        quality_qalys = life_exp * qol_effect * quality * conf_adj
        total_qalys = mortality_qalys + quality_qalys

        return total_qalys
