"""Tests for the pathway-specific lifecycle cost-effectiveness analysis.

Covers run_lifecycle with deterministic RRs, directional checks on
life years gained, pathway contributions, ICER, and discount rate effects.
"""

import numpy as np
import pytest

from whatnut.lifecycle import LifecycleResult, run_lifecycle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def protective_result() -> LifecycleResult:
    """Lifecycle result with all RRs < 1 (protective)."""
    return run_lifecycle(
        rr_cvd=0.80,
        rr_cancer=0.95,
        rr_other=0.90,
        annual_cost=100.0,
        start_age=40,
        qaly_discount_rate=0.03,
        cost_discount_rate=0.03,
    )


@pytest.fixture
def neutral_result() -> LifecycleResult:
    """Lifecycle result with all RRs = 1 (no effect)."""
    return run_lifecycle(
        rr_cvd=1.0,
        rr_cancer=1.0,
        rr_other=1.0,
        annual_cost=100.0,
        start_age=40,
        qaly_discount_rate=0.03,
        cost_discount_rate=0.03,
    )


# ---------------------------------------------------------------------------
# Basic output structure
# ---------------------------------------------------------------------------


class TestLifecycleOutput:
    """run_lifecycle should return a LifecycleResult with all fields."""

    def test_returns_lifecycle_result(self, protective_result):
        assert isinstance(protective_result, LifecycleResult)

    def test_all_fields_present(self, protective_result):
        fields = [
            "life_years_cvd",
            "life_years_cancer",
            "life_years_other",
            "life_years_gained",
            "qalys_gained",
            "life_years_gained_discounted",
            "qalys_gained_discounted",
            "total_cost_discounted",
            "cost_per_qaly",
            "cvd_contribution",
            "cancer_contribution",
            "other_contribution",
        ]
        for field in fields:
            assert hasattr(protective_result, field), f"Missing field: {field}"


# ---------------------------------------------------------------------------
# Deterministic RR behavior
# ---------------------------------------------------------------------------


class TestDeterministicRR:
    """Lifecycle with fixed (deterministic) RRs should have predictable behavior."""

    def test_life_years_positive_when_rrs_below_one(self, protective_result):
        """RRs < 1 reduce mortality, so life years gained should be positive."""
        assert protective_result.life_years_gained > 0

    def test_qalys_positive_when_rrs_below_one(self, protective_result):
        assert protective_result.qalys_gained > 0
        assert protective_result.qalys_gained_discounted > 0

    def test_neutral_rrs_give_zero_benefit(self, neutral_result):
        """RRs = 1 means no mortality change, so life years gained should be ~0."""
        assert neutral_result.life_years_gained == pytest.approx(0.0, abs=1e-10)
        assert neutral_result.qalys_gained == pytest.approx(0.0, abs=1e-10)

    def test_harmful_rrs_give_negative_benefit(self):
        """RRs > 1 increase mortality, so life years gained should be negative."""
        result = run_lifecycle(
            rr_cvd=1.10,
            rr_cancer=1.05,
            rr_other=1.08,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )
        assert result.life_years_gained < 0

    def test_stronger_protection_gives_more_benefit(self):
        """Lower RRs should give more life years gained."""
        strong = run_lifecycle(
            rr_cvd=0.70, rr_cancer=0.85, rr_other=0.80,
            annual_cost=100.0, start_age=40,
        )
        weak = run_lifecycle(
            rr_cvd=0.95, rr_cancer=0.98, rr_other=0.97,
            annual_cost=100.0, start_age=40,
        )
        assert strong.life_years_gained > weak.life_years_gained


# ---------------------------------------------------------------------------
# Pathway contributions
# ---------------------------------------------------------------------------


class TestPathwayContributions:
    """Pathway contributions should sum to ~1 and reflect relative RR effects."""

    def test_contributions_sum_to_approximately_one(self, protective_result):
        total = (
            protective_result.cvd_contribution
            + protective_result.cancer_contribution
            + protective_result.other_contribution
        )
        assert total == pytest.approx(1.0, abs=0.05)

    def test_all_contributions_non_negative(self, protective_result):
        assert protective_result.cvd_contribution >= 0
        assert protective_result.cancer_contribution >= 0
        assert protective_result.other_contribution >= 0

    def test_cvd_dominant_when_cvd_rr_lowest(self):
        """When CVD has the strongest protection, CVD contribution should be largest."""
        result = run_lifecycle(
            rr_cvd=0.70,
            rr_cancer=0.99,
            rr_other=0.99,
            annual_cost=100.0,
            start_age=60,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )
        assert result.cvd_contribution > result.cancer_contribution
        assert result.cvd_contribution > result.other_contribution

    def test_pathway_life_years_sum_to_total(self, protective_result):
        """By-pathway life years should sum to approximately the total."""
        pathway_sum = (
            protective_result.life_years_cvd
            + protective_result.life_years_cancer
            + protective_result.life_years_other
        )
        assert pathway_sum == pytest.approx(
            protective_result.life_years_gained, rel=0.05
        )


# ---------------------------------------------------------------------------
# ICER (cost-effectiveness)
# ---------------------------------------------------------------------------


class TestICER:
    """ICER should be finite and positive when benefit is positive."""

    def test_icer_finite_and_positive(self, protective_result):
        assert np.isfinite(protective_result.cost_per_qaly)
        assert protective_result.cost_per_qaly > 0

    def test_icer_infinite_when_no_benefit(self, neutral_result):
        """ICER should be infinite when QALYs gained is zero."""
        assert neutral_result.cost_per_qaly == float("inf")

    def test_icer_increases_with_cost(self):
        """Higher annual cost should increase ICER."""
        cheap = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=50.0, start_age=40,
        )
        expensive = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=500.0, start_age=40,
        )
        assert expensive.cost_per_qaly > cheap.cost_per_qaly

    def test_total_cost_positive(self, protective_result):
        assert protective_result.total_cost_discounted > 0


# ---------------------------------------------------------------------------
# Discount rate effects
# ---------------------------------------------------------------------------


class TestDiscountRate:
    """Discount rate should reduce present value of future benefits."""

    def test_discounting_reduces_life_years(self, protective_result):
        """Discounted life years should be less than undiscounted."""
        assert protective_result.life_years_gained_discounted < protective_result.life_years_gained

    def test_discounting_reduces_qalys(self, protective_result):
        assert protective_result.qalys_gained_discounted < protective_result.qalys_gained

    def test_zero_discount_gives_equal_values(self):
        """With 0% discount, discounted == undiscounted."""
        result = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.0,
            cost_discount_rate=0.03,
        )
        assert result.life_years_gained_discounted == pytest.approx(
            result.life_years_gained, rel=1e-6
        )
        assert result.qalys_gained_discounted == pytest.approx(
            result.qalys_gained, rel=1e-6
        )

    def test_higher_discount_reduces_more(self):
        """3% discount should reduce QALYs more than 0% but still be positive."""
        result_0 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, qaly_discount_rate=0.0, cost_discount_rate=0.03,
        )
        result_3 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, qaly_discount_rate=0.03, cost_discount_rate=0.03,
        )
        result_5 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, qaly_discount_rate=0.05, cost_discount_rate=0.03,
        )
        assert result_0.qalys_gained_discounted > result_3.qalys_gained_discounted
        assert result_3.qalys_gained_discounted > result_5.qalys_gained_discounted

    def test_discount_rate_affects_icer(self):
        """Different discount rates should produce different ICERs."""
        result_0 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, qaly_discount_rate=0.0, cost_discount_rate=0.03,
        )
        result_3 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, qaly_discount_rate=0.03, cost_discount_rate=0.03,
        )
        assert result_0.cost_per_qaly != result_3.cost_per_qaly


# ---------------------------------------------------------------------------
# Age sensitivity
# ---------------------------------------------------------------------------


class TestAgeSensitivity:
    """Start age should affect lifecycle results."""

    def test_younger_start_more_undiscounted_qalys(self):
        """Starting younger gives more years to accrue benefit."""
        young = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=30,
        )
        old = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=60,
        )
        assert young.qalys_gained > old.qalys_gained

    def test_max_age_parameter(self):
        """Custom max_age should produce different-length computations."""
        result_100 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, max_age=100,
        )
        result_110 = run_lifecycle(
            rr_cvd=0.80, rr_cancer=0.95, rr_other=0.90,
            annual_cost=100.0, start_age=40, max_age=110,
        )
        # More years modeled should give at least as many life years
        assert result_110.life_years_gained >= result_100.life_years_gained
