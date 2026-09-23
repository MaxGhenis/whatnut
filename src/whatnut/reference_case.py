"""Reference-case assumptions shared by the What Nut analysis.

The model reports mortality-derived QALYs for cost comparison rather than a
full cost-utility analysis. The main paper keeps health gains undiscounted,
while these values provide the institutional 3%/3% reference-case sensitivity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ReferenceCase:
    """Cost-effectiveness reference-case metadata."""

    id: str
    name: str
    perspective: str
    health_discount_rate: float
    cost_discount_rate: float
    utility_instrument: str
    reporting_standard: str
    source_urls: tuple[str, ...]
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
    utility_instrument="EQ-5D population norms",
    reporting_standard="CHEERS 2022",
    source_urls=(
        "https://jamanetwork.com/journals/jama/fullarticle/2552214",
        "https://www.bmj.com/content/376/bmj-2021-067975",
    ),
    notes=(
        "Discount both health effects and costs at 3% in the reference case.",
        "What Nut reports mortality-derived QALYs, not a full formal CUA.",
    ),
)

DEFAULT_REFERENCE_CASE = US_SECOND_PANEL_REFERENCE_CASE
DEFAULT_QALY_DISCOUNT_RATE = 0.0
DEFAULT_COST_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.cost_discount_rate
DEFAULT_REFERENCE_QALY_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.health_discount_rate
DEFAULT_REFERENCE_COST_DISCOUNT_RATE = DEFAULT_REFERENCE_CASE.cost_discount_rate


def validate_discount_rate(rate: float, *, label: str) -> float:
    """Validate a discount rate for supported sensitivity analyses."""
    rate = float(rate)
    if rate < 0:
        raise ValueError(f"{label} discount rate must be nonnegative.")
    if rate > 0.10:
        raise ValueError(
            f"{label} discount rate above 10% is outside supported sensitivity bounds."
        )
    return rate


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
