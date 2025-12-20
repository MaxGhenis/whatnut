"""Pathway-specific lifecycle model.

Extends the base lifecycle model to use cause-specific mortality effects
from Aune et al. 2016:
- CVD mortality: RR 0.75 (95% CI: 0.71-0.79)
- Cancer mortality: RR 0.87 (95% CI: 0.80-0.93)
- Other causes: RR 0.90 (assumed)

This allows for different temporal profiles since:
- CVD mortality peaks earlier (50-70)
- Cancer mortality more spread (60-85)
- Different discount sensitivities by pathway
"""

from dataclasses import dataclass
import numpy as np
from typing import Optional

from whatnut.lifecycle import (
    get_mortality_curve,
    get_quality_curve,
    LifecycleParams,
    LifecycleResult,
)


# Cause-specific relative risks from Aune et al. 2016
# https://bmcmedicine.biomedcentral.com/articles/10.1186/s12916-016-0730-3
CAUSE_SPECIFIC_RR = {
    'cvd': {
        'rr': 0.75,
        'ci_lower': 0.71,
        'ci_upper': 0.79,
        'log_sd': 0.03,  # Approximate from CI
        'source': 'Aune 2016, 20,381 CVD deaths',
    },
    'cancer': {
        'rr': 0.87,
        'ci_lower': 0.80,
        'ci_upper': 0.93,
        'log_sd': 0.04,
        'source': 'Aune 2016, 21,353 cancer deaths',
    },
    'other': {
        'rr': 0.90,
        'ci_lower': 0.85,
        'ci_upper': 0.95,
        'log_sd': 0.03,
        'source': 'Assumed (respiratory, diabetes, etc.)',
    },
}


# Cause-of-death fractions by age
# Source: CDC WONDER, 2021 US mortality data (approximate)
# CVD includes heart disease and cerebrovascular
# Cancer includes all malignant neoplasms
# Other includes respiratory, diabetes, accidents, Alzheimer's, etc.
CAUSE_FRACTIONS_BY_AGE = {
    20: (0.10, 0.05, 0.85),  # Young: mostly accidents, suicide
    30: (0.12, 0.10, 0.78),
    40: (0.20, 0.25, 0.55),
    50: (0.25, 0.35, 0.40),
    60: (0.30, 0.35, 0.35),
    70: (0.35, 0.30, 0.35),
    80: (0.40, 0.20, 0.40),
    90: (0.45, 0.10, 0.45),
    100: (0.50, 0.05, 0.45),
}


def interpolate_cause_fractions(age: int) -> tuple[float, float, float]:
    """Get cause-of-death fractions (CVD, cancer, other) for a given age."""
    ages = sorted(CAUSE_FRACTIONS_BY_AGE.keys())

    if age <= ages[0]:
        return CAUSE_FRACTIONS_BY_AGE[ages[0]]
    if age >= ages[-1]:
        return CAUSE_FRACTIONS_BY_AGE[ages[-1]]

    lower_age = max(a for a in ages if a <= age)
    upper_age = min(a for a in ages if a > age)

    lower_fracs = CAUSE_FRACTIONS_BY_AGE[lower_age]
    upper_fracs = CAUSE_FRACTIONS_BY_AGE[upper_age]

    frac = (age - lower_age) / (upper_age - lower_age)

    return tuple(
        lower_fracs[i] + frac * (upper_fracs[i] - lower_fracs[i])
        for i in range(3)
    )


def get_weighted_rr(age: int, rr_cvd: float, rr_cancer: float, rr_other: float) -> float:
    """Get age-weighted relative risk based on cause-of-death mix."""
    cvd_f, cancer_f, other_f = interpolate_cause_fractions(age)
    return cvd_f * rr_cvd + cancer_f * rr_cancer + other_f * rr_other


@dataclass
class PathwayParams:
    """Parameters for pathway-specific lifecycle model."""

    start_age: int = 40
    max_age: int = 110
    discount_rate: float = 0.03

    # Cause-specific relative risks
    rr_cvd: float = 0.75
    rr_cancer: float = 0.87
    rr_other: float = 0.90

    # Uncertainty (log-scale SD)
    rr_cvd_sd: float = 0.03
    rr_cancer_sd: float = 0.04
    rr_other_sd: float = 0.03

    # Confounding adjustment (applied to all pathways)
    # Evidence-optimized prior: Beta(1.5, 4.5) with mean 0.25
    # Calibrated by minimizing squared error to independent evidence:
    #   - LDL pathway calibration: ~17% of CVD effect mechanistically explained
    #   - UK Biobank vegetable-CVD: ~20% causal in sibling comparisons
    #   - Golestan cohort (Iran): effect persists without Western SES correlation
    #   - E-value = 1.8: effect unlikely to be zero
    # The 95% CI (2%-63%) spans pessimistic to moderately optimistic beliefs.
    confounding_alpha: float = 1.5  # Beta distribution alpha
    confounding_beta: float = 4.5   # Beta distribution beta
    # Point estimate for deterministic runs (mean of prior)
    confounding_adjustment: float = 0.25

    # Cost
    annual_cost: float = 250.0

    # Nut-specific adjustment (multiplicative on log-RR, applies to all pathways)
    nut_adjustment: float = 1.0
    nut_adjustment_sd: float = 0.1


@dataclass
class PathwayResult:
    """Results from pathway-specific lifecycle model."""

    # By pathway (undiscounted)
    life_years_cvd: float
    life_years_cancer: float
    life_years_other: float

    # Totals
    life_years_gained: float
    qalys_gained: float

    # Discounted
    life_years_gained_discounted: float
    qalys_gained_discounted: float
    total_cost_discounted: float

    # Cost-effectiveness
    cost_per_qaly: float

    # Pathway contributions (fraction of total benefit)
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float


class PathwayLifecycleCEA:
    """Pathway-specific lifecycle cost-effectiveness model.

    Uses cause-specific mortality effects and age-varying cause-of-death
    fractions to model different temporal profiles for different pathways.

    Example:
        >>> model = PathwayLifecycleCEA(seed=42)
        >>> params = PathwayParams()
        >>> result = model.run(params)
        >>> print(f"CVD contribution: {result.cvd_contribution:.1%}")
        >>> print(f"Cancer contribution: {result.cancer_contribution:.1%}")
    """

    def __init__(self, seed: Optional[int] = None):
        self.rng = np.random.default_rng(seed)

    def run(self, params: PathwayParams) -> PathwayResult:
        """Run pathway-specific lifecycle model."""
        ages = np.arange(params.start_age, params.max_age + 1)
        n_years = len(ages)

        # Get baseline mortality and quality curves
        mortality_baseline = get_mortality_curve(params.start_age, params.max_age)
        quality_weights = get_quality_curve(params.start_age, params.max_age)

        # Apply nut adjustment to all RRs
        rr_cvd = params.rr_cvd ** params.nut_adjustment
        rr_cancer = params.rr_cancer ** params.nut_adjustment
        rr_other = params.rr_other ** params.nut_adjustment

        # Apply confounding adjustment
        rr_cvd = 1 - (1 - rr_cvd) * params.confounding_adjustment
        rr_cancer = 1 - (1 - rr_cancer) * params.confounding_adjustment
        rr_other = 1 - (1 - rr_other) * params.confounding_adjustment

        # Calculate age-specific weighted RR
        weighted_rr = np.array([
            get_weighted_rr(age, rr_cvd, rr_cancer, rr_other)
            for age in ages
        ])

        # Apply to mortality
        mortality_intervention = mortality_baseline * weighted_rr

        # Calculate survival curves
        survival_baseline = np.cumprod(1 - mortality_baseline)
        survival_baseline = np.insert(survival_baseline[:-1], 0, 1.0)

        survival_intervention = np.cumprod(1 - mortality_intervention)
        survival_intervention = np.insert(survival_intervention[:-1], 0, 1.0)

        # Life years gained by pathway
        # Decompose total mortality reduction into pathway contributions
        ly_gained_by_age = survival_intervention - survival_baseline

        # Pathway contributions (based on cause fractions and RR differentials)
        cvd_contrib = np.zeros(n_years)
        cancer_contrib = np.zeros(n_years)
        other_contrib = np.zeros(n_years)

        for i, age in enumerate(ages):
            cvd_f, cancer_f, other_f = interpolate_cause_fractions(age)

            # Contribution proportional to (fraction * mortality_reduction)
            cvd_reduction = cvd_f * (1 - rr_cvd)
            cancer_reduction = cancer_f * (1 - rr_cancer)
            other_reduction = other_f * (1 - rr_other)
            total_reduction = cvd_reduction + cancer_reduction + other_reduction

            if total_reduction > 0:
                cvd_contrib[i] = cvd_reduction / total_reduction
                cancer_contrib[i] = cancer_reduction / total_reduction
                other_contrib[i] = other_reduction / total_reduction

        # Life years by pathway
        ly_cvd = np.sum(ly_gained_by_age * cvd_contrib)
        ly_cancer = np.sum(ly_gained_by_age * cancer_contrib)
        ly_other = np.sum(ly_gained_by_age * other_contrib)
        ly_total = np.sum(ly_gained_by_age)

        # QALYs
        qaly_gain_by_age = ly_gained_by_age * quality_weights
        qalys_gained = np.sum(qaly_gain_by_age)

        # Discounting
        discount_factors = np.array([
            1 / (1 + params.discount_rate) ** t for t in range(n_years)
        ])

        ly_gained_disc = np.sum(ly_gained_by_age * discount_factors)
        qalys_gained_disc = np.sum(qaly_gain_by_age * discount_factors)

        # Costs
        annual_costs = params.annual_cost * survival_intervention
        total_cost_disc = np.sum(annual_costs * discount_factors)

        # ICER
        cost_per_qaly = total_cost_disc / qalys_gained_disc if qalys_gained_disc > 0 else float('inf')

        # Overall pathway contributions (weighted by discounted LY)
        ly_cvd_disc = np.sum(ly_gained_by_age * cvd_contrib * discount_factors)
        ly_cancer_disc = np.sum(ly_gained_by_age * cancer_contrib * discount_factors)
        ly_other_disc = np.sum(ly_gained_by_age * other_contrib * discount_factors)

        cvd_contribution = ly_cvd_disc / ly_gained_disc if ly_gained_disc > 0 else 0
        cancer_contribution = ly_cancer_disc / ly_gained_disc if ly_gained_disc > 0 else 0
        other_contribution = ly_other_disc / ly_gained_disc if ly_gained_disc > 0 else 0

        return PathwayResult(
            life_years_cvd=ly_cvd,
            life_years_cancer=ly_cancer,
            life_years_other=ly_other,
            life_years_gained=ly_total,
            qalys_gained=qalys_gained,
            life_years_gained_discounted=ly_gained_disc,
            qalys_gained_discounted=qalys_gained_disc,
            total_cost_discounted=total_cost_disc,
            cost_per_qaly=cost_per_qaly,
            cvd_contribution=cvd_contribution,
            cancer_contribution=cancer_contribution,
            other_contribution=other_contribution,
        )

    def run_monte_carlo(
        self,
        params: PathwayParams,
        n_simulations: int = 10000
    ) -> dict:
        """Run Monte Carlo over pathway-specific uncertainty."""
        qalys = np.zeros(n_simulations)
        icers = np.zeros(n_simulations)
        cvd_contribs = np.zeros(n_simulations)
        cancer_contribs = np.zeros(n_simulations)

        for i in range(n_simulations):
            # Sample pathway-specific RRs
            rr_cvd = np.exp(self.rng.normal(np.log(params.rr_cvd), params.rr_cvd_sd))
            rr_cancer = np.exp(self.rng.normal(np.log(params.rr_cancer), params.rr_cancer_sd))
            rr_other = np.exp(self.rng.normal(np.log(params.rr_other), params.rr_other_sd))

            # Sample confounding from calibrated prior
            sampled_conf = self.rng.beta(params.confounding_alpha, params.confounding_beta)

            # Sample nut adjustment
            sampled_adj = self.rng.normal(params.nut_adjustment, params.nut_adjustment_sd)

            sim_params = PathwayParams(
                start_age=params.start_age,
                max_age=params.max_age,
                discount_rate=params.discount_rate,
                rr_cvd=rr_cvd,
                rr_cancer=rr_cancer,
                rr_other=rr_other,
                confounding_adjustment=sampled_conf,
                annual_cost=params.annual_cost,
                nut_adjustment=sampled_adj,
            )

            result = self.run(sim_params)
            qalys[i] = result.qalys_gained_discounted
            icers[i] = result.cost_per_qaly
            cvd_contribs[i] = result.cvd_contribution
            cancer_contribs[i] = result.cancer_contribution

        return {
            'qalys': qalys,
            'icers': icers,
            'cvd_contributions': cvd_contribs,
            'cancer_contributions': cancer_contribs,
            'qaly_mean': np.mean(qalys),
            'qaly_median': np.median(qalys),
            'qaly_ci_95': (np.percentile(qalys, 2.5), np.percentile(qalys, 97.5)),
            'icer_median': np.median(icers[np.isfinite(icers)]),
            'cvd_contribution_mean': np.mean(cvd_contribs),
            'cancer_contribution_mean': np.mean(cancer_contribs),
        }


def compare_models():
    """Compare single-RR vs pathway-specific models."""
    from whatnut.lifecycle import LifecycleCEA, LifecycleParams

    # Single-RR model (current)
    single_model = LifecycleCEA(seed=42)
    single_params = LifecycleParams(start_age=40, hazard_ratio=0.78)
    single_result = single_model.run(single_params)

    # Pathway model
    pathway_model = PathwayLifecycleCEA(seed=42)
    pathway_params = PathwayParams(start_age=40)
    pathway_result = pathway_model.run(pathway_params)

    print("=== Model Comparison ===\n")
    print("Single-RR Model (HR=0.78 uniform):")
    print(f"  QALYs (discounted): {single_result.qalys_gained_discounted:.3f}")
    print(f"  Cost/QALY: ${single_result.cost_per_qaly:,.0f}")
    print()
    print("Pathway Model (CVD=0.75, Cancer=0.87, Other=0.90):")
    print(f"  QALYs (discounted): {pathway_result.qalys_gained_discounted:.3f}")
    print(f"  Cost/QALY: ${pathway_result.cost_per_qaly:,.0f}")
    print()
    print("Pathway contributions:")
    print(f"  CVD: {pathway_result.cvd_contribution:.1%}")
    print(f"  Cancer: {pathway_result.cancer_contribution:.1%}")
    print(f"  Other: {pathway_result.other_contribution:.1%}")


if __name__ == '__main__':
    compare_models()
