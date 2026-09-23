"""Tests for reference-case assumptions."""

import pytest

from whatnut.reference_case import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    DEFAULT_REFERENCE_CASE,
    DEFAULT_REFERENCE_COST_DISCOUNT_RATE,
    DEFAULT_REFERENCE_QALY_DISCOUNT_RATE,
    discounted_years,
    validate_discount_rate,
)


def test_main_discount_defaults_keep_health_undiscounted():
    assert DEFAULT_QALY_DISCOUNT_RATE == pytest.approx(0.0)
    assert DEFAULT_COST_DISCOUNT_RATE == pytest.approx(0.03)


def test_default_reference_case_uses_second_panel_style_discounting():
    assert DEFAULT_REFERENCE_CASE.health_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.cost_discount_rate == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_CASE.reporting_standard == "CHEERS 2022"
    assert DEFAULT_REFERENCE_QALY_DISCOUNT_RATE == pytest.approx(0.03)
    assert DEFAULT_REFERENCE_COST_DISCOUNT_RATE == pytest.approx(0.03)


def test_discounted_years_handles_fractional_durations():
    assert discounted_years(0, 0.03) == 0
    assert discounted_years(1, 0.03) == pytest.approx(1.0)
    assert discounted_years(2.5, 0.03) == pytest.approx(
        1 + 1 / 1.03 + 0.5 / 1.03**2
    )


def test_validate_discount_rate_rejects_out_of_scope_values():
    with pytest.raises(ValueError, match="nonnegative"):
        validate_discount_rate(-0.01, label="QALY")
    with pytest.raises(ValueError, match="above 10%"):
        validate_discount_rate(0.11, label="QALY")
