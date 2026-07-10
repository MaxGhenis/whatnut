"""Reference-case assumptions shared by the What Nut analysis.

The model reports mortality-derived QALYs for cost comparison rather than a
full cost-utility analysis. The US Second Panel-style 3%/3% convention is the
primary case; undiscounted health effects are retained as a named sensitivity.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace


@dataclass(frozen=True)
class ReferenceCase:
    """Cost-effectiveness reference-case metadata."""

    id: str
    name: str
    perspective: str
    health_discount_rate: float
    cost_discount_rate: float
    utility_preference_order: tuple[str, ...]
    reporting_standard: str
    source_urls: tuple[str, ...]
    formal_reference_case: bool
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serializable representation."""
        return asdict(self)


US_SECOND_PANEL_REFERENCE_CASE = ReferenceCase(
    id="us_second_panel_healthcare_sector_3pct",
    name="US Second Panel health care sector reference case",
    perspective="health_care_sector",
    health_discount_rate=0.03,
    cost_discount_rate=0.03,
    utility_preference_order=(
        "eq_5d",
        "sf_6d",
        "hui",
        "mapping",
        "gbd_disability_weight",
        "expert_judgment",
        "personal_utility",
    ),
    reporting_standard="CHEERS 2022",
    source_urls=(
        "https://jamanetwork.com/journals/jama/fullarticle/2552214",
        "https://www.bmj.com/content/376/bmj-2021-067975",
    ),
    formal_reference_case=True,
    notes=(
        "Discount both health effects and costs at 3% in the primary case.",
        "What Nut uses EQ-5D population norms.",
        "What Nut reports mortality-derived QALYs, not a full formal CUA.",
    ),
)

WHATNUT_CONSUMER_REFERENCE_CASE = ReferenceCase(
    id="whatnut_consumer_3pct",
    name="What Nut consumer 3%/3% reference case",
    perspective="consumer_out_of_pocket",
    health_discount_rate=US_SECOND_PANEL_REFERENCE_CASE.health_discount_rate,
    cost_discount_rate=US_SECOND_PANEL_REFERENCE_CASE.cost_discount_rate,
    utility_preference_order=US_SECOND_PANEL_REFERENCE_CASE.utility_preference_order,
    reporting_standard="CHEERS 2022",
    source_urls=US_SECOND_PANEL_REFERENCE_CASE.source_urls,
    formal_reference_case=False,
    notes=(
        "Uses US Second Panel-style 3% health and cost discounting.",
        "Uses EQ-5D population norms for mortality-derived QALYs.",
        "Includes consumer retail nut costs, not a health-care-sector cost inventory.",
        "What Nut reports mortality-derived QALYs, not a full formal CUA.",
    ),
)

DEFAULT_REFERENCE_CASE = WHATNUT_CONSUMER_REFERENCE_CASE
DEFAULT_QALY_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.health_discount_rate
DEFAULT_COST_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.cost_discount_rate
UNDISCOUNTED_QALY_DISCOUNT_RATE = 0.0
UNDISCOUNTED_COST_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.cost_discount_rate


def validate_discount_rate(rate: float, *, label: str) -> float:
    """Validate a discount rate for supported sensitivity analyses."""
    try:
        rate = float(rate)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} discount rate must be a finite number.") from error
    if not math.isfinite(rate):
        raise ValueError(f"{label} discount rate must be a finite number.")
    if rate < 0:
        raise ValueError(f"{label} discount rate must be nonnegative.")
    if rate > 0.10:
        raise ValueError(
            f"{label} discount rate above 10% is outside supported sensitivity bounds."
        )
    return rate


def consumer_reference_case(
    health_discount_rate: float = DEFAULT_QALY_DISCOUNT_RATE,
    cost_discount_rate: float = DEFAULT_COST_DISCOUNT_RATE,
) -> ReferenceCase:
    """Return reference-case metadata matching an analysis run's rates."""
    health_rate = validate_discount_rate(health_discount_rate, label="health")
    cost_rate = validate_discount_rate(cost_discount_rate, label="cost")
    if (
        health_rate == DEFAULT_REFERENCE_CASE.health_discount_rate
        and cost_rate == DEFAULT_REFERENCE_CASE.cost_discount_rate
    ):
        return DEFAULT_REFERENCE_CASE

    health_pct = health_rate * 100
    cost_pct = cost_rate * 100
    return replace(
        DEFAULT_REFERENCE_CASE,
        id=(f"whatnut_consumer_custom_health_{health_pct:g}pct_cost_{cost_pct:g}pct"),
        name=(
            "What Nut consumer custom reference case "
            f"({health_pct:g}% health/{cost_pct:g}% cost)"
        ),
        health_discount_rate=health_rate,
        cost_discount_rate=cost_rate,
        notes=(
            f"Discounts health effects at {health_pct:g}% and costs at "
            f"{cost_pct:g}% for this analysis run.",
            *DEFAULT_REFERENCE_CASE.notes[1:],
        ),
    )


def discounted_years(duration_years: float, discount_rate: float) -> float:
    """Present-value years for a possibly fractional duration."""
    duration_years = float(duration_years)
    if duration_years <= 0:
        return 0.0
    discount_rate = validate_discount_rate(discount_rate, label="duration")
    full_years = int(duration_years)
    total = sum(1 / (1 + discount_rate) ** year for year in range(full_years))
    remainder = duration_years - full_years
    if remainder:
        total += remainder / (1 + discount_rate) ** full_years
    return total
