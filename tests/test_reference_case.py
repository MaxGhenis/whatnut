"""Tests for reference-case assumptions."""

import pytest

from whatnut.reference_case import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    DEFAULT_REFERENCE_CASE,
    UNDISCOUNTED_COST_DISCOUNT_RATE,
    UNDISCOUNTED_QALY_DISCOUNT_RATE,
    US_SECOND_PANEL_REFERENCE_CASE,
    WHATNUT_CONSUMER_REFERENCE_CASE,
    consumer_reference_case,
    discounted_years,
    validate_discount_rate,
)


def test_primary_defaults_use_reference_case_discounting():
    assert DEFAULT_QALY_DISCOUNT_RATE == pytest.approx(0.03)
    assert DEFAULT_COST_DISCOUNT_RATE == pytest.approx(0.03)


def test_default_reference_case_uses_second_panel_style_discounting():
    assert DEFAULT_REFERENCE_CASE.health_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.cost_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.reporting_standard == "CHEERS 2022"
    assert DEFAULT_REFERENCE_CASE.utility_preference_order[0] == "eq_5d"
    assert DEFAULT_REFERENCE_CASE is WHATNUT_CONSUMER_REFERENCE_CASE
    assert DEFAULT_REFERENCE_CASE.perspective == "consumer_out_of_pocket"
    assert DEFAULT_REFERENCE_CASE.formal_reference_case is False
    assert US_SECOND_PANEL_REFERENCE_CASE.perspective == "health_care_sector"
    assert US_SECOND_PANEL_REFERENCE_CASE.formal_reference_case is True


def test_undiscounted_health_sensitivity_keeps_costs_at_three_percent():
    assert UNDISCOUNTED_QALY_DISCOUNT_RATE == pytest.approx(0.0)
    assert UNDISCOUNTED_COST_DISCOUNT_RATE == pytest.approx(0.03)


def test_discounted_years_handles_fractional_durations():
    assert discounted_years(0, 0.03) == 0
    assert discounted_years(1, 0.03) == pytest.approx(1.0)
    assert discounted_years(2.5, 0.03) == pytest.approx(1 + 1 / 1.03 + 0.5 / 1.03**2)


def test_validate_discount_rate_rejects_out_of_scope_values():
    with pytest.raises(ValueError, match="nonnegative"):
        validate_discount_rate(-0.01, label="QALY")
    with pytest.raises(ValueError, match="above 10%"):
        validate_discount_rate(0.11, label="QALY")


@pytest.mark.parametrize(
    "value", [float("nan"), float("inf"), -float("inf"), None, "x"]
)
def test_validate_discount_rate_rejects_nonfinite_or_nonnumeric_values(value):
    with pytest.raises(ValueError, match="finite number"):
        validate_discount_rate(value, label="QALY")


def test_custom_consumer_reference_case_matches_requested_rates():
    case = consumer_reference_case(0.02, 0.05)

    assert case.health_discount_rate == pytest.approx(0.02)
    assert case.cost_discount_rate == pytest.approx(0.05)
    assert "custom" in case.id
    assert consumer_reference_case(0.03, 0.03) is DEFAULT_REFERENCE_CASE
