"""Cause-specific mortality lifecycle outcomes and intervention costs.

The CDC life table supplies annual all-cause death probabilities (qx).
This module converts qx to integrated hazards, partitions each hazard by
age-specific cause fractions, applies cause-specific hazard ratios, and only
then converts the adjusted total hazard back to an annual probability. This
keeps mortality and survival inside their probability domains for every draw.

Annual outcomes and recurring costs use half-cycle occupancy: the mean of
survival at the start and end of each age interval. Accruals are discounted at
the interval midpoint. This avoids awarding a full year of life, quality, or
intervention cost to people who die during that year.

The published single-age table ends at 99. Age 100 is an explicit terminal
open interval with qx=1; the lifecycle never extrapolates beyond it.
"""

from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

import numpy as np

from whatnut.config import (
    get_cause_fractions,
    get_mortality_curve,
    get_quality_curve,
)
from whatnut.reference_case import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    validate_discount_rate,
)

MINIMUM_SUPPORTED_AGE = 20
TERMINAL_AGE = 100
_EFFECT_EPSILON = 1e-12


def _cost_per_positive_qaly(
    total_cost_discounted: float | np.ndarray,
    qalys_gained_discounted: float | np.ndarray,
) -> float | np.ndarray:
    """Compatibility calculation retained outside the lifecycle kernel."""
    warnings.warn(
        "LifecycleResult.cost_per_qaly is deprecated; use the decision module "
        "to summarize expected costs and QALYs across paired draws.",
        DeprecationWarning,
        stacklevel=3,
    )
    costs = np.asarray(total_cost_discounted, dtype=float)
    qalys = np.asarray(qalys_gained_discounted, dtype=float)
    result = np.full(np.broadcast_shapes(costs.shape, qalys.shape), np.inf)
    np.divide(costs, qalys, out=result, where=qalys > _EFFECT_EPSILON)
    if result.ndim == 0:
        return float(result)
    return result


@dataclass(frozen=True)
class LifecycleResult:
    """Outcomes and costs from one cause-specific lifecycle evaluation."""

    # Exact Shapley decomposition of undiscounted life-year change.
    life_years_cvd: float
    life_years_cancer: float
    life_years_other: float

    # Exact Shapley decomposition of the primary discounted-QALY change.
    qalys_gained_discounted_cvd: float
    qalys_gained_discounted_cancer: float
    qalys_gained_discounted_other: float

    life_years_gained: float
    qalys_gained: float
    life_years_gained_discounted: float
    qalys_gained_discounted: float
    total_cost_discounted: float

    # Signed shares of the primary discounted-QALY change. Opposing pathways may
    # be negative and offsetting shares can exceed one; non-null shares sum to
    # one because the Shapley components exactly decompose the net effect.
    cvd_contribution: float
    cancer_contribution: float
    other_contribution: float

    @property
    def cost_per_qaly(self) -> float:
        """Deprecated draw-level ratio; decision analysis owns economics."""
        return float(
            _cost_per_positive_qaly(
                self.total_cost_discounted,
                self.qalys_gained_discounted,
            )
        )


@dataclass(frozen=True)
class LifecycleVectorResult:
    """Vectorized lifecycle outcomes and costs across Monte Carlo draws."""

    # Per-draw exact Shapley components of the primary discounted-QALY change.
    qalys_gained_discounted_cvd: np.ndarray
    qalys_gained_discounted_cancer: np.ndarray
    qalys_gained_discounted_other: np.ndarray

    life_years_gained: np.ndarray
    qalys_gained: np.ndarray
    life_years_gained_discounted: np.ndarray
    qalys_gained_discounted: np.ndarray
    total_cost_discounted: np.ndarray

    @property
    def cost_per_qaly(self) -> np.ndarray:
        """Deprecated draw-level ratio; decision analysis owns economics."""
        result = _cost_per_positive_qaly(
            self.total_cost_discounted,
            self.qalys_gained_discounted,
        )
        assert isinstance(result, np.ndarray)
        return result


@dataclass(frozen=True)
class BaselineOutcomes:
    """Baseline health outcomes under the lifecycle's occupancy convention."""

    life_years: float
    qalys: float
    life_years_discounted: float
    qalys_discounted: float

    @property
    def average_quality_weight(self) -> float:
        """Occupancy-weighted mean quality weight over remaining life."""
        if self.life_years <= 0:
            return 0.0
        return self.qalys / self.life_years


@dataclass(frozen=True)
class _LifecycleCoreResult:
    """Shared arrays from the scalar/vectorized lifecycle kernel."""

    ages: np.ndarray
    baseline_qx: np.ndarray
    cause_fractions: np.ndarray
    hazard_ratios: np.ndarray
    quality_weights: np.ndarray
    qaly_discount_weights: np.ndarray
    baseline_survival: np.ndarray
    intervention_survival: np.ndarray
    baseline_occupancy: np.ndarray
    intervention_occupancy: np.ndarray
    life_years_gained: np.ndarray
    qalys_gained: np.ndarray
    life_years_gained_discounted: np.ndarray
    qalys_gained_discounted: np.ndarray
    total_cost_discounted: np.ndarray


def _validate_age(value: int, *, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(f"{label} must be an integer.")
    value = int(value)
    if not MINIMUM_SUPPORTED_AGE <= value <= TERMINAL_AGE:
        raise ValueError(
            f"{label} must be between {MINIMUM_SUPPORTED_AGE} and {TERMINAL_AGE}."
        )
    return value


def _validate_horizon(start_age: int, max_age: int) -> tuple[int, int]:
    start_age = _validate_age(start_age, label="start_age")
    max_age = _validate_age(max_age, label="max_age")
    if max_age < start_age:
        raise ValueError("max_age must be greater than or equal to start_age.")
    return start_age, max_age


def _validate_annual_cost(annual_cost: float) -> float:
    if isinstance(annual_cost, bool):
        raise ValueError("annual_cost must be a finite nonnegative number.")
    try:
        annual_cost = float(annual_cost)
    except (TypeError, ValueError) as error:
        raise ValueError("annual_cost must be a finite nonnegative number.") from error
    if not math.isfinite(annual_cost) or annual_cost < 0:
        raise ValueError("annual_cost must be a finite nonnegative number.")
    return annual_cost


def _validate_hazard_ratio(values: np.ndarray, *, label: str) -> np.ndarray:
    try:
        raw_values = np.asarray(values)
        if raw_values.dtype.kind == "b":
            raise ValueError(f"{label} must contain finite nonnegative values.")
        values = np.asarray(raw_values, dtype=float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must contain finite nonnegative values.") from error
    if values.ndim != 1 or values.size == 0:
        raise ValueError(f"{label} must be a nonempty one-dimensional array.")
    if np.any(~np.isfinite(values)) or np.any(values < 0):
        raise ValueError(f"{label} must contain finite nonnegative values.")
    return values


def _qx_to_hazard(qx: np.ndarray) -> np.ndarray:
    """Convert annual death probabilities to integrated annual hazards."""
    qx = np.asarray(qx, dtype=float)
    if np.any(~np.isfinite(qx)) or np.any((qx < 0) | (qx > 1)):
        raise ValueError("Mortality probabilities must be finite and in [0, 1].")
    hazards = np.empty_like(qx)
    terminal = qx == 1
    hazards[terminal] = np.inf
    hazards[~terminal] = -np.log1p(-qx[~terminal])
    return hazards


def _hazard_to_qx(hazards: np.ndarray) -> np.ndarray:
    """Convert nonnegative integrated hazards to annual probabilities."""
    hazards = np.asarray(hazards, dtype=float)
    if np.any(np.isnan(hazards)) or np.any(hazards < 0):
        raise ValueError("Integrated hazards must be nonnegative and not NaN.")
    qx = -np.expm1(-hazards)
    if np.any(~np.isfinite(qx)) or np.any((qx < 0) | (qx > 1)):
        raise RuntimeError("Hazard conversion produced an invalid probability.")
    return qx


def _survival_at_cycle_start(qx: np.ndarray) -> np.ndarray:
    """Return survival at the start of each annual cycle."""
    qx = np.asarray(qx, dtype=float)
    if qx.ndim not in (1, 2):
        raise ValueError("Mortality input must be one- or two-dimensional.")
    _qx_to_hazard(qx)  # Domain validation, including NaN and infinity.

    survival = np.ones_like(qx)
    if qx.shape[-1] > 1:
        survival[..., 1:] = np.cumprod(1 - qx[..., :-1], axis=-1)
    if np.any(~np.isfinite(survival)) or np.any((survival < 0) | (survival > 1)):
        raise RuntimeError("Lifecycle produced survival outside [0, 1].")
    if np.any(np.diff(survival, axis=-1) > 1e-15):
        raise RuntimeError("Lifecycle produced an increasing survival curve.")
    return survival


def _cycle_occupancy(survival_at_start: np.ndarray, qx: np.ndarray) -> np.ndarray:
    """Return half-cycle person-time for each annual interval.

    Adult deaths are assumed to occur uniformly within an interval, so
    person-time is the trapezoidal mean of survival at its two boundaries.
    The explicit terminal interval therefore contributes half of the people
    alive at age 100 before forcing survival to zero.
    """
    survival_at_start = np.asarray(survival_at_start, dtype=float)
    qx = np.asarray(qx, dtype=float)
    if survival_at_start.shape != qx.shape:
        raise ValueError("Survival and mortality arrays must have equal shapes.")
    if survival_at_start.ndim not in (1, 2):
        raise ValueError("Survival input must be one- or two-dimensional.")
    _qx_to_hazard(qx)
    if np.any(~np.isfinite(survival_at_start)) or np.any(
        (survival_at_start < 0) | (survival_at_start > 1)
    ):
        raise ValueError("Survival probabilities must be finite and in [0, 1].")

    survival_at_end = survival_at_start * (1 - qx)
    occupancy = 0.5 * (survival_at_start + survival_at_end)
    if np.any(~np.isfinite(occupancy)) or np.any((occupancy < 0) | (occupancy > 1)):
        raise RuntimeError("Lifecycle produced cycle occupancy outside [0, 1].")
    return occupancy


def _mid_cycle_discount_weights(n_cycles: int, rate: float) -> np.ndarray:
    """Return discount weights for accruals spread uniformly within cycles."""
    return 1 / (1 + rate) ** (np.arange(n_cycles, dtype=float) + 0.5)


def _cause_fraction_matrix(ages: np.ndarray) -> np.ndarray:
    fractions = np.array([get_cause_fractions(int(age)) for age in ages], dtype=float)
    if (
        fractions.shape != (len(ages), 3)
        or np.any(~np.isfinite(fractions))
        or np.any(fractions < 0)
        or not np.allclose(fractions.sum(axis=1), 1.0, atol=1e-12)
    ):
        raise ValueError("Cause fractions must be nonnegative and sum to one.")
    return fractions


def _adjust_mortality_on_hazard_scale(
    baseline_qx: np.ndarray,
    cause_fractions: np.ndarray,
    hazard_ratios: np.ndarray,
) -> np.ndarray:
    """Apply cause-specific HRs to hazards and return bounded annual qx."""
    baseline_hazards = _qx_to_hazard(baseline_qx)
    hazard_multipliers = hazard_ratios @ cause_fractions.T
    adjusted_qx = np.empty_like(hazard_multipliers)

    terminal = np.isinf(baseline_hazards)
    finite = ~terminal
    adjusted_hazards = hazard_multipliers[:, finite] * baseline_hazards[finite]
    adjusted_qx[:, finite] = _hazard_to_qx(adjusted_hazards)

    # qx=1 identifies the CDC open interval, not a one-year probability to
    # which an HR can be applied. Both arms terminate in this interval.
    adjusted_qx[:, terminal] = 1.0
    if np.any(~np.isfinite(adjusted_qx)) or np.any(
        (adjusted_qx < 0) | (adjusted_qx > 1)
    ):
        raise RuntimeError("Adjusted mortality fell outside [0, 1].")
    return adjusted_qx


def _run_lifecycle_core(
    rr_cvd: np.ndarray,
    rr_cancer: np.ndarray,
    rr_other: np.ndarray,
    annual_cost: float,
    start_age: int,
    max_age: int,
    qaly_discount_rate: float,
    cost_discount_rate: float,
) -> _LifecycleCoreResult:
    start_age, max_age = _validate_horizon(start_age, max_age)
    annual_cost = _validate_annual_cost(annual_cost)
    qaly_discount_rate = validate_discount_rate(qaly_discount_rate, label="QALY")
    cost_discount_rate = validate_discount_rate(cost_discount_rate, label="cost")

    rr_cvd = _validate_hazard_ratio(rr_cvd, label="rr_cvd")
    rr_cancer = _validate_hazard_ratio(rr_cancer, label="rr_cancer")
    rr_other = _validate_hazard_ratio(rr_other, label="rr_other")
    if not (rr_cvd.shape == rr_cancer.shape == rr_other.shape):
        raise ValueError("Cause-specific hazard-ratio arrays must have equal lengths.")

    ages = np.arange(start_age, max_age + 1)
    baseline_qx = np.asarray(get_mortality_curve(start_age, max_age), dtype=float)
    if max_age == TERMINAL_AGE and baseline_qx[-1] != 1:
        raise ValueError("Age 100 must be the terminal/open interval with qx=1.")
    quality_weights = np.asarray(get_quality_curve(start_age, max_age), dtype=float)
    if np.any(~np.isfinite(quality_weights)) or np.any(
        (quality_weights < 0) | (quality_weights > 1)
    ):
        raise ValueError("Quality weights must be finite and in [0, 1].")

    cause_fractions = _cause_fraction_matrix(ages)
    hazard_ratios = np.column_stack((rr_cvd, rr_cancer, rr_other))
    intervention_qx = _adjust_mortality_on_hazard_scale(
        baseline_qx,
        cause_fractions,
        hazard_ratios,
    )

    baseline_survival = _survival_at_cycle_start(baseline_qx)
    intervention_survival = _survival_at_cycle_start(intervention_qx)
    baseline_occupancy = _cycle_occupancy(baseline_survival, baseline_qx)
    intervention_occupancy = _cycle_occupancy(
        intervention_survival,
        intervention_qx,
    )
    occupancy_difference = intervention_occupancy - baseline_occupancy[None, :]

    n_years = len(ages)
    qaly_discount = _mid_cycle_discount_weights(n_years, qaly_discount_rate)
    cost_discount = _mid_cycle_discount_weights(n_years, cost_discount_rate)
    qaly_gain_by_age = occupancy_difference * quality_weights[None, :]

    life_years_gained = np.sum(occupancy_difference, axis=1)
    qalys_gained = np.sum(qaly_gain_by_age, axis=1)
    life_years_gained_discounted = np.sum(
        occupancy_difference * qaly_discount[None, :], axis=1
    )
    qalys_gained_discounted = np.sum(qaly_gain_by_age * qaly_discount[None, :], axis=1)
    total_cost_discounted = annual_cost * np.sum(
        intervention_occupancy * cost_discount[None, :], axis=1
    )

    outputs = (
        life_years_gained,
        qalys_gained,
        life_years_gained_discounted,
        qalys_gained_discounted,
        total_cost_discounted,
    )
    if any(np.any(~np.isfinite(output)) for output in outputs):
        raise ValueError("Lifecycle outcomes and costs must remain finite.")
    if np.any(total_cost_discounted < 0):
        raise RuntimeError("Lifecycle produced a negative intervention cost.")

    return _LifecycleCoreResult(
        ages=ages,
        baseline_qx=baseline_qx,
        cause_fractions=cause_fractions,
        hazard_ratios=hazard_ratios,
        quality_weights=quality_weights,
        qaly_discount_weights=qaly_discount,
        baseline_survival=baseline_survival,
        intervention_survival=intervention_survival,
        baseline_occupancy=baseline_occupancy,
        intervention_occupancy=intervention_occupancy,
        life_years_gained=life_years_gained,
        qalys_gained=qalys_gained,
        life_years_gained_discounted=life_years_gained_discounted,
        qalys_gained_discounted=qalys_gained_discounted,
        total_cost_discounted=total_cost_discounted,
    )


@dataclass(frozen=True)
class _PathwayShapleyResult:
    """Per-draw exact pathway components for lifecycle health outcomes."""

    life_years: np.ndarray
    qalys_discounted: np.ndarray


def _pathway_shapley_values(core: _LifecycleCoreResult) -> _PathwayShapleyResult:
    """Exactly decompose each draw's LY and discounted-QALY changes."""
    n_pathways = 3
    n_draws = core.hazard_ratios.shape[0]
    outcomes: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    # Evaluate the 2^3 coalitions in vectorized form across all draws. A
    # pathway excluded from a coalition receives the null hazard ratio of one.
    for mask in range(1 << n_pathways):
        coalition_hrs = np.ones_like(core.hazard_ratios)
        for pathway in range(n_pathways):
            if mask & (1 << pathway):
                coalition_hrs[:, pathway] = core.hazard_ratios[:, pathway]
        coalition_qx = _adjust_mortality_on_hazard_scale(
            core.baseline_qx,
            core.cause_fractions,
            coalition_hrs,
        )
        coalition_survival = _survival_at_cycle_start(coalition_qx)
        coalition_occupancy = _cycle_occupancy(
            coalition_survival,
            coalition_qx,
        )
        outcomes[mask] = (
            np.sum(coalition_occupancy, axis=1),
            np.sum(
                coalition_occupancy
                * core.quality_weights[None, :]
                * core.qaly_discount_weights[None, :],
                axis=1,
            ),
        )

    life_years = np.zeros((n_draws, n_pathways))
    qalys_discounted = np.zeros((n_draws, n_pathways))
    factorial = math.factorial
    denominator = factorial(n_pathways)
    for pathway in range(n_pathways):
        bit = 1 << pathway
        for mask in range(1 << n_pathways):
            if mask & bit:
                continue
            coalition_size = mask.bit_count()
            weight = (
                factorial(coalition_size)
                * factorial(n_pathways - coalition_size - 1)
                / denominator
            )
            with_pathway = outcomes[mask | bit]
            without_pathway = outcomes[mask]
            life_years[:, pathway] += weight * (with_pathway[0] - without_pathway[0])
            qalys_discounted[:, pathway] += weight * (
                with_pathway[1] - without_pathway[1]
            )

    if not np.allclose(
        life_years.sum(axis=1),
        core.life_years_gained,
        rtol=0,
        atol=1e-11,
    ):
        raise RuntimeError("Life-year Shapley components did not decompose the effect.")
    if not np.allclose(
        qalys_discounted.sum(axis=1),
        core.qalys_gained_discounted,
        rtol=0,
        atol=1e-11,
    ):
        raise RuntimeError(
            "Discounted-QALY Shapley components did not decompose the effect."
        )

    return _PathwayShapleyResult(
        life_years=life_years,
        qalys_discounted=qalys_discounted,
    )


def _signed_shares(values: np.ndarray, total: float) -> np.ndarray:
    """Return signed Shapley shares of a net effect."""
    if abs(total) <= _EFFECT_EPSILON:
        return np.zeros_like(values)
    shares = values / total
    if np.any(~np.isfinite(shares)) or not np.isclose(shares.sum(), 1.0, atol=1e-10):
        raise RuntimeError("Signed pathway shares did not sum to one.")
    return shares


def calculate_baseline_outcomes(
    *,
    start_age: int = 40,
    max_age: int = TERMINAL_AGE,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
) -> BaselineOutcomes:
    """Calculate baseline life-years and QALYs with half-cycle occupancy.

    This is the public baseline counterpart to :func:`run_lifecycle`. It uses
    the same mortality, quality-weight, terminal-age, half-cycle, and discount
    conventions as the intervention kernel so reporting code does not need to
    reconstruct survival independently.
    """
    start_age, max_age = _validate_horizon(start_age, max_age)
    qaly_discount_rate = validate_discount_rate(qaly_discount_rate, label="QALY")

    mortality = np.asarray(get_mortality_curve(start_age, max_age), dtype=float)
    if max_age == TERMINAL_AGE and mortality[-1] != 1:
        raise ValueError("Age 100 must be the terminal/open interval with qx=1.")
    quality_weights = np.asarray(get_quality_curve(start_age, max_age), dtype=float)
    if np.any(~np.isfinite(quality_weights)) or np.any(
        (quality_weights < 0) | (quality_weights > 1)
    ):
        raise ValueError("Quality weights must be finite and in [0, 1].")

    survival = _survival_at_cycle_start(mortality)
    occupancy = _cycle_occupancy(survival, mortality)
    discount = _mid_cycle_discount_weights(len(mortality), qaly_discount_rate)
    life_years = float(np.sum(occupancy))
    qalys = float(np.sum(occupancy * quality_weights))
    life_years_discounted = float(np.sum(occupancy * discount))
    qalys_discounted = float(np.sum(occupancy * quality_weights * discount))
    outputs = (life_years, qalys, life_years_discounted, qalys_discounted)
    if any(not math.isfinite(output) or output < 0 for output in outputs):
        raise RuntimeError(
            "Baseline lifecycle outcomes must be finite and nonnegative."
        )

    return BaselineOutcomes(
        life_years=life_years,
        qalys=qalys,
        life_years_discounted=life_years_discounted,
        qalys_discounted=qalys_discounted,
    )


def run_lifecycle(
    rr_cvd: float,
    rr_cancer: float,
    rr_other: float,
    annual_cost: float,
    start_age: int = 40,
    max_age: int = TERMINAL_AGE,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
) -> LifecycleResult:
    """Run the lifecycle model for one set of cause-specific hazard ratios.

    ``rr_*`` names are retained for API compatibility, but the inputs are
    interpreted as hazard ratios and applied on the cause-specific hazard
    scale. Supported ages are 20-100 because the quality and cause-fraction
    inputs begin at age 20; age 100 is terminal.
    """
    rr_arrays = tuple(np.asarray([rr]) for rr in (rr_cvd, rr_cancer, rr_other))
    core = _run_lifecycle_core(
        rr_cvd=rr_arrays[0],
        rr_cancer=rr_arrays[1],
        rr_other=rr_arrays[2],
        annual_cost=annual_cost,
        start_age=start_age,
        max_age=max_age,
        qaly_discount_rate=qaly_discount_rate,
        cost_discount_rate=cost_discount_rate,
    )
    pathways = _pathway_shapley_values(core)
    shares = _signed_shares(
        pathways.qalys_discounted[0],
        float(core.qalys_gained_discounted[0]),
    )

    return LifecycleResult(
        life_years_cvd=float(pathways.life_years[0, 0]),
        life_years_cancer=float(pathways.life_years[0, 1]),
        life_years_other=float(pathways.life_years[0, 2]),
        qalys_gained_discounted_cvd=float(pathways.qalys_discounted[0, 0]),
        qalys_gained_discounted_cancer=float(pathways.qalys_discounted[0, 1]),
        qalys_gained_discounted_other=float(pathways.qalys_discounted[0, 2]),
        life_years_gained=float(core.life_years_gained[0]),
        qalys_gained=float(core.qalys_gained[0]),
        life_years_gained_discounted=float(core.life_years_gained_discounted[0]),
        qalys_gained_discounted=float(core.qalys_gained_discounted[0]),
        total_cost_discounted=float(core.total_cost_discounted[0]),
        cvd_contribution=float(shares[0]),
        cancer_contribution=float(shares[1]),
        other_contribution=float(shares[2]),
    )


def run_lifecycle_vectorized(
    rr_cvd: np.ndarray,
    rr_cancer: np.ndarray,
    rr_other: np.ndarray,
    annual_cost: float,
    start_age: int = 40,
    max_age: int = TERMINAL_AGE,
    qaly_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
) -> LifecycleVectorResult:
    """Run the shared lifecycle kernel across paired Monte Carlo draws."""
    core = _run_lifecycle_core(
        rr_cvd=rr_cvd,
        rr_cancer=rr_cancer,
        rr_other=rr_other,
        annual_cost=annual_cost,
        start_age=start_age,
        max_age=max_age,
        qaly_discount_rate=qaly_discount_rate,
        cost_discount_rate=cost_discount_rate,
    )
    pathways = _pathway_shapley_values(core)
    return LifecycleVectorResult(
        qalys_gained_discounted_cvd=pathways.qalys_discounted[:, 0],
        qalys_gained_discounted_cancer=pathways.qalys_discounted[:, 1],
        qalys_gained_discounted_other=pathways.qalys_discounted[:, 2],
        life_years_gained=core.life_years_gained,
        qalys_gained=core.qalys_gained,
        life_years_gained_discounted=core.life_years_gained_discounted,
        qalys_gained_discounted=core.qalys_gained_discounted,
        total_cost_discounted=core.total_cost_discounted,
    )
