"""Pathway-specific lifecycle cost-effectiveness analysis.

Consolidates the previous lifecycle.py and lifecycle_pathways.py into a
single module. Uses cause-specific mortality effects and age-varying
cause-of-death fractions.

Input: pathway-specific RRs (already confounding-adjusted), annual cost,
       start age, discount rate.
Output: life years gained (total + by pathway), QALYs (discounted +
        undiscounted), ICER.
"""

from dataclasses import dataclass

import numpy as np

from whatnut.config import (
    get_cause_fractions,
    get_mortality_curve,
    get_quality_curve,
)


@dataclass
class LifecycleResult:
    """Results from pathway-specific lifecycle model."""

    # By pathway (undiscounted life years)
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

    # Pathway contributions (fraction of total discounted LY benefit)
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float


def run_lifecycle(
    rr_cvd: float,
    rr_cancer: float,
    rr_other: float,
    annual_cost: float,
    start_age: int = 40,
    max_age: int = 110,
    discount_rate: float = 0.03,
) -> LifecycleResult:
    """Run pathway-specific lifecycle model for a single set of RRs.

    Args:
        rr_cvd: Relative risk for CVD mortality (already confounding-adjusted).
        rr_cancer: Relative risk for cancer mortality.
        rr_other: Relative risk for other-cause mortality.
        annual_cost: Annual cost of intervention in USD.
        start_age: Age at start of intervention.
        max_age: Maximum modeled age.
        discount_rate: Annual discount rate for costs and QALYs.

    Returns:
        LifecycleResult with life years, QALYs, costs, and ICER.
    """
    ages = np.arange(start_age, max_age + 1)
    n_years = len(ages)

    mortality_baseline = get_mortality_curve(start_age, max_age)
    quality_weights = get_quality_curve(start_age, max_age)

    # Age-specific weighted RR based on cause-of-death mix
    weighted_rr = np.empty(n_years)
    cvd_fracs = np.empty(n_years)
    cancer_fracs = np.empty(n_years)
    other_fracs = np.empty(n_years)

    for i, age in enumerate(ages):
        cf, canf, of = get_cause_fractions(age)
        cvd_fracs[i] = cf
        cancer_fracs[i] = canf
        other_fracs[i] = of
        weighted_rr[i] = cf * rr_cvd + canf * rr_cancer + of * rr_other

    # Intervention mortality
    mortality_intervention = mortality_baseline * weighted_rr

    # Survival curves
    survival_baseline = np.cumprod(1 - mortality_baseline)
    survival_baseline = np.insert(survival_baseline[:-1], 0, 1.0)

    survival_intervention = np.cumprod(1 - mortality_intervention)
    survival_intervention = np.insert(survival_intervention[:-1], 0, 1.0)

    # Life years gained by age
    ly_gained_by_age = survival_intervention - survival_baseline
    ly_total = float(np.sum(ly_gained_by_age))

    # Decompose into pathway contributions
    cvd_reduction = cvd_fracs * (1 - rr_cvd)
    cancer_reduction = cancer_fracs * (1 - rr_cancer)
    other_reduction = other_fracs * (1 - rr_other)
    total_reduction = cvd_reduction + cancer_reduction + other_reduction

    safe_total = np.where(total_reduction > 0, total_reduction, 1.0)
    cvd_contrib_by_age = cvd_reduction / safe_total
    cancer_contrib_by_age = cancer_reduction / safe_total
    other_contrib_by_age = other_reduction / safe_total

    ly_cvd = float(np.sum(ly_gained_by_age * cvd_contrib_by_age))
    ly_cancer = float(np.sum(ly_gained_by_age * cancer_contrib_by_age))
    ly_other = float(np.sum(ly_gained_by_age * other_contrib_by_age))

    # QALYs (undiscounted)
    qaly_gain_by_age = ly_gained_by_age * quality_weights
    qalys_gained = float(np.sum(qaly_gain_by_age))

    # Discounting
    discount_factors = 1 / (1 + discount_rate) ** np.arange(n_years)
    ly_gained_disc = float(np.sum(ly_gained_by_age * discount_factors))
    qalys_gained_disc = float(np.sum(qaly_gain_by_age * discount_factors))

    # Costs
    annual_costs = annual_cost * survival_intervention
    total_cost_disc = float(np.sum(annual_costs * discount_factors))

    # ICER
    cost_per_qaly = (
        total_cost_disc / qalys_gained_disc if qalys_gained_disc > 0 else float("inf")
    )

    # Overall pathway contributions (weighted by discounted LY)
    ly_cvd_disc = float(np.sum(ly_gained_by_age * cvd_contrib_by_age * discount_factors))
    ly_cancer_disc = float(np.sum(ly_gained_by_age * cancer_contrib_by_age * discount_factors))
    ly_other_disc = float(np.sum(ly_gained_by_age * other_contrib_by_age * discount_factors))

    cvd_contribution = ly_cvd_disc / ly_gained_disc if ly_gained_disc > 0 else 0
    cancer_contribution = ly_cancer_disc / ly_gained_disc if ly_gained_disc > 0 else 0
    other_contribution = ly_other_disc / ly_gained_disc if ly_gained_disc > 0 else 0

    return LifecycleResult(
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
