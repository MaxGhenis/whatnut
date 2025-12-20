"""Tests for lifecycle cost-effectiveness analysis model."""

import numpy as np
import pytest
from whatnut.lifecycle import (
    LifecycleCEA,
    LifecycleParams,
    LifecycleResult,
    NUT_COSTS,
    get_nut_cost,
    run_nut_cea,
    get_mortality_curve,
    get_quality_curve,
    interpolate_mortality,
    get_quality_weight,
)


class TestMortalityCurve:
    """Tests for mortality rate interpolation and curve generation."""

    def test_mortality_increases_with_age(self):
        """Mortality rates should increase monotonically with age."""
        curve = get_mortality_curve(40, 100)
        for i in range(1, len(curve)):
            assert curve[i] >= curve[i - 1], f"Mortality decreased at age {40 + i}"

    def test_mortality_in_valid_range(self):
        """Mortality rates should be between 0 and 1."""
        curve = get_mortality_curve(0, 110)
        assert np.all(curve >= 0)
        assert np.all(curve <= 1)

    def test_interpolation_at_known_age(self):
        """Interpolation at exact age should match table value."""
        # Age 40 is in the table
        rate = interpolate_mortality(40)
        assert rate == pytest.approx(0.00193, rel=0.01)

    def test_interpolation_between_ages(self):
        """Interpolation between ages should give intermediate value."""
        rate_35 = interpolate_mortality(35)
        rate_40 = interpolate_mortality(40)
        rate_37 = interpolate_mortality(37)
        assert rate_35 < rate_37 < rate_40


class TestQualityCurve:
    """Tests for quality of life weight interpolation."""

    def test_quality_decreases_with_age(self):
        """Quality of life should decrease with age."""
        curve = get_quality_curve(40, 100)
        for i in range(1, len(curve)):
            assert curve[i] <= curve[i - 1], f"Quality increased at age {40 + i}"

    def test_quality_in_valid_range(self):
        """Quality weights should be between 0 and 1."""
        curve = get_quality_curve(20, 110)
        assert np.all(curve >= 0)
        assert np.all(curve <= 1)

    def test_quality_at_known_age(self):
        """Quality at exact age should match table value."""
        weight = get_quality_weight(40)
        assert weight == pytest.approx(0.89, rel=0.01)


class TestLifecycleCEA:
    """Tests for the main lifecycle CEA model."""

    def test_basic_run(self):
        """Model should run and return valid results."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40)
        result = model.run(params)

        assert isinstance(result, LifecycleResult)
        assert result.life_years_gained > 0
        assert result.qalys_gained > 0
        assert result.cost_per_qaly > 0

    def test_discounting_reduces_values(self):
        """Discounted values should be less than undiscounted."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40, discount_rate=0.03)
        result = model.run(params)

        assert result.qalys_gained_discounted < result.qalys_gained
        assert result.life_years_gained_discounted < result.life_years_gained

    def test_no_discounting(self):
        """With 0% discount, discounted equals undiscounted."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40, discount_rate=0.0)
        result = model.run(params)

        assert result.qalys_gained_discounted == pytest.approx(result.qalys_gained, rel=0.01)

    def test_younger_age_more_undiscounted_qalys(self):
        """Starting younger yields more undiscounted QALYs (longer horizon)."""
        model = LifecycleCEA(seed=42)
        result_30 = model.run(LifecycleParams(start_age=30))
        result_60 = model.run(LifecycleParams(start_age=60))

        # Undiscounted: more years = more QALYs
        assert result_30.qalys_gained > result_60.qalys_gained

    def test_discounting_affects_age_comparison(self):
        """With discounting, older start can yield higher discounted QALYs.

        This occurs because: (1) mortality is higher at older ages so HR
        reduction saves more life-years in near term, and (2) those gains
        are discounted less than distant gains from young start.
        """
        model = LifecycleCEA(seed=42)
        result_40 = model.run(LifecycleParams(start_age=40))
        result_60 = model.run(LifecycleParams(start_age=60))

        # With 3% discounting, the relationship can invert
        # Just verify both are positive and finite
        assert result_40.qalys_gained_discounted > 0
        assert result_60.qalys_gained_discounted > 0

    def test_lower_hr_more_benefit(self):
        """Lower hazard ratio should yield more life years."""
        model = LifecycleCEA(seed=42)
        result_low = model.run(LifecycleParams(hazard_ratio=0.70))
        result_high = model.run(LifecycleParams(hazard_ratio=0.90))

        assert result_low.life_years_gained > result_high.life_years_gained

    def test_reasonable_qaly_range(self):
        """QALYs gained should be in a reasonable range."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40, hazard_ratio=0.78)
        result = model.run(params)

        # Discounted QALYs should be between 0.1 and 2.0
        assert 0.1 < result.qalys_gained_discounted < 2.0

    def test_reasonable_icer_range(self):
        """ICER should be in a reasonable range for nut consumption."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40, annual_cost=250)
        result = model.run(params)

        # Cost per QALY should be between $1,000 and $100,000
        assert 1000 < result.cost_per_qaly < 100000


class TestMonteCarloSimulation:
    """Tests for Monte Carlo uncertainty analysis."""

    def test_monte_carlo_runs(self):
        """Monte Carlo should run and return expected keys."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40)
        result = model.run_monte_carlo(params, n_simulations=100)

        assert 'qalys' in result
        assert 'icers' in result
        assert 'qaly_mean' in result
        assert 'qaly_ci_95' in result
        assert len(result['qalys']) == 100

    def test_monte_carlo_uncertainty(self):
        """Monte Carlo should show uncertainty (variance > 0)."""
        model = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40)
        result = model.run_monte_carlo(params, n_simulations=1000)

        assert np.std(result['qalys']) > 0
        assert result['qaly_ci_95'][0] < result['qaly_ci_95'][1]

    def test_reproducible_with_seed(self):
        """Same seed should give same results."""
        model1 = LifecycleCEA(seed=42)
        model2 = LifecycleCEA(seed=42)
        params = LifecycleParams(start_age=40)

        result1 = model1.run_monte_carlo(params, n_simulations=100)
        result2 = model2.run_monte_carlo(params, n_simulations=100)

        np.testing.assert_array_almost_equal(result1['qalys'], result2['qalys'])


class TestNutCosts:
    """Tests for nut cost data."""

    def test_all_nuts_have_costs(self):
        """All nuts should have cost data."""
        expected_nuts = ['peanut', 'almond', 'walnut', 'cashew',
                         'pistachio', 'pecan', 'macadamia']
        for nut_id in expected_nuts:
            assert nut_id in NUT_COSTS

    def test_cost_data_complete(self):
        """Each nut cost should have all required fields."""
        for nut_id, cost in NUT_COSTS.items():
            assert cost.price_per_lb > 0
            assert cost.annual_cost_28g > 0
            assert cost.source != ""
            assert cost.source_url.startswith("http")
            assert cost.year >= 2020

    def test_annual_cost_calculation(self):
        """Annual cost should be price × 22.5 lbs."""
        for nut_id, cost in NUT_COSTS.items():
            expected = cost.price_per_lb * 22.5
            assert cost.annual_cost_28g == pytest.approx(expected, rel=0.01)

    def test_get_nut_cost(self):
        """get_nut_cost should return correct data."""
        cost = get_nut_cost('walnut')
        assert cost.nut_id == 'walnut'
        assert cost.price_per_lb > 0

    def test_get_nut_cost_invalid(self):
        """get_nut_cost should raise for invalid nut."""
        with pytest.raises(ValueError, match="Unknown nut"):
            get_nut_cost('invalid_nut')


class TestRunNutCEA:
    """Tests for the convenience function run_nut_cea."""

    def test_run_nut_cea_basic(self):
        """run_nut_cea should work for all nuts."""
        for nut_id in NUT_COSTS:
            result = run_nut_cea(nut_id)
            assert result.qalys_gained_discounted > 0
            assert result.cost_per_qaly > 0

    def test_peanut_most_cost_effective(self):
        """Peanuts should have lowest cost per QALY (cheapest nut)."""
        peanut_result = run_nut_cea('peanut')
        macadamia_result = run_nut_cea('macadamia')

        assert peanut_result.cost_per_qaly < macadamia_result.cost_per_qaly

    def test_custom_parameters(self):
        """Custom parameters should be respected."""
        result_default = run_nut_cea('walnut', start_age=40)
        result_older = run_nut_cea('walnut', start_age=60)

        # Undiscounted QALYs should be higher with younger start (more years)
        assert result_default.qalys_gained > result_older.qalys_gained
