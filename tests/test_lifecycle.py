"""Tests for the pathway-specific lifecycle cost-effectiveness analysis.

Covers run_lifecycle with deterministic RRs, directional checks on
life years gained, pathway contributions, ICER, and discount rate effects.
"""

import numpy as np
import pytest

from whatnut.config import get_cause_fractions, get_mortality_curve
from whatnut.lifecycle import (
    BaselineOutcomes,
    LifecycleResult,
    _adjust_mortality_on_hazard_scale,
    _cause_fraction_matrix,
    _cycle_occupancy,
    _survival_at_cycle_start,
    calculate_baseline_outcomes,
    run_lifecycle,
    run_lifecycle_vectorized,
)

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
            "qalys_gained_discounted_cvd",
            "qalys_gained_discounted_cancer",
            "qalys_gained_discounted_other",
            "life_years_gained",
            "qalys_gained",
            "life_years_gained_discounted",
            "qalys_gained_discounted",
            "total_cost_discounted",
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
            rr_cvd=0.70,
            rr_cancer=0.85,
            rr_other=0.80,
            annual_cost=100.0,
            start_age=40,
        )
        weak = run_lifecycle(
            rr_cvd=0.95,
            rr_cancer=0.98,
            rr_other=0.97,
            annual_cost=100.0,
            start_age=40,
        )
        assert strong.life_years_gained > weak.life_years_gained

    def test_pathway_relative_risks_are_weighted_exactly_once(self):
        """Cause-specific RRs should enter the mortality curve once."""
        start_age = 40
        max_age = 80
        rr_cvd, rr_cancer, rr_other = 0.75, 0.9, 1.05
        result = run_lifecycle(
            rr_cvd=rr_cvd,
            rr_cancer=rr_cancer,
            rr_other=rr_other,
            annual_cost=100.0,
            start_age=start_age,
            max_age=max_age,
        )

        ages = np.arange(start_age, max_age + 1)
        mortality = get_mortality_curve(start_age, max_age)
        weighted_rr = np.array(
            [
                sum(
                    fraction * rr
                    for fraction, rr in zip(
                        get_cause_fractions(int(age)),
                        (rr_cvd, rr_cancer, rr_other),
                    )
                )
                for age in ages
            ]
        )
        baseline = np.insert(np.cumprod(1 - mortality)[:-1], 0, 1.0)
        baseline_hazard = -np.log1p(-mortality)
        intervention_mortality = -np.expm1(-baseline_hazard * weighted_rr)
        intervention = np.insert(np.cumprod(1 - intervention_mortality)[:-1], 0, 1.0)
        baseline_occupancy = 0.5 * (baseline + baseline * (1 - mortality))
        intervention_occupancy = 0.5 * (
            intervention + intervention * (1 - intervention_mortality)
        )
        expected_life_years = float(np.sum(intervention_occupancy - baseline_occupancy))

        assert result.life_years_gained == pytest.approx(expected_life_years)


class TestHalfCycleOccupancy:
    """Outcomes and recurring costs accrue over person-time within each year."""

    def test_cycle_occupancy_uses_mean_boundary_survival(self):
        qx = np.array([0.0, 1.0])
        survival = _survival_at_cycle_start(qx)

        assert survival == pytest.approx([1.0, 1.0])
        assert _cycle_occupancy(survival, qx) == pytest.approx([1.0, 0.5])

    def test_terminal_interval_contributes_half_a_year(self):
        outcomes = calculate_baseline_outcomes(
            start_age=100,
            max_age=100,
            qaly_discount_rate=0.0,
        )

        assert outcomes.life_years == pytest.approx(0.5)
        assert outcomes.life_years_discounted == pytest.approx(0.5)

    def test_mid_cycle_discounting_applies_to_terminal_interval(self):
        outcomes = calculate_baseline_outcomes(
            start_age=100,
            max_age=100,
            qaly_discount_rate=0.03,
        )

        assert outcomes.life_years_discounted == pytest.approx(0.5 / np.sqrt(1.03))

    def test_recurring_cost_uses_discounted_intervention_occupancy(self):
        annual_cost = 100.0
        discount_rate = 0.03
        baseline = calculate_baseline_outcomes(
            start_age=40,
            qaly_discount_rate=discount_rate,
        )
        neutral = run_lifecycle(
            rr_cvd=1.0,
            rr_cancer=1.0,
            rr_other=1.0,
            annual_cost=annual_cost,
            start_age=40,
            cost_discount_rate=discount_rate,
        )

        assert neutral.total_cost_discounted == pytest.approx(
            annual_cost * baseline.life_years_discounted
        )


class TestBaselineOutcomes:
    """The public baseline helper shares lifecycle conventions."""

    def test_returns_typed_complete_outcomes(self):
        outcomes = calculate_baseline_outcomes(start_age=40)

        assert isinstance(outcomes, BaselineOutcomes)
        assert outcomes.life_years > outcomes.qalys > 0
        assert outcomes.life_years > outcomes.life_years_discounted > 0
        assert outcomes.qalys > outcomes.qalys_discounted > 0
        assert outcomes.average_quality_weight == pytest.approx(
            outcomes.qalys / outcomes.life_years
        )

    def test_age_40_life_years_use_half_cycle_occupancy(self):
        outcomes = calculate_baseline_outcomes(
            start_age=40,
            max_age=100,
            qaly_discount_rate=0.03,
        )

        assert outcomes.life_years == pytest.approx(38.80806987410118)

    def test_matches_independent_trapezoidal_calculation(self):
        mortality = np.asarray(get_mortality_curve(40, 100), dtype=float)
        start_survival = np.insert(np.cumprod(1 - mortality)[:-1], 0, 1.0)
        end_survival = start_survival * (1 - mortality)
        expected_life_years = float(np.sum((start_survival + end_survival) / 2))

        outcomes = calculate_baseline_outcomes(start_age=40, max_age=100)

        assert outcomes.life_years == pytest.approx(expected_life_years)


class TestVectorizedParity:
    """Vectorized lifecycle results must match scalar calculations draw by draw."""

    def test_scalar_and_vectorized_paths_match(self):
        rr_cvd = np.array([0.8, 1.0, 1.1])
        rr_cancer = np.array([0.95, 1.0, 1.05])
        rr_other = np.array([0.9, 1.0, 1.08])
        vector = run_lifecycle_vectorized(
            rr_cvd=rr_cvd,
            rr_cancer=rr_cancer,
            rr_other=rr_other,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )

        fields = (
            "qalys_gained_discounted_cvd",
            "qalys_gained_discounted_cancer",
            "qalys_gained_discounted_other",
            "life_years_gained",
            "qalys_gained",
            "life_years_gained_discounted",
            "qalys_gained_discounted",
            "total_cost_discounted",
        )
        for index in range(len(rr_cvd)):
            scalar = run_lifecycle(
                rr_cvd=float(rr_cvd[index]),
                rr_cancer=float(rr_cancer[index]),
                rr_other=float(rr_other[index]),
                annual_cost=100.0,
                start_age=40,
                qaly_discount_rate=0.03,
                cost_discount_rate=0.03,
            )
            for field in fields:
                assert getattr(vector, field)[index] == pytest.approx(
                    getattr(scalar, field)
                )

    def test_deprecated_vector_icer_is_available(self):
        vector = run_lifecycle_vectorized(
            rr_cvd=np.array([0.8, 1.0]),
            rr_cancer=np.array([0.9, 1.0]),
            rr_other=np.array([0.95, 1.0]),
            annual_cost=100.0,
        )
        with pytest.deprecated_call(match="decision module"):
            ratios = vector.cost_per_qaly
        assert np.isfinite(ratios[0])
        assert ratios[1] == np.inf


# ---------------------------------------------------------------------------
# Pathway contributions
# ---------------------------------------------------------------------------


class TestPathwayContributions:
    """Pathway contributions exactly attribute the primary discounted QALYs."""

    def test_contributions_sum_to_one(self, protective_result):
        total = (
            protective_result.cvd_contribution
            + protective_result.cancer_contribution
            + protective_result.other_contribution
        )
        assert total == pytest.approx(1.0, abs=1e-10)

    def test_all_contributions_non_negative(self, protective_result):
        assert protective_result.cvd_contribution >= 0
        assert protective_result.cancer_contribution >= 0
        assert protective_result.other_contribution >= 0

    def test_neutral_effect_has_deterministic_zero_shares(self, neutral_result):
        assert neutral_result.cvd_contribution == 0
        assert neutral_result.cancer_contribution == 0
        assert neutral_result.other_contribution == 0
        assert neutral_result.qalys_gained_discounted_cvd == pytest.approx(
            0.0, abs=1e-14
        )
        assert neutral_result.qalys_gained_discounted_cancer == pytest.approx(
            0.0, abs=1e-14
        )
        assert neutral_result.qalys_gained_discounted_other == pytest.approx(
            0.0, abs=1e-14
        )

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
        """Legacy by-pathway life-year fields remain an exact LY decomposition."""
        pathway_sum = (
            protective_result.life_years_cvd
            + protective_result.life_years_cancer
            + protective_result.life_years_other
        )
        assert pathway_sum == pytest.approx(
            protective_result.life_years_gained, abs=1e-12
        )

    def test_discounted_qaly_pathways_sum_to_primary_total(self, protective_result):
        pathway_sum = (
            protective_result.qalys_gained_discounted_cvd
            + protective_result.qalys_gained_discounted_cancer
            + protective_result.qalys_gained_discounted_other
        )

        assert pathway_sum == pytest.approx(
            protective_result.qalys_gained_discounted, abs=1e-12
        )

    def test_contributions_are_discounted_qaly_shares(self, protective_result):
        total = protective_result.qalys_gained_discounted

        assert protective_result.cvd_contribution == pytest.approx(
            protective_result.qalys_gained_discounted_cvd / total
        )
        assert protective_result.cancer_contribution == pytest.approx(
            protective_result.qalys_gained_discounted_cancer / total
        )
        assert protective_result.other_contribution == pytest.approx(
            protective_result.qalys_gained_discounted_other / total
        )


class TestVectorizedPathwayAttribution:
    """Per-draw Shapley components support attribution of expected QALYs."""

    @pytest.fixture
    def vector(self):
        return run_lifecycle_vectorized(
            rr_cvd=np.array([0.7, 0.7, 1.1, 1.0]),
            rr_cancer=np.array([0.9, 1.2, 1.2, 1.0]),
            rr_other=np.ones(4),
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )

    def test_components_sum_to_total_for_every_draw(self, vector):
        pathway_sum = (
            vector.qalys_gained_discounted_cvd
            + vector.qalys_gained_discounted_cancer
            + vector.qalys_gained_discounted_other
        )

        assert pathway_sum == pytest.approx(vector.qalys_gained_discounted, abs=1e-12)

    def test_components_are_signed_for_protective_and_harmful_pathways(self, vector):
        assert vector.qalys_gained_discounted_cvd[0] > 0
        assert vector.qalys_gained_discounted_cancer[0] > 0
        assert vector.qalys_gained_discounted_cvd[1] > 0
        assert vector.qalys_gained_discounted_cancer[1] < 0
        assert vector.qalys_gained_discounted_cvd[2] < 0
        assert vector.qalys_gained_discounted_cancer[2] < 0

    def test_structural_null_pathway_has_zero_component(self, vector):
        assert vector.qalys_gained_discounted_other == pytest.approx(
            np.zeros(4), abs=1e-14
        )

    def test_null_draw_has_zero_components(self, vector):
        components = np.array(
            [
                vector.qalys_gained_discounted_cvd[3],
                vector.qalys_gained_discounted_cancer[3],
                vector.qalys_gained_discounted_other[3],
            ]
        )

        assert components == pytest.approx(np.zeros(3), abs=1e-14)

    def test_expected_component_shares_reconstruct_expected_qaly(self, vector):
        component_means = np.array(
            [
                np.mean(vector.qalys_gained_discounted_cvd),
                np.mean(vector.qalys_gained_discounted_cancer),
                np.mean(vector.qalys_gained_discounted_other),
            ]
        )
        expected_qaly = float(np.mean(vector.qalys_gained_discounted))
        expected_shares = component_means / expected_qaly

        assert component_means.sum() == pytest.approx(expected_qaly, abs=1e-12)
        assert expected_shares.sum() == pytest.approx(1.0, abs=1e-12)
        assert float(np.sum(expected_shares * expected_qaly)) == pytest.approx(
            expected_qaly, abs=1e-12
        )


# ---------------------------------------------------------------------------
# ICER (cost-effectiveness)
# ---------------------------------------------------------------------------


class TestDeprecatedICERCompatibility:
    """Legacy draw-level ICER access remains available with a warning."""

    def test_icer_finite_and_positive(self, protective_result):
        with pytest.deprecated_call(match="decision module"):
            icer = protective_result.cost_per_qaly
        assert np.isfinite(icer)
        assert icer > 0

    def test_icer_infinite_when_no_benefit(self, neutral_result):
        """ICER should be infinite when QALYs gained is zero."""
        with pytest.deprecated_call(match="decision module"):
            assert neutral_result.cost_per_qaly == float("inf")

    def test_icer_increases_with_cost(self):
        """Higher annual cost should increase ICER."""
        cheap = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=50.0,
            start_age=40,
        )
        expensive = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=500.0,
            start_age=40,
        )
        with pytest.deprecated_call(match="decision module"):
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
        assert (
            protective_result.life_years_gained_discounted
            < protective_result.life_years_gained
        )

    def test_discounting_reduces_qalys(self, protective_result):
        assert (
            protective_result.qalys_gained_discounted < protective_result.qalys_gained
        )

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
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.0,
            cost_discount_rate=0.03,
        )
        result_3 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )
        result_5 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.05,
            cost_discount_rate=0.03,
        )
        assert result_0.qalys_gained_discounted > result_3.qalys_gained_discounted
        assert result_3.qalys_gained_discounted > result_5.qalys_gained_discounted

    def test_discount_rate_affects_icer(self):
        """Different discount rates should produce different ICERs."""
        result_0 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.0,
            cost_discount_rate=0.03,
        )
        result_3 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            qaly_discount_rate=0.03,
            cost_discount_rate=0.03,
        )
        with pytest.deprecated_call(match="decision module"):
            assert result_0.cost_per_qaly != result_3.cost_per_qaly


# ---------------------------------------------------------------------------
# Age sensitivity
# ---------------------------------------------------------------------------


class TestAgeSensitivity:
    """Start age should affect lifecycle results."""

    def test_younger_start_more_undiscounted_qalys(self):
        """Starting younger gives more years to accrue benefit."""
        young = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=30,
        )
        old = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=60,
        )
        assert young.qalys_gained > old.qalys_gained

    def test_max_age_parameter(self):
        """The CDC open interval is the last supported lifecycle age."""
        result_99 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            max_age=99,
        )
        result_100 = run_lifecycle(
            rr_cvd=0.80,
            rr_cancer=0.95,
            rr_other=0.90,
            annual_cost=100.0,
            start_age=40,
            max_age=100,
        )
        assert result_100.life_years_gained >= result_99.life_years_gained
        with pytest.raises(ValueError, match="max_age"):
            run_lifecycle(
                rr_cvd=0.80,
                rr_cancer=0.95,
                rr_other=0.90,
                annual_cost=100.0,
                start_age=40,
                max_age=101,
            )


class TestScientificDomains:
    """Mortality, survival, and cost always remain in valid domains."""

    def test_harmful_hazard_ratios_still_produce_valid_probabilities(self):
        ages = np.arange(40, 101)
        baseline_qx = get_mortality_curve(40, 100)
        fractions = _cause_fraction_matrix(ages)
        adjusted_qx = _adjust_mortality_on_hazard_scale(
            baseline_qx,
            fractions,
            np.array([[10.0, 7.0, 5.0], [0.0, 0.0, 0.0]]),
        )
        survival = _survival_at_cycle_start(adjusted_qx)

        assert np.all(np.isfinite(adjusted_qx))
        assert np.all((adjusted_qx >= 0) & (adjusted_qx <= 1))
        assert np.all((survival >= 0) & (survival <= 1))
        assert np.all(np.diff(survival, axis=1) <= 0)
        assert np.all(adjusted_qx[:, -1] == 1.0)

    def test_extreme_harm_has_finite_nonnegative_cost(self):
        result = run_lifecycle_vectorized(
            rr_cvd=np.array([1.0, 10.0, 100.0]),
            rr_cancer=np.array([1.0, 10.0, 100.0]),
            rr_other=np.array([1.0, 10.0, 100.0]),
            annual_cost=100.0,
        )
        assert np.all(np.isfinite(result.total_cost_discounted))
        assert np.all(result.total_cost_discounted >= 0)

    @pytest.mark.parametrize("annual_cost", [-1, np.nan, np.inf, True])
    def test_invalid_annual_cost_rejected(self, annual_cost):
        with pytest.raises(ValueError, match="annual_cost"):
            run_lifecycle(0.8, 0.9, 0.95, annual_cost)

    @pytest.mark.parametrize("hazard_ratio", [-0.1, np.nan, np.inf, True])
    def test_invalid_hazard_ratio_rejected(self, hazard_ratio):
        with pytest.raises(ValueError, match="rr_cvd"):
            run_lifecycle(hazard_ratio, 0.9, 0.95, 100.0)

    @pytest.mark.parametrize("start_age", [0, 19, 101, 40.5, True])
    def test_unsupported_start_age_rejected(self, start_age):
        with pytest.raises(ValueError, match="start_age"):
            run_lifecycle(0.8, 0.9, 0.95, 100.0, start_age=start_age)

    def test_vector_inputs_must_have_matching_shapes(self):
        with pytest.raises(ValueError, match="equal lengths"):
            run_lifecycle_vectorized(
                np.array([0.8, 0.9]),
                np.array([0.9]),
                np.array([0.95, 1.0]),
                100.0,
            )

    def test_signed_shapley_pathways_sum_to_total(self):
        result = run_lifecycle(
            rr_cvd=0.7,
            rr_cancer=1.2,
            rr_other=0.95,
            annual_cost=100.0,
        )
        assert (
            result.life_years_cvd + result.life_years_cancer + result.life_years_other
        ) == pytest.approx(result.life_years_gained, abs=1e-12)
        assert (
            result.qalys_gained_discounted_cvd
            + result.qalys_gained_discounted_cancer
            + result.qalys_gained_discounted_other
        ) == pytest.approx(result.qalys_gained_discounted, abs=1e-12)
        assert (
            result.cvd_contribution
            + result.cancer_contribution
            + result.other_contribution
        ) == pytest.approx(1.0, abs=1e-10)
        assert result.qalys_gained_discounted_cvd > 0
        assert result.qalys_gained_discounted_cancer < 0
        assert result.cancer_contribution < 0
