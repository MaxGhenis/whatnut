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


@dataclass
class LifecycleVectorResult:
    """Vectorized lifecycle output across Monte Carlo samples.

    Each field is a 1-D array of length n_samples.
    """

    life_years_gained: np.ndarray
    qalys_gained: np.ndarray
    life_years_gained_discounted: np.ndarray
    qalys_gained_discounted: np.ndarray
    total_cost_discounted: np.ndarray
    cost_per_qaly: np.ndarray


def run_lifecycle(
    rr_cvd: float,
    rr_cancer: float,
    rr_other: float,
    annual_cost: float,
    start_age: int = 40,
    max_age: int = 110,
    qaly_discount_rate: float = 0.0,
    cost_discount_rate: float = 0.03,
) -> LifecycleResult:
    """Run pathway-specific lifecycle model for a single set of RRs.

    Args:
        rr_cvd: Relative risk for CVD mortality (already confounding-adjusted).
        rr_cancer: Relative risk for cancer mortality.
        rr_other: Relative risk for other-cause mortality.
        annual_cost: Annual cost of intervention in USD.
        start_age: Age at start of intervention.
        max_age: Maximum modeled age.
        qaly_discount_rate: Annual discount rate for life years and QALYs.
        cost_discount_rate: Annual discount rate for costs.

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
        cvd_frac, cancer_frac, other_frac = get_cause_fractions(age)
        cvd_fracs[i] = cvd_frac
        cancer_fracs[i] = cancer_frac
        other_fracs[i] = other_frac
        weighted_rr[i] = cvd_frac * rr_cvd + cancer_frac * rr_cancer + other_frac * rr_other

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
    qaly_discount_factors = 1 / (1 + qaly_discount_rate) ** np.arange(n_years)
    ly_gained_disc = float(np.sum(ly_gained_by_age * qaly_discount_factors))
    qalys_gained_disc = float(np.sum(qaly_gain_by_age * qaly_discount_factors))

    # Costs
    annual_costs = annual_cost * survival_intervention
    cost_discount_factors = 1 / (1 + cost_discount_rate) ** np.arange(n_years)
    total_cost_disc = float(np.sum(annual_costs * cost_discount_factors))

    # ICER. Treat QALYs within float-noise of zero as zero so a neutral
    # scenario (no benefit, RR=1.0) returns +inf rather than a huge but
    # finite value driven by sub-epsilon drift in the survival integration.
    cost_per_qaly = (
        total_cost_disc / qalys_gained_disc
        if qalys_gained_disc > 1e-12
        else float("inf")
    )

    # Overall pathway contributions (weighted by discounted LY)
    ly_cvd_disc = float(np.sum(ly_gained_by_age * cvd_contrib_by_age * qaly_discount_factors))
    ly_cancer_disc = float(np.sum(ly_gained_by_age * cancer_contrib_by_age * qaly_discount_factors))
    ly_other_disc = float(np.sum(ly_gained_by_age * other_contrib_by_age * qaly_discount_factors))

    cvd_contribution = ly_cvd_disc / ly_gained_disc if ly_gained_disc > 0 else 0
    cancer_contribution = ly_cancer_disc / ly_gained_disc if ly_gained_disc > 0 else 0
    other_contribution = ly_other_disc / ly_gained_disc if ly_gained_disc > 0 else 0
    # Clamp pathway contributions to [0, 1] to suppress sampling-noise
    # artifacts near null RRs (e.g., cashew's cancer contribution at -0.00
    # or CVD at 1.01 when cancer_RR ≈ 1.0001). The ratios remain exact
    # algebraically; this clamp only affects reported round numbers.
    cvd_contribution = float(np.clip(cvd_contribution, 0.0, 1.0))
    cancer_contribution = float(np.clip(cancer_contribution, 0.0, 1.0))
    other_contribution = float(np.clip(other_contribution, 0.0, 1.0))

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


def run_lifecycle_vectorized(
    rr_cvd: np.ndarray,
    rr_cancer: np.ndarray,
    rr_other: np.ndarray,
    annual_cost: float,
    start_age: int = 40,
    max_age: int = 110,
    qaly_discount_rate: float = 0.0,
    cost_discount_rate: float = 0.03,
) -> LifecycleVectorResult:
    """Vectorized lifecycle over Monte Carlo samples.

    All RR inputs are 1-D arrays of shape (n_samples,). Output arrays have
    the same length. This replaces the per-sample Python loop in pipeline.
    """
    rr_cvd = np.asarray(rr_cvd)
    rr_cancer = np.asarray(rr_cancer)
    rr_other = np.asarray(rr_other)

    ages = np.arange(start_age, max_age + 1)
    n_years = len(ages)

    mortality_baseline = get_mortality_curve(start_age, max_age)
    quality_weights = get_quality_curve(start_age, max_age)

    cvd_fracs = np.empty(n_years)
    cancer_fracs = np.empty(n_years)
    other_fracs = np.empty(n_years)
    for i, age in enumerate(ages):
        cvd_fracs[i], cancer_fracs[i], other_fracs[i] = get_cause_fractions(age)

    # weighted_rr: (n_samples, n_years)
    weighted_rr = (
        cvd_fracs[None, :] * rr_cvd[:, None]
        + cancer_fracs[None, :] * rr_cancer[:, None]
        + other_fracs[None, :] * rr_other[:, None]
    )
    mortality_intervention = mortality_baseline[None, :] * weighted_rr

    survival_baseline = np.cumprod(1 - mortality_baseline)
    survival_baseline = np.insert(survival_baseline[:-1], 0, 1.0)

    survival_intervention = np.cumprod(1 - mortality_intervention, axis=1)
    survival_intervention = np.concatenate(
        [np.ones((mortality_intervention.shape[0], 1)), survival_intervention[:, :-1]],
        axis=1,
    )

    ly_gained_by_age = survival_intervention - survival_baseline[None, :]
    ly_total = np.sum(ly_gained_by_age, axis=1)

    qaly_gain_by_age = ly_gained_by_age * quality_weights[None, :]
    qalys_total = np.sum(qaly_gain_by_age, axis=1)

    qaly_discount = (1 / (1 + qaly_discount_rate) ** np.arange(n_years))
    cost_discount = (1 / (1 + cost_discount_rate) ** np.arange(n_years))

    ly_disc = np.sum(ly_gained_by_age * qaly_discount[None, :], axis=1)
    qalys_disc = np.sum(qaly_gain_by_age * qaly_discount[None, :], axis=1)

    annual_costs = annual_cost * survival_intervention
    total_cost_disc = np.sum(annual_costs * cost_discount[None, :], axis=1)

    qalys_positive = qalys_disc > 1e-12
    cost_per_qaly = np.where(
        qalys_positive, total_cost_disc / np.where(qalys_positive, qalys_disc, 1.0), np.inf
    )

    return LifecycleVectorResult(
        life_years_gained=ly_total,
        qalys_gained=qalys_total,
        life_years_gained_discounted=ly_disc,
        qalys_gained_discounted=qalys_disc,
        total_cost_discounted=total_cost_disc,
        cost_per_qaly=cost_per_qaly,
    )
