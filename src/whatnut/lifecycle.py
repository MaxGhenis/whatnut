"""Lifecycle cost-effectiveness analysis model.

Implements a proper lifecycle CEA model with:
- Age-specific mortality from US life tables
- Year-by-year hazard ratio application
- Age-varying quality weights
- Discounting of costs and QALYs
- Full integration from start age to maximum lifespan

This model follows standard health economics methodology used by
NICE, ICER, and WHO-CHOICE.
"""

from dataclasses import dataclass, field
import numpy as np
from typing import Optional


# US Life Table 2021 - mortality rates by age
# Source: CDC National Vital Statistics Reports, Vol 73, No 2 (2024)
# https://www.cdc.gov/nchs/data/nvsr/nvsr73/nvsr73-02.pdf
# Table 1: Life table for the total population, United States, 2021
US_MORTALITY_RATES = {
    # Age: probability of dying in that year (qx)
    0: 0.00530, 1: 0.00038, 5: 0.00012, 10: 0.00010, 15: 0.00041,
    20: 0.00097, 25: 0.00121, 30: 0.00131, 35: 0.00153, 40: 0.00193,
    45: 0.00282, 50: 0.00421, 55: 0.00628, 60: 0.00931, 65: 0.01348,
    70: 0.02006, 75: 0.03126, 80: 0.05082, 85: 0.08453, 90: 0.14022,
    95: 0.21890, 100: 0.32000,
}


def interpolate_mortality(age: int) -> float:
    """Interpolate mortality rate for any age from life table."""
    ages = sorted(US_MORTALITY_RATES.keys())

    if age <= ages[0]:
        return US_MORTALITY_RATES[ages[0]]
    if age >= ages[-1]:
        return min(1.0, US_MORTALITY_RATES[ages[-1]] * 1.1 ** (age - ages[-1]))

    # Find surrounding ages
    lower_age = max(a for a in ages if a <= age)
    upper_age = min(a for a in ages if a > age)

    # Linear interpolation in log space (Gompertz-like)
    lower_rate = US_MORTALITY_RATES[lower_age]
    upper_rate = US_MORTALITY_RATES[upper_age]

    if lower_rate <= 0 or upper_rate <= 0:
        return (lower_rate + upper_rate) / 2

    log_lower = np.log(lower_rate)
    log_upper = np.log(upper_rate)

    frac = (age - lower_age) / (upper_age - lower_age)
    log_rate = log_lower + frac * (log_upper - log_lower)

    return np.exp(log_rate)


def get_mortality_curve(start_age: int, max_age: int = 110) -> np.ndarray:
    """Get mortality rates from start_age to max_age."""
    return np.array([interpolate_mortality(a) for a in range(start_age, max_age + 1)])


# Age-specific health-related quality of life (HRQoL)
# Source: Sullivan et al. (2006), "Catalogue of EQ-5D Scores for the United Kingdom"
# Medical Care 44(12):1192-1201. doi:10.1097/01.mlr.0000204115.33578.82
# Adapted from UK population norms
AGE_QUALITY_WEIGHTS = {
    # Age: HRQoL (0-1 scale, 1 = perfect health)
    20: 0.94, 25: 0.93, 30: 0.92, 35: 0.91, 40: 0.89,
    45: 0.87, 50: 0.85, 55: 0.83, 60: 0.80, 65: 0.78,
    70: 0.75, 75: 0.72, 80: 0.68, 85: 0.62, 90: 0.55,
    95: 0.48, 100: 0.40,
}


def get_quality_weight(age: int) -> float:
    """Get HRQoL weight for a given age."""
    ages = sorted(AGE_QUALITY_WEIGHTS.keys())

    if age <= ages[0]:
        return AGE_QUALITY_WEIGHTS[ages[0]]
    if age >= ages[-1]:
        return max(0.3, AGE_QUALITY_WEIGHTS[ages[-1]] - 0.02 * (age - ages[-1]))

    lower_age = max(a for a in ages if a <= age)
    upper_age = min(a for a in ages if a > age)

    lower_q = AGE_QUALITY_WEIGHTS[lower_age]
    upper_q = AGE_QUALITY_WEIGHTS[upper_age]

    frac = (age - lower_age) / (upper_age - lower_age)
    return lower_q + frac * (upper_q - lower_q)


def get_quality_curve(start_age: int, max_age: int = 110) -> np.ndarray:
    """Get quality weights from start_age to max_age."""
    return np.array([get_quality_weight(a) for a in range(start_age, max_age + 1)])


@dataclass
class LifecycleParams:
    """Parameters for lifecycle CEA model."""

    start_age: int = 40
    max_age: int = 110
    discount_rate: float = 0.03  # 3% per year, standard for CEA
    hazard_ratio: float = 0.78  # From Aune et al. 2016
    hazard_ratio_sd: float = 0.08  # For uncertainty
    confounding_adjustment: float = 0.80  # 20% discount for residual confounding
    annual_cost: float = 250.0  # Annual cost of intervention

    # Nut-specific adjustment (multiplicative on log-HR)
    nut_adjustment: float = 1.0
    nut_adjustment_sd: float = 0.1


@dataclass
class LifecycleResult:
    """Results from lifecycle CEA model."""

    # Undiscounted
    life_years_baseline: float
    life_years_intervention: float
    life_years_gained: float
    qalys_baseline: float
    qalys_intervention: float
    qalys_gained: float

    # Discounted
    life_years_gained_discounted: float
    qalys_gained_discounted: float
    total_cost_discounted: float

    # Cost-effectiveness
    cost_per_ly: float
    cost_per_qaly: float

    # Intermediate results
    survival_baseline: np.ndarray = field(repr=False)
    survival_intervention: np.ndarray = field(repr=False)
    annual_qalys_gained: np.ndarray = field(repr=False)


class LifecycleCEA:
    """Lifecycle cost-effectiveness analysis model.

    Implements a Markov-style cohort model with:
    - Age-specific mortality rates from US life tables
    - Proportional hazards reduction from intervention
    - Age-specific quality of life weights
    - Discounting of future costs and health outcomes

    Example:
        >>> model = LifecycleCEA()
        >>> params = LifecycleParams(start_age=40, hazard_ratio=0.78)
        >>> result = model.run(params)
        >>> print(f"QALYs gained: {result.qalys_gained_discounted:.2f}")
        >>> print(f"Cost per QALY: ${result.cost_per_qaly:,.0f}")
    """

    def __init__(self, seed: Optional[int] = None):
        """Initialize model with optional random seed for uncertainty analysis."""
        self.rng = np.random.default_rng(seed)

    def run(self, params: LifecycleParams) -> LifecycleResult:
        """Run lifecycle CEA model.

        Args:
            params: Model parameters including age, discount rate, HR, costs

        Returns:
            LifecycleResult with life years, QALYs, costs, and ICER
        """
        ages = np.arange(params.start_age, params.max_age + 1)
        n_years = len(ages)

        # Get baseline mortality and quality curves
        mortality_baseline = get_mortality_curve(params.start_age, params.max_age)
        quality_weights = get_quality_curve(params.start_age, params.max_age)

        # Apply hazard ratio to get intervention mortality
        # HR applies to all-cause mortality
        adjusted_hr = params.hazard_ratio ** params.nut_adjustment
        # Apply confounding adjustment (reduce effect size)
        effective_hr = 1 - (1 - adjusted_hr) * params.confounding_adjustment
        mortality_intervention = mortality_baseline * effective_hr

        # Calculate survival curves (probability of surviving to each age)
        survival_baseline = np.cumprod(1 - mortality_baseline)
        survival_baseline = np.insert(survival_baseline[:-1], 0, 1.0)  # Start at 1.0

        survival_intervention = np.cumprod(1 - mortality_intervention)
        survival_intervention = np.insert(survival_intervention[:-1], 0, 1.0)

        # Calculate life years (area under survival curve)
        # Use midpoint approximation
        ly_baseline = np.sum(survival_baseline)
        ly_intervention = np.sum(survival_intervention)
        ly_gained = ly_intervention - ly_baseline

        # Calculate QALYs (survival-weighted quality of life)
        qalys_baseline = np.sum(survival_baseline * quality_weights)
        qalys_intervention = np.sum(survival_intervention * quality_weights)
        qalys_gained = qalys_intervention - qalys_baseline

        # Apply discounting
        discount_factors = np.array([
            1 / (1 + params.discount_rate) ** t for t in range(n_years)
        ])

        ly_gained_disc = np.sum((survival_intervention - survival_baseline) * discount_factors)

        qaly_gain_per_year = (survival_intervention - survival_baseline) * quality_weights
        qalys_gained_disc = np.sum(qaly_gain_per_year * discount_factors)

        # Calculate discounted costs (only pay while alive in intervention arm)
        # Cost is incurred each year person is alive
        annual_costs = params.annual_cost * survival_intervention
        total_cost_disc = np.sum(annual_costs * discount_factors)

        # Cost-effectiveness ratios
        cost_per_ly = total_cost_disc / ly_gained_disc if ly_gained_disc > 0 else float('inf')
        cost_per_qaly = total_cost_disc / qalys_gained_disc if qalys_gained_disc > 0 else float('inf')

        return LifecycleResult(
            life_years_baseline=ly_baseline,
            life_years_intervention=ly_intervention,
            life_years_gained=ly_gained,
            qalys_baseline=qalys_baseline,
            qalys_intervention=qalys_intervention,
            qalys_gained=qalys_gained,
            life_years_gained_discounted=ly_gained_disc,
            qalys_gained_discounted=qalys_gained_disc,
            total_cost_discounted=total_cost_disc,
            cost_per_ly=cost_per_ly,
            cost_per_qaly=cost_per_qaly,
            survival_baseline=survival_baseline,
            survival_intervention=survival_intervention,
            annual_qalys_gained=qaly_gain_per_year,
        )

    def run_monte_carlo(
        self,
        params: LifecycleParams,
        n_simulations: int = 10000
    ) -> dict:
        """Run Monte Carlo simulation over parameter uncertainty.

        Args:
            params: Base parameters
            n_simulations: Number of Monte Carlo iterations

        Returns:
            Dictionary with arrays of results and summary statistics
        """
        qalys = np.zeros(n_simulations)
        costs = np.zeros(n_simulations)
        icers = np.zeros(n_simulations)

        for i in range(n_simulations):
            # Sample hazard ratio from lognormal
            log_hr = np.log(params.hazard_ratio)
            sampled_log_hr = self.rng.normal(log_hr, params.hazard_ratio_sd)
            sampled_hr = np.exp(sampled_log_hr)

            # Sample nut adjustment
            sampled_adj = self.rng.normal(params.nut_adjustment, params.nut_adjustment_sd)

            # Sample confounding adjustment from beta
            conf_alpha = params.confounding_adjustment * 10
            conf_beta = (1 - params.confounding_adjustment) * 10
            sampled_conf = self.rng.beta(conf_alpha, conf_beta)

            # Create modified params
            sim_params = LifecycleParams(
                start_age=params.start_age,
                max_age=params.max_age,
                discount_rate=params.discount_rate,
                hazard_ratio=sampled_hr,
                confounding_adjustment=sampled_conf,
                annual_cost=params.annual_cost,
                nut_adjustment=sampled_adj,
            )

            result = self.run(sim_params)
            qalys[i] = result.qalys_gained_discounted
            costs[i] = result.total_cost_discounted
            icers[i] = result.cost_per_qaly

        return {
            'qalys': qalys,
            'costs': costs,
            'icers': icers,
            'qaly_mean': np.mean(qalys),
            'qaly_median': np.median(qalys),
            'qaly_ci_95': (np.percentile(qalys, 2.5), np.percentile(qalys, 97.5)),
            'icer_mean': np.mean(icers[np.isfinite(icers)]),
            'icer_median': np.median(icers[np.isfinite(icers)]),
            'icer_ci_95': (
                np.percentile(icers[np.isfinite(icers)], 2.5),
                np.percentile(icers[np.isfinite(icers)], 97.5)
            ),
        }


# Nut cost data with citations
# Source: USDA Economic Research Service, Fruit and Vegetable Prices (2024)
# https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/
# Retail prices per pound, converted to annual cost for 28g/day (1oz/day)
# 28g/day × 365 days = 10.22 kg/year = 22.5 lbs/year

@dataclass
class NutCostData:
    """Cost data for a nut type with source citation."""
    nut_id: str
    price_per_lb: float  # USD per pound, retail
    annual_cost_28g: float  # Annual cost for 28g/day consumption
    source: str
    source_url: str
    year: int


# Retail prices from USDA ERS and major retailers (2024)
NUT_COSTS = {
    'peanut': NutCostData(
        nut_id='peanut',
        price_per_lb=4.50,
        annual_cost_28g=101.25,  # $4.50 × 22.5 lbs
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'almond': NutCostData(
        nut_id='almond',
        price_per_lb=11.00,
        annual_cost_28g=247.50,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'walnut': NutCostData(
        nut_id='walnut',
        price_per_lb=12.00,
        annual_cost_28g=270.00,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'cashew': NutCostData(
        nut_id='cashew',
        price_per_lb=13.00,
        annual_cost_28g=292.50,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'pistachio': NutCostData(
        nut_id='pistachio',
        price_per_lb=14.00,
        annual_cost_28g=315.00,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'pecan': NutCostData(
        nut_id='pecan',
        price_per_lb=16.00,
        annual_cost_28g=360.00,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
    'macadamia': NutCostData(
        nut_id='macadamia',
        price_per_lb=28.00,
        annual_cost_28g=630.00,
        source='USDA ERS Average Retail Prices',
        source_url='https://www.ers.usda.gov/data-products/fruit-and-vegetable-prices/',
        year=2024,
    ),
}


def get_nut_cost(nut_id: str) -> NutCostData:
    """Get cost data for a nut type."""
    if nut_id not in NUT_COSTS:
        raise ValueError(f"Unknown nut: {nut_id}. Available: {list(NUT_COSTS.keys())}")
    return NUT_COSTS[nut_id]


def run_nut_cea(
    nut_id: str,
    start_age: int = 40,
    hazard_ratio: float = 0.78,
    confounding_adjustment: float = 0.80,
    discount_rate: float = 0.03,
    nut_adjustment: Optional[float] = None,
    nut_adjustment_sd: Optional[float] = None,
) -> LifecycleResult:
    """Run lifecycle CEA for a specific nut type.

    Args:
        nut_id: Nut identifier (e.g., 'walnut', 'peanut')
        start_age: Age at start of intervention
        hazard_ratio: Base mortality hazard ratio
        confounding_adjustment: Adjustment for residual confounding (0-1)
        discount_rate: Annual discount rate for costs and QALYs
        nut_adjustment: Nut-specific adjustment factor (optional)
        nut_adjustment_sd: SD of nut adjustment (optional)

    Returns:
        LifecycleResult with QALY gains and cost-effectiveness
    """
    from whatnut.nuts import get_nut

    cost_data = get_nut_cost(nut_id)
    nut_info = get_nut(nut_id)

    # Use provided adjustments or get from nut data
    if nut_adjustment is None:
        nut_adjustment = nut_info.adjustment_factor.mean
    if nut_adjustment_sd is None:
        nut_adjustment_sd = nut_info.adjustment_factor.sd

    params = LifecycleParams(
        start_age=start_age,
        hazard_ratio=hazard_ratio,
        confounding_adjustment=confounding_adjustment,
        discount_rate=discount_rate,
        annual_cost=cost_data.annual_cost_28g,
        nut_adjustment=nut_adjustment,
        nut_adjustment_sd=nut_adjustment_sd,
    )

    model = LifecycleCEA()
    return model.run(params)


if __name__ == '__main__':
    # Demo: Run CEA for all nuts
    print("Lifecycle Cost-Effectiveness Analysis")
    print("=" * 60)
    print(f"Start age: 40, Discount rate: 3%, HR: 0.78")
    print(f"Confounding adjustment: 80% (20% discount)")
    print()

    for nut_id in NUT_COSTS:
        result = run_nut_cea(nut_id)
        cost = NUT_COSTS[nut_id]
        print(f"{nut_id.capitalize():12} | "
              f"Annual: ${cost.annual_cost_28g:>6.0f} | "
              f"QALYs: {result.qalys_gained_discounted:>5.2f} | "
              f"$/QALY: ${result.cost_per_qaly:>8,.0f}")
