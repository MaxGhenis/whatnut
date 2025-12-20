"""Tests for pathway-specific lifecycle model."""

import numpy as np
import pytest
from whatnut.lifecycle_pathways import (
    PathwayLifecycleCEA,
    PathwayParams,
    PathwayResult,
    CAUSE_SPECIFIC_RR,
    interpolate_cause_fractions,
    get_weighted_rr,
)


class TestCauseSpecificRR:
    """Tests for cause-specific relative risk data."""

    def test_all_causes_present(self):
        """All major causes should have RR data."""
        assert 'cvd' in CAUSE_SPECIFIC_RR
        assert 'cancer' in CAUSE_SPECIFIC_RR
        assert 'other' in CAUSE_SPECIFIC_RR

    def test_cvd_strongest_effect(self):
        """CVD should have strongest protective effect (lowest RR)."""
        assert CAUSE_SPECIFIC_RR['cvd']['rr'] < CAUSE_SPECIFIC_RR['cancer']['rr']
        assert CAUSE_SPECIFIC_RR['cvd']['rr'] < CAUSE_SPECIFIC_RR['other']['rr']

    def test_rrs_protective(self):
        """All RRs should be < 1 (protective)."""
        for cause, data in CAUSE_SPECIFIC_RR.items():
            assert data['rr'] < 1.0, f"{cause} RR should be < 1"

    def test_rrs_have_sources(self):
        """All RRs should have source citations."""
        for cause, data in CAUSE_SPECIFIC_RR.items():
            assert 'source' in data
            assert len(data['source']) > 0


class TestCauseFractions:
    """Tests for cause-of-death fraction interpolation."""

    def test_fractions_sum_to_one(self):
        """Cause fractions should sum to approximately 1."""
        for age in [30, 40, 50, 60, 70, 80, 90]:
            fracs = interpolate_cause_fractions(age)
            assert sum(fracs) == pytest.approx(1.0, rel=0.01)

    def test_cvd_increases_with_age(self):
        """CVD fraction should increase with age."""
        cvd_40 = interpolate_cause_fractions(40)[0]
        cvd_80 = interpolate_cause_fractions(80)[0]
        assert cvd_80 > cvd_40

    def test_cancer_peaks_midlife(self):
        """Cancer fraction should peak around 50-60."""
        cancer_40 = interpolate_cause_fractions(40)[1]
        cancer_55 = interpolate_cause_fractions(55)[1]
        cancer_90 = interpolate_cause_fractions(90)[1]
        assert cancer_55 > cancer_40
        assert cancer_55 > cancer_90

    def test_interpolation_smooth(self):
        """Interpolation should be smooth between known ages."""
        fracs_45 = interpolate_cause_fractions(45)
        fracs_40 = interpolate_cause_fractions(40)
        fracs_50 = interpolate_cause_fractions(50)

        # 45 should be between 40 and 50 for all causes
        for i in range(3):
            assert min(fracs_40[i], fracs_50[i]) <= fracs_45[i] <= max(fracs_40[i], fracs_50[i])


class TestWeightedRR:
    """Tests for age-weighted relative risk calculation."""

    def test_weighted_rr_between_bounds(self):
        """Weighted RR should be between min and max cause-specific RRs."""
        rr_cvd, rr_cancer, rr_other = 0.75, 0.87, 0.90
        min_rr = min(rr_cvd, rr_cancer, rr_other)
        max_rr = max(rr_cvd, rr_cancer, rr_other)

        for age in [40, 60, 80]:
            weighted = get_weighted_rr(age, rr_cvd, rr_cancer, rr_other)
            assert min_rr <= weighted <= max_rr

    def test_older_ages_lower_rr(self):
        """Older ages should have lower weighted RR (more CVD-dominated)."""
        rr_cvd, rr_cancer, rr_other = 0.75, 0.87, 0.90

        rr_40 = get_weighted_rr(40, rr_cvd, rr_cancer, rr_other)
        rr_80 = get_weighted_rr(80, rr_cvd, rr_cancer, rr_other)

        assert rr_80 < rr_40  # Stronger effect at older ages


class TestPathwayLifecycleCEA:
    """Tests for the pathway-specific lifecycle model."""

    def test_basic_run(self):
        """Model should run and return valid results."""
        model = PathwayLifecycleCEA(seed=42)
        params = PathwayParams(start_age=40)
        result = model.run(params)

        assert isinstance(result, PathwayResult)
        assert result.life_years_gained > 0
        assert result.qalys_gained > 0
        assert result.cost_per_qaly > 0

    def test_pathway_contributions_sum_to_one(self):
        """Pathway contributions should sum to approximately 1."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run(PathwayParams())

        total = result.cvd_contribution + result.cancer_contribution + result.other_contribution
        assert total == pytest.approx(1.0, rel=0.01)

    def test_cvd_dominant_contribution(self):
        """CVD should contribute most to life years gained."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run(PathwayParams())

        assert result.cvd_contribution > result.cancer_contribution
        assert result.cvd_contribution > result.other_contribution
        assert result.cvd_contribution > 0.5  # Should be >50%

    def test_discounting_reduces_values(self):
        """Discounted values should be less than undiscounted."""
        model = PathwayLifecycleCEA(seed=42)

        result_0 = model.run(PathwayParams(discount_rate=0.0))
        result_3 = model.run(PathwayParams(discount_rate=0.03))

        assert result_3.qalys_gained_discounted < result_0.qalys_gained_discounted
        assert result_3.life_years_gained_discounted < result_0.life_years_gained_discounted

    def test_pathway_life_years_sum(self):
        """Pathway life years should approximately sum to total."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run(PathwayParams())

        pathway_sum = result.life_years_cvd + result.life_years_cancer + result.life_years_other
        assert pathway_sum == pytest.approx(result.life_years_gained, rel=0.01)

    def test_reasonable_qaly_range(self):
        """QALYs should be in reasonable range with calibrated confounding."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run(PathwayParams(start_age=40, discount_rate=0.03))

        # With 25% causal (evidence-optimized), discounted QALYs ~0.04-0.15
        assert 0.01 < result.qalys_gained_discounted < 0.5

    def test_reasonable_longevity_range(self):
        """Life years gained should be in reasonable range with calibrated confounding."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run(PathwayParams(start_age=40, discount_rate=0.0))

        # With 25% causal (evidence-optimized), undiscounted life years ~0.25-0.6
        assert 0.1 < result.life_years_gained < 1.5


class TestPathwayMonteCarlo:
    """Tests for Monte Carlo with pathway model."""

    def test_monte_carlo_runs(self):
        """Monte Carlo should run and return expected keys."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run_monte_carlo(PathwayParams(), n_simulations=100)

        assert 'qalys' in result
        assert 'icers' in result
        assert 'cvd_contributions' in result
        assert 'qaly_ci_95' in result
        assert len(result['qalys']) == 100

    def test_monte_carlo_uncertainty(self):
        """Monte Carlo should show uncertainty."""
        model = PathwayLifecycleCEA(seed=42)
        result = model.run_monte_carlo(PathwayParams(), n_simulations=1000)

        assert np.std(result['qalys']) > 0
        assert result['qaly_ci_95'][0] < result['qaly_ci_95'][1]

    def test_reproducible_with_seed(self):
        """Same seed should give same results."""
        model1 = PathwayLifecycleCEA(seed=42)
        model2 = PathwayLifecycleCEA(seed=42)

        result1 = model1.run_monte_carlo(PathwayParams(), n_simulations=100)
        result2 = model2.run_monte_carlo(PathwayParams(), n_simulations=100)

        np.testing.assert_array_almost_equal(result1['qalys'], result2['qalys'])


class TestComparisonWithSingleRRModel:
    """Tests comparing pathway model to single-RR model."""

    def test_pathway_with_calibrated_confounding_gives_lower_qalys(self):
        """Pathway model with calibrated confounding gives lower QALYs.

        The pathway model uses:
        1. Pathway-specific RRs (weighted average higher than uniform 0.78)
        2. Evidence-optimized confounding prior (25% causal vs 80% in single-RR)
        """
        from whatnut.lifecycle import LifecycleCEA, LifecycleParams

        single_model = LifecycleCEA(seed=42)
        single_result = single_model.run(LifecycleParams(start_age=40))

        pathway_model = PathwayLifecycleCEA(seed=42)
        pathway_result = pathway_model.run(PathwayParams(start_age=40))

        # Pathway model should give much lower QALYs due to calibrated confounding
        assert pathway_result.qalys_gained_discounted < single_result.qalys_gained_discounted * 0.5

    def test_pathway_model_near_cost_effectiveness_threshold(self):
        """Pathway model with calibration should be near $50k/QALY threshold."""
        pathway_model = PathwayLifecycleCEA(seed=42)
        pathway_result = pathway_model.run(PathwayParams(start_age=40, annual_cost=250))

        # With calibrated confounding, ICER should be in $30k-$100k range
        assert 30000 < pathway_result.cost_per_qaly < 100000


class TestPathwaySpecificNutAdjustments:
    """Tests for pathway-specific nut adjustments."""

    def test_walnut_benefits_more_than_uniform(self):
        """Walnut with pathway-specific (CVD=1.25) should benefit more than uniform (1.15).

        Walnut's CVD adjustment (1.25) is higher than uniform (1.15), and CVD
        contributes 59% of benefit. So pathway-specific should give higher QALYs.
        Expected: ~5-15% increase.
        """
        from whatnut.lifecycle_pathways import NUT_PATHWAY_ADJUSTMENTS

        model = PathwayLifecycleCEA(seed=42)

        # Uniform adjustment (old model)
        uniform_result = model.run(PathwayParams(
            nut_adj_cvd=1.15,
            nut_adj_cancer=1.15,
            nut_adj_other=1.15,
        ))

        # Pathway-specific (new model)
        walnut = NUT_PATHWAY_ADJUSTMENTS['walnut']
        pathway_result = model.run(PathwayParams(
            nut_adj_cvd=walnut['cvd'][0],
            nut_adj_cancer=walnut['cancer'][0],
            nut_adj_other=walnut['other'][0],
        ))

        # Pathway-specific should give higher QALYs (stronger CVD effect)
        assert pathway_result.qalys_gained > uniform_result.qalys_gained
        # But not dramatically higher (within 20%)
        assert pathway_result.qalys_gained < uniform_result.qalys_gained * 1.20

    def test_peanut_cancer_penalty_reduces_benefit(self):
        """Peanut's cancer penalty (0.90) should reduce overall benefit.

        With pathway-specific, peanut has CVD=0.98, Cancer=0.90, Other=0.98.
        Cancer contributes 17% of benefit. The cancer penalty should be
        partially offset by the higher CVD adjustment (0.98 vs 0.95 uniform).
        Expected: within ±10% of uniform.
        """
        from whatnut.lifecycle_pathways import NUT_PATHWAY_ADJUSTMENTS

        model = PathwayLifecycleCEA(seed=42)

        # Uniform adjustment
        uniform_result = model.run(PathwayParams(
            nut_adj_cvd=0.95,
            nut_adj_cancer=0.95,
            nut_adj_other=0.95,
        ))

        # Pathway-specific
        peanut = NUT_PATHWAY_ADJUSTMENTS['peanut']
        pathway_result = model.run(PathwayParams(
            nut_adj_cvd=peanut['cvd'][0],
            nut_adj_cancer=peanut['cancer'][0],
            nut_adj_other=peanut['other'][0],
        ))

        # Results should be similar (within 10%)
        ratio = pathway_result.qalys_gained / uniform_result.qalys_gained
        assert 0.90 < ratio < 1.10

    def test_walnut_vs_peanut_gap_increases_with_pathway_specific(self):
        """Gap between walnut and peanut should increase with pathway-specific.

        Walnut's CVD advantage (1.25 vs 0.98) is larger than the uniform
        difference (1.15 vs 0.95). So the gap should widen.
        """
        from whatnut.lifecycle_pathways import NUT_PATHWAY_ADJUSTMENTS

        model = PathwayLifecycleCEA(seed=42)

        # Uniform model gap
        walnut_uniform = model.run(PathwayParams(
            nut_adj_cvd=1.15, nut_adj_cancer=1.15, nut_adj_other=1.15,
        ))
        peanut_uniform = model.run(PathwayParams(
            nut_adj_cvd=0.95, nut_adj_cancer=0.95, nut_adj_other=0.95,
        ))
        uniform_gap = walnut_uniform.qalys_gained - peanut_uniform.qalys_gained

        # Pathway-specific model gap
        walnut = NUT_PATHWAY_ADJUSTMENTS['walnut']
        peanut = NUT_PATHWAY_ADJUSTMENTS['peanut']
        walnut_pathway = model.run(PathwayParams(
            nut_adj_cvd=walnut['cvd'][0],
            nut_adj_cancer=walnut['cancer'][0],
            nut_adj_other=walnut['other'][0],
        ))
        peanut_pathway = model.run(PathwayParams(
            nut_adj_cvd=peanut['cvd'][0],
            nut_adj_cancer=peanut['cancer'][0],
            nut_adj_other=peanut['other'][0],
        ))
        pathway_gap = walnut_pathway.qalys_gained - peanut_pathway.qalys_gained

        # Pathway-specific gap should be larger
        assert pathway_gap > uniform_gap
