"""Decision context and Monte Carlo cost-effectiveness summaries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray

DEFAULT_WILLINGNESS_TO_PAY = 50_000.0
EXPECTED_NMB_DECIMALS = 6


@dataclass(frozen=True)
class DecisionContext:
    """Describe the intervention comparison represented by model outputs."""

    intervention: str
    comparator: str
    cost_basis: str
    not_modeled: tuple[str, ...]
    outcome: str
    ranking_metric: str
    probability_metric: str

    def to_dict(self) -> dict[str, object]:
        """Return the context as a serializable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class MutuallyExclusiveDecision:
    """All-option decision summary computed from paired NMB draws."""

    expected_nmb: dict[str, float]
    probability_optimal: dict[str, float]
    ranking: tuple[str, ...]
    recommended_option_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        """Return a stable JSON-serializable representation."""
        data = asdict(self)
        # Canonicalize derived floating-point summaries at the artifact
        # boundary so supported NumPy/SciPy versions do not differ at the
        # 12th decimal place.
        data["expected_nmb"] = {
            option_id: round(value, EXPECTED_NMB_DECIMALS)
            for option_id, value in self.expected_nmb.items()
        }
        data["probability_optimal"] = {
            option_id: round(value, 9)
            for option_id, value in self.probability_optimal.items()
        }
        return data


SINGLE_NUT_ADDITION_DECISION = DecisionContext(
    intervention="Add one 28 g serving of one nut per day.",
    comparator="No modeled daily-nut intervention.",
    cost_basis="Gross retail cost of the added 28 g daily serving.",
    not_modeled=(
        "Current diet or routine.",
        "Food displaced by the added nut.",
        "Dietary substitution effects.",
        "Direct morbidity effects or harms.",
        "Adherence decay or finite intervention persistence.",
        "Personalized transport to the user's baseline risk.",
        "Stacking or interactions among mixed nuts.",
    ),
    outcome="Mortality-derived quality-adjusted life-years (QALYs).",
    ranking_metric=(
        "Maximum expected net monetary benefit at the declared willingness-to-pay, "
        "including the no-intervention comparator."
    ),
    probability_metric=(
        "Draw-wise probability of maximum net monetary benefit across mutually "
        "exclusive options, including the no-intervention comparator."
    ),
)


def _as_finite_draws(values: ArrayLike, *, label: str) -> NDArray[np.float64]:
    """Convert model draws to a finite one-dimensional array."""
    try:
        array = np.asarray(values)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a numeric one-dimensional array.") from error

    if array.ndim != 1:
        raise ValueError(f"{label} must be one-dimensional.")
    if array.size == 0:
        raise ValueError(f"{label} must be nonempty.")
    if np.iscomplexobj(array):
        raise ValueError(f"{label} must contain real numeric values.")

    try:
        array = array.astype(np.float64, copy=False)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must contain numeric values.") from error

    if not np.all(np.isfinite(array)):
        raise ValueError(f"{label} must contain only finite values.")
    return array


def _validated_inputs(
    qalys: ArrayLike,
    costs: ArrayLike,
    willingness_to_pay: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64], float]:
    """Validate paired model draws and a willingness-to-pay threshold."""
    qaly_draws = _as_finite_draws(qalys, label="qalys")
    cost_draws = _as_finite_draws(costs, label="costs")
    if qaly_draws.shape != cost_draws.shape:
        raise ValueError("qalys and costs must have the same shape.")

    wtp = validate_willingness_to_pay(willingness_to_pay)

    return qaly_draws, cost_draws, wtp


def validate_willingness_to_pay(value: float) -> float:
    """Validate an illustrative QALY valuation used for NMB decisions."""
    if isinstance(value, bool):
        raise ValueError("willingness_to_pay must be a positive finite value.")
    try:
        wtp = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(
            "willingness_to_pay must be a positive finite value."
        ) from error
    if not np.isfinite(wtp) or wtp <= 0:
        raise ValueError("willingness_to_pay must be a positive finite value.")
    return wtp


def summarize_cost_effectiveness(
    qalys: ArrayLike,
    costs: ArrayLike,
    willingness_to_pay: float,
) -> dict[str, float]:
    """Summarize paired incremental QALY and cost model draws.

    Net monetary benefit is calculated draw by draw as
    ``willingness_to_pay * qalys - costs``. The expected cost per QALY is the
    ratio of draw means and is infinite when expected incremental QALYs
    are zero or negative.
    """
    qaly_draws, cost_draws, wtp = _validated_inputs(
        qalys,
        costs,
        willingness_to_pay,
    )

    expected_qaly = float(np.mean(qaly_draws))
    expected_cost = float(np.mean(cost_draws))
    net_monetary_benefit = wtp * qaly_draws - cost_draws

    return {
        "expected_qaly": expected_qaly,
        "expected_cost": expected_cost,
        "expected_cost_per_qaly": (
            expected_cost / expected_qaly if expected_qaly > 0 else float("inf")
        ),
        "p_benefit": float(np.mean(qaly_draws > 0)),
        "p_harm": float(np.mean(qaly_draws < 0)),
        "expected_upside": float(np.mean(np.maximum(qaly_draws, 0))),
        "expected_downside": float(np.mean(np.minimum(qaly_draws, 0))),
        "expected_net_monetary_benefit": float(np.mean(net_monetary_benefit)),
        "p_nmb_positive": float(np.mean(net_monetary_benefit > 0)),
    }


def summarize_mutually_exclusive_nmb(
    nmb_draws_by_option: Mapping[str, ArrayLike],
) -> MutuallyExclusiveDecision:
    """Summarize paired NMB draws across mutually exclusive options.

    The common draw axis is required. Probability of optimality is split
    equally across exact ties, so results do not depend on input ordering.
    """
    if not nmb_draws_by_option:
        raise ValueError("nmb_draws_by_option must be nonempty.")

    option_ids = tuple(nmb_draws_by_option)
    draws = {
        option_id: _as_finite_draws(values, label=f"NMB draws for {option_id}")
        for option_id, values in nmb_draws_by_option.items()
    }
    shapes = {array.shape for array in draws.values()}
    if len(shapes) != 1:
        raise ValueError("all option NMB draws must have the same shape.")

    matrix = np.column_stack([draws[option_id] for option_id in option_ids])
    draw_max = np.max(matrix, axis=1, keepdims=True)
    is_optimal = matrix == draw_max
    optimal_share = is_optimal / np.sum(is_optimal, axis=1, keepdims=True)

    # One-millionth of a dollar is the canonical economic resolution used for
    # both serialization and tie decisions. This preserves sub-cent signs
    # while preventing platform-scale floating noise from changing a rank.
    expected_nmb = {
        option_id: round(
            float(np.mean(draws[option_id])),
            EXPECTED_NMB_DECIMALS,
        )
        for option_id in option_ids
    }
    probability_optimal = {
        option_id: float(np.mean(optimal_share[:, index]))
        for index, option_id in enumerate(option_ids)
    }
    ranking = tuple(sorted(option_ids, key=lambda key: (-expected_nmb[key], key)))
    best_expected_nmb = max(expected_nmb.values())
    recommended = tuple(
        sorted(
            option_id
            for option_id, value in expected_nmb.items()
            if value == best_expected_nmb
        )
    )

    return MutuallyExclusiveDecision(
        expected_nmb=expected_nmb,
        probability_optimal=probability_optimal,
        ranking=ranking,
        recommended_option_ids=recommended,
    )


__all__ = [
    "DecisionContext",
    "MutuallyExclusiveDecision",
    "DEFAULT_WILLINGNESS_TO_PAY",
    "EXPECTED_NMB_DECIMALS",
    "SINGLE_NUT_ADDITION_DECISION",
    "summarize_cost_effectiveness",
    "summarize_mutually_exclusive_nmb",
    "validate_willingness_to_pay",
]
