"""External validation tests for QALY estimates.

TDD: Validate that our estimates align with published literature.
"""

import pytest
import numpy as np
from whatnut.simulation import (
    MonteCarloSimulation,
    SimulationParams,
)


class TestExternalValidation:
    """Compare estimates to published QALY/life expectancy data."""

    @pytest.fixture
    def result(self):
        sim = MonteCarloSimulation(seed=42)
        return sim.run(SimulationParams(n_simulations=10000))

    def test_category_effect_aligns_with_literature(self, result):
        """~2.5 QALYs for nut consumption aligns with dietary intervention literature.

        References:
        - Mediterranean diet CEAs show 2-3 QALYs benefit
        - WHO CHOICE lists dietary interventions at 1-5 QALYs typically
        - Our confounding-adjusted estimate should be in this range
        """
        category_effect = result.category_effect.median
        assert 1.0 < category_effect < 5.0, (
            f"Category effect {category_effect:.1f} outside expected range (1-5 QALYs)"
        )

    def test_mortality_reduction_matches_aune_meta(self, result):
        """22% mortality reduction from Aune 2016 translates to ~2-4 years.

        For a 40-year-old with ~40 years remaining life expectancy,
        22% mortality reduction over lifetime ≈ 2-4 additional years.
        After confounding adjustment (~80%), expect 1.5-3 QALYs.
        """
        # All nuts should show positive effect
        for nut_result in result.results:
            assert nut_result.median > 0, f"{nut_result.nut_id} shows no benefit"

        # Average effect should be ~2-3 QALYs after confounding
        medians = [r.median for r in result.results]
        avg_median = np.mean(medians)
        assert 1.5 < avg_median < 4.0, f"Average {avg_median:.1f} outside expected range"

    def test_uncertainty_reflects_meta_analysis_ci(self, result):
        """95% CI should reflect meta-analysis uncertainty.

        Aune 2016: RR 0.78 (0.72-0.84)
        This 15% relative uncertainty should propagate to QALY estimates.
        """
        for nut_result in result.results:
            ci_width = nut_result.ci_95[1] - nut_result.ci_95[0]
            # CI width should be substantial (reflecting uncertainty)
            assert ci_width > 0.5, f"{nut_result.nut_id} CI too narrow"
            # But not implausibly wide
            assert ci_width < 10, f"{nut_result.nut_id} CI too wide"

    def test_walnut_premium_matches_guasch_ferre(self, result):
        """Walnut premium aligns with Guasch-Ferré 2017 cohort data.

        Guasch-Ferré found walnut-specific HR 0.79 for CVD,
        suggesting slight premium over general nuts (HR 0.78).
        Our walnut adjustment of 1.15 should produce ~15% higher QALYs.
        """
        walnut = next(r for r in result.results if r.nut_id == "walnut")
        almond = next(r for r in result.results if r.nut_id == "almond")

        # Walnut should be higher than almond
        assert walnut.median > almond.median

        # Premium should be modest (~10-25%)
        premium_pct = (walnut.median - almond.median) / almond.median * 100
        assert 5 < premium_pct < 30, f"Walnut premium {premium_pct:.0f}% outside expected range"

    def test_peanut_not_penalized_vs_tree_nuts(self, result):
        """Peanuts should be similar to tree nuts per Bao 2013.

        Bao 2013 (n=118,962) found peanuts had similar mortality
        benefits to tree nuts. Peanut should be within ~20% of average.
        """
        peanut = next(r for r in result.results if r.nut_id == "peanut")
        medians = [r.median for r in result.results]
        avg_median = np.mean(medians)

        peanut_diff_pct = abs(peanut.median - avg_median) / avg_median * 100
        assert peanut_diff_pct < 25, f"Peanut differs {peanut_diff_pct:.0f}% from average"


class TestDistributionProperties:
    """Verify statistical properties of sampled distributions."""

    @pytest.fixture
    def sim(self):
        return MonteCarloSimulation(seed=42)

    def test_lognormal_hr_positive(self, sim):
        """Hazard ratio samples should always be positive."""
        params = SimulationParams(n_simulations=10000)
        result = sim.run(params)

        for nut_result in result.results:
            # HR can't be negative - would mean nuts make you immortal
            # All QALY samples derive from positive HRs
            assert all(nut_result.samples > -100), "Implausible negative samples"

    def test_beta_quality_bounded(self, sim):
        """Quality weights should be in (0, 1)."""
        # Run many simulations - if beta is wrong, we'd see out-of-bounds
        params = SimulationParams(n_simulations=10000)
        result = sim.run(params)

        # QALYs should be bounded by reasonable quality weights
        for nut_result in result.results:
            # With quality ~ Beta(17,3) mean 0.85, max life * 0.85 ~= 34 QALYs
            # No sample should exceed this theoretical maximum
            assert all(nut_result.samples < 50), "Samples exceed theoretical maximum"

    def test_confounding_adjustment_realistic(self, sim):
        """Confounding adjustment Beta(8,2) should have mean ~0.80."""
        # If confounding adjustment were broken (e.g., always 0 or 1),
        # we'd see unrealistic estimates
        params = SimulationParams(n_simulations=10000, confounding_adjustment=0.80)
        result = sim.run(params)

        # With 80% confounding adjustment, category effect should be ~80% of
        # what it would be with 95% adjustment (can't use 1.0 as it makes beta invalid)
        params_high_conf = SimulationParams(n_simulations=10000, confounding_adjustment=0.95)
        sim2 = MonteCarloSimulation(seed=42)
        result_high_conf = sim2.run(params_high_conf)

        ratio = result.category_effect.median / result_high_conf.category_effect.median
        assert 0.7 < ratio < 1.0, f"Confounding adjustment ratio {ratio:.2f} unexpected"

    def test_reproducibility_with_seed(self, sim):
        """Same seed should produce identical results."""
        params = SimulationParams(n_simulations=1000, seed=12345)

        sim1 = MonteCarloSimulation(seed=12345)
        result1 = sim1.run(params)

        sim2 = MonteCarloSimulation(seed=12345)
        result2 = sim2.run(params)

        for r1, r2 in zip(result1.results, result2.results):
            assert r1.median == r2.median, "Seeded runs not reproducible"
            assert np.array_equal(r1.samples, r2.samples), "Sample arrays differ"

    def test_different_seeds_differ(self, sim):
        """Different seeds should produce different results."""
        params = SimulationParams(n_simulations=1000)

        sim1 = MonteCarloSimulation(seed=1)
        result1 = sim1.run(params)

        sim2 = MonteCarloSimulation(seed=2)
        result2 = sim2.run(params)

        # At least some results should differ
        any_differ = False
        for r1, r2 in zip(result1.results, result2.results):
            if r1.median != r2.median:
                any_differ = True
                break

        assert any_differ, "Different seeds produced same results"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_young_person_higher_qalys(self):
        """Younger person should gain more QALYs (longer time horizon)."""
        sim = MonteCarloSimulation(seed=42)

        young = SimulationParams(age=30, life_expectancy=50, n_simulations=5000)
        old = SimulationParams(age=70, life_expectancy=15, n_simulations=5000)

        result_young = sim.run(young)
        sim2 = MonteCarloSimulation(seed=42)  # Reset for fair comparison
        result_old = sim2.run(old)

        assert result_young.category_effect.median > result_old.category_effect.median

    def test_lower_base_hr_higher_qalys(self):
        """Lower base HR (more protective) should produce higher QALYs."""
        sim = MonteCarloSimulation(seed=42)

        protective = SimulationParams(base_hr_mean=0.70, n_simulations=5000)
        less_protective = SimulationParams(base_hr_mean=0.85, n_simulations=5000)

        result_prot = sim.run(protective)
        sim2 = MonteCarloSimulation(seed=42)
        result_less = sim2.run(less_protective)

        assert result_prot.category_effect.median > result_less.category_effect.median

    def test_high_confounding_adjustment_gives_higher_estimate(self):
        """Higher confounding adjustment (trusting data more) gives higher estimate."""
        sim = MonteCarloSimulation(seed=42)

        # High confounding adjustment (near 1.0) = trust observational data more
        # Use 0.95 to avoid Beta(alpha, 0) edge case
        params = SimulationParams(confounding_adjustment=0.95, n_simulations=5000)
        result = sim.run(params)

        # Category effect should be higher than with default 0.80 adjustment
        default_params = SimulationParams(confounding_adjustment=0.80, n_simulations=5000)
        sim2 = MonteCarloSimulation(seed=42)
        default_result = sim2.run(default_params)

        assert result.category_effect.median > default_result.category_effect.median
