"""Tests for Monte Carlo simulation module.

TDD: Define expected simulation behavior and outputs.
"""

import pytest
import numpy as np
from whatnut.simulation import (
    MonteCarloSimulation,
    SimulationParams,
    SimulationResult,
    DEFAULT_PARAMS,
)


class TestSimulationParams:
    """Simulation parameters must be valid."""

    def test_default_params_exist(self):
        assert DEFAULT_PARAMS is not None

    def test_default_params_reasonable(self):
        p = DEFAULT_PARAMS
        assert 20 <= p.age <= 80
        assert 0.6 < p.base_hr_mean < 0.9  # Meta-analysis range
        assert p.n_simulations >= 1000
        assert 0 < p.confounding_adjustment <= 1

    def test_params_validation(self):
        with pytest.raises(ValueError):
            SimulationParams(age=-1)
        with pytest.raises(ValueError):
            SimulationParams(base_hr_mean=1.5)  # HR > 1 means nuts increase mortality
        with pytest.raises(ValueError):
            SimulationParams(n_simulations=0)


class TestMonteCarloSimulation:
    """Monte Carlo simulation must produce valid outputs."""

    @pytest.fixture
    def simulation(self):
        return MonteCarloSimulation(seed=42)

    def test_simulation_reproducible(self, simulation):
        """Same seed should produce same results."""
        result1 = simulation.run(DEFAULT_PARAMS)
        sim2 = MonteCarloSimulation(seed=42)
        result2 = sim2.run(DEFAULT_PARAMS)
        assert result1.results[0].median == result2.results[0].median

    def test_simulation_returns_all_nuts(self, simulation):
        from whatnut.nuts import NUTS
        result = simulation.run(DEFAULT_PARAMS)
        assert len(result.results) == len(NUTS)

    def test_simulation_result_structure(self, simulation):
        result = simulation.run(DEFAULT_PARAMS)
        for nut_result in result.results:
            assert hasattr(nut_result, "nut_id")
            assert hasattr(nut_result, "samples")
            assert hasattr(nut_result, "median")
            assert hasattr(nut_result, "mean")
            assert hasattr(nut_result, "ci_95")
            assert hasattr(nut_result, "p_positive")

    def test_samples_count_matches_n_simulations(self, simulation):
        params = SimulationParams(n_simulations=500)
        result = simulation.run(params)
        for nut_result in result.results:
            assert len(nut_result.samples) == 500


class TestSimulationResults:
    """Simulation results must be scientifically plausible."""

    @pytest.fixture
    def result(self):
        sim = MonteCarloSimulation(seed=42)
        return sim.run(DEFAULT_PARAMS)

    def test_all_qalys_plausible(self, result):
        """QALY gains should be in plausible range (0-10 years)."""
        for nut_result in result.results:
            assert -2 < nut_result.median < 10
            assert nut_result.ci_95[0] > -5
            assert nut_result.ci_95[1] < 15

    def test_positive_probability_high(self, result):
        """Probability of positive effect should be high for all nuts."""
        for nut_result in result.results:
            assert nut_result.p_positive > 0.8, f"{nut_result.nut_id} p_positive too low"

    def test_walnut_highest_median(self, result):
        """Walnuts should have highest median QALY."""
        walnut = next(r for r in result.results if r.nut_id == "walnut")
        for nut_result in result.results:
            if nut_result.nut_id != "walnut":
                assert walnut.median >= nut_result.median - 0.1  # Allow small tolerance

    def test_spread_between_nuts_small(self, result):
        """Difference between best and worst should be < 1.5 QALYs."""
        medians = [r.median for r in result.results]
        spread = max(medians) - min(medians)
        assert spread < 1.5, f"Spread {spread} too large"

    def test_category_effect_larger_than_spread(self, result):
        """Any nut vs no nuts should be larger than nut choice effect."""
        medians = [r.median for r in result.results]
        spread = max(medians) - min(medians)
        category_effect = result.category_effect.median
        assert category_effect > spread, "Category effect should exceed nut spread"


class TestUncertaintyQuantification:
    """Uncertainty must reflect evidence quality."""

    @pytest.fixture
    def result(self):
        sim = MonteCarloSimulation(seed=42)
        return sim.run(DEFAULT_PARAMS)

    def test_low_evidence_wider_ci(self, result):
        """Nuts with less evidence (higher SD) should have wider CIs on average."""
        # Almond has lowest SD (0.06) - strongest evidence
        almond = next(r for r in result.results if r.nut_id == "almond")
        almond_width = almond.ci_95[1] - almond.ci_95[0]

        # Pecan has highest SD (0.18) - weakest evidence
        pecan = next(r for r in result.results if r.nut_id == "pecan")
        pecan_width = pecan.ci_95[1] - pecan.ci_95[0]

        assert pecan_width > almond_width

    def test_ci_contains_median(self, result):
        """95% CI should contain the median."""
        for nut_result in result.results:
            assert nut_result.ci_95[0] <= nut_result.median <= nut_result.ci_95[1]
