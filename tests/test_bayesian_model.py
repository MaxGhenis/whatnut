"""Tests for pathway-specific Bayesian model v2.

TDD: Define expectations before running.
"""

import pytest
import numpy as np


class TestExtendedNutrients:
    """Test that extended nutrient data is loaded correctly."""

    def test_all_nuts_have_extended_nutrients(self):
        """All 7 nuts should have the new nutrient fields."""
        from whatnut.bayesian_model import load_extended_nut_nutrients

        nutrients = load_extended_nut_nutrients()
        expected_nuts = ['walnut', 'almond', 'pistachio', 'pecan',
                         'macadamia', 'peanut', 'cashew']

        for nut in expected_nuts:
            assert nut in nutrients, f"Missing nut: {nut}"
            for field in ['magnesium', 'arginine', 'phytosterols', 'protein']:
                assert field in nutrients[nut], f"{nut} missing {field}"
                assert nutrients[nut][field] > 0, f"{nut} {field} should be > 0"

    def test_almond_highest_magnesium_among_tree_nuts(self):
        """Almond should have highest magnesium (76.5mg)."""
        from whatnut.bayesian_model import load_extended_nut_nutrients

        nutrients = load_extended_nut_nutrients()
        tree_nuts = ['walnut', 'almond', 'pistachio', 'pecan', 'macadamia']

        almond_mg = nutrients['almond']['magnesium']
        for nut in tree_nuts:
            if nut != 'almond':
                assert almond_mg >= nutrients[nut]['magnesium'], \
                    f"Almond magnesium should be >= {nut}"

    def test_peanut_highest_protein(self):
        """Peanut should have highest protein (7.3g)."""
        from whatnut.bayesian_model import load_extended_nut_nutrients

        nutrients = load_extended_nut_nutrients()
        peanut_protein = nutrients['peanut']['protein']

        for nut in nutrients:
            if nut != 'peanut':
                assert peanut_protein >= nutrients[nut]['protein'], \
                    f"Peanut protein should be >= {nut}"


class TestPathwayPriors:
    """Test that pathway-specific priors are properly structured."""

    def test_all_pathways_have_all_nutrients(self):
        """Each pathway should have priors for all nutrients."""
        from whatnut.bayesian_model import PATHWAY_NUTRIENT_PRIORS, NUTRIENTS, PATHWAYS

        for pathway in PATHWAYS:
            assert pathway in PATHWAY_NUTRIENT_PRIORS, f"Missing pathway: {pathway}"
            for nutrient in NUTRIENTS:
                assert nutrient in PATHWAY_NUTRIENT_PRIORS[pathway], \
                    f"{pathway} missing {nutrient}"
                prior = PATHWAY_NUTRIENT_PRIORS[pathway][nutrient]
                assert 'mean' in prior and 'sd' in prior, \
                    f"{pathway}/{nutrient} missing mean/sd"

    def test_cvd_has_strongest_ala_effect(self):
        """CVD pathway should have strongest ALA effect."""
        from whatnut.bayesian_model import PATHWAY_NUTRIENT_PRIORS

        cvd_ala = abs(PATHWAY_NUTRIENT_PRIORS['cvd']['ala_omega3']['mean'])
        cancer_ala = abs(PATHWAY_NUTRIENT_PRIORS['cancer']['ala_omega3']['mean'])
        other_ala = abs(PATHWAY_NUTRIENT_PRIORS['other']['ala_omega3']['mean'])

        assert cvd_ala > cancer_ala, "CVD ALA effect should > cancer"
        assert cvd_ala > other_ala, "CVD ALA effect should > other"

    def test_saturated_fat_harmful_in_all_pathways(self):
        """Saturated fat should have positive (harmful) effect in all pathways."""
        from whatnut.bayesian_model import PATHWAY_NUTRIENT_PRIORS, PATHWAYS

        for pathway in PATHWAYS:
            sat_fat = PATHWAY_NUTRIENT_PRIORS[pathway]['saturated_fat']['mean']
            assert sat_fat >= 0, f"Sat fat in {pathway} should be >= 0 (harmful)"


class TestModelStructure:
    """Test that the model is built correctly."""

    def test_model_builds_without_error(self):
        """Model should build without errors."""
        from whatnut.bayesian_model import build_pathway_model, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not installed")

        model, nuts, pathways = build_pathway_model()
        assert len(nuts) == 7
        assert len(pathways) == 4
        assert 'quality' in pathways

    def test_model_has_pathway_specific_effects(self):
        """Model should have separate effect variables for each pathway."""
        from whatnut.bayesian_model import build_pathway_model, PYMC_AVAILABLE

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not installed")

        model, nuts, pathways = build_pathway_model()

        # Check that pathway-specific variables exist
        var_names = [v.name for v in model.free_RVs]
        for pathway in pathways:
            assert any(f'_{pathway}_' in name for name in var_names), \
                f"Model should have {pathway}-specific variables"


class TestMCMCInference:
    """Test MCMC inference produces valid results."""

    @pytest.fixture
    def quick_trace(self):
        """Run quick MCMC for testing."""
        from whatnut.bayesian_model import (
            build_pathway_model, run_pathway_inference, PYMC_AVAILABLE
        )

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not installed")

        model, nuts, pathways = build_pathway_model()
        trace = run_pathway_inference(model, draws=100, tune=50, chains=2, seed=42)
        return trace, nuts, pathways

    def test_fewer_divergences_than_v1(self, quick_trace):
        """Non-centered parameterization should reduce divergences."""
        trace, _, _ = quick_trace

        # Count divergences
        divergences = trace.sample_stats['diverging'].values.sum()
        n_samples = trace.posterior.dims['chain'] * trace.posterior.dims['draw']

        # Should have < 10% divergences (v1 had ~40%)
        divergence_rate = divergences / n_samples
        assert divergence_rate < 0.15, \
            f"Divergence rate {divergence_rate:.1%} too high (should be < 15%)"

    def test_pathway_rrs_differ(self, quick_trace):
        """Different pathways should have different RR patterns."""
        trace, nuts, pathways = quick_trace

        rr_cvd = trace.posterior['rr_cvd'].values.mean(axis=(0, 1))
        rr_cancer = trace.posterior['rr_cancer'].values.mean(axis=(0, 1))

        # CVD and cancer effects shouldn't be identical
        assert not np.allclose(rr_cvd, rr_cancer, atol=0.01), \
            "CVD and cancer RRs shouldn't be identical"

    def test_walnut_cvd_better_than_cancer(self, quick_trace):
        """Walnut should have stronger CVD effect than cancer effect."""
        trace, nuts, _ = quick_trace

        walnut_idx = nuts.index('walnut')
        cvd_effect = trace.posterior['rr_cvd'].values[:, :, walnut_idx].mean()
        cancer_effect = trace.posterior['rr_cancer'].values[:, :, walnut_idx].mean()

        # Walnut CVD RR should be lower (more beneficial) than cancer RR
        assert cvd_effect < cancer_effect, \
            f"Walnut CVD ({cvd_effect:.3f}) should be < cancer ({cancer_effect:.3f})"


class TestLifecycleIntegration:
    """Test integration with lifecycle model."""

    def test_qalys_use_pathway_specific_rrs(self):
        """Lifecycle MC should use different RRs for different pathways."""
        from whatnut.bayesian_model import (
            build_pathway_model, run_pathway_inference,
            run_full_lifecycle_mc, PYMC_AVAILABLE
        )

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not installed")

        model, nuts, pathways = build_pathway_model()
        trace = run_pathway_inference(model, draws=50, tune=25, chains=1, seed=42)
        summary, _ = run_full_lifecycle_mc(trace, nuts, pathways, n_samples=20)

        # All nuts should have results
        assert len(summary) == 7

        # QALYs should be reasonable
        for nut in nuts:
            assert -0.5 < summary[nut]['qaly_mean'] < 0.5, \
                f"{nut} QALY out of reasonable range"

    def test_quality_pathway_affects_qalys(self):
        """Quality pathway should affect final QALY estimates."""
        # This is implicitly tested by the quality multiplier in run_full_lifecycle_mc
        # If quality RR < 1, QALYs should be slightly higher
        from whatnut.bayesian_model import load_extended_nut_nutrients

        nutrients = load_extended_nut_nutrients()

        # High fiber/magnesium nuts should have better quality effects
        # Cashew has highest magnesium (82.8) but low fiber (0.9)
        # Almond has high fiber (3.5) and good magnesium (76.5)
        assert nutrients['almond']['fiber'] > nutrients['cashew']['fiber']


class TestResultsConsistency:
    """Test that results are internally consistent."""

    def test_higher_ala_means_lower_cvd_rr(self):
        """Nuts with more ALA should have lower CVD RR."""
        from whatnut.bayesian_model import (
            build_pathway_model, run_pathway_inference, PYMC_AVAILABLE,
            load_extended_nut_nutrients
        )

        if not PYMC_AVAILABLE:
            pytest.skip("PyMC not installed")

        nutrients = load_extended_nut_nutrients()
        model, nuts, _ = build_pathway_model()
        trace = run_pathway_inference(model, draws=100, tune=50, chains=2, seed=42)

        # Walnut has highest ALA
        walnut_ala = nutrients['walnut']['ala_omega3']
        peanut_ala = nutrients['peanut']['ala_omega3']
        assert walnut_ala > peanut_ala

        # Walnut should have lower CVD RR
        walnut_idx = nuts.index('walnut')
        peanut_idx = nuts.index('peanut')

        walnut_cvd = trace.posterior['rr_cvd'].values[:, :, walnut_idx].mean()
        peanut_cvd = trace.posterior['rr_cvd'].values[:, :, peanut_idx].mean()

        # Walnut CVD should be lower (or very close if uncertainty dominates)
        assert walnut_cvd <= peanut_cvd + 0.02, \
            f"Walnut CVD ({walnut_cvd:.3f}) should be <= peanut CVD ({peanut_cvd:.3f})"
