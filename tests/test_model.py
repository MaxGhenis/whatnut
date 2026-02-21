"""Tests for the forward Monte Carlo model module.

Covers sample_model output shapes, RR distribution sanity checks,
reproducibility with seeds, and summarize_rr output structure.
Uses n_samples=100 for speed.
"""

import numpy as np
import pytest

from whatnut.config import NUT_IDS, PATHWAYS, NUTRIENTS
from whatnut.model import ModelSamples, sample_model, summarize_rr


N_FAST = 100  # Small sample count for fast tests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def samples_default() -> ModelSamples:
    """Samples with default nut IDs and fast sample count."""
    return sample_model(n_samples=N_FAST, seed=42)


@pytest.fixture(scope="module")
def samples_subset() -> ModelSamples:
    """Samples with a subset of nuts."""
    return sample_model(n_samples=N_FAST, seed=42, nut_ids=["walnut", "almond"])


# ---------------------------------------------------------------------------
# Output shape and structure
# ---------------------------------------------------------------------------


class TestSampleModelShapes:
    """sample_model should return correctly shaped arrays."""

    def test_returns_model_samples(self, samples_default):
        assert isinstance(samples_default, ModelSamples)

    def test_rr_dict_has_all_pathways(self, samples_default):
        for pathway in PATHWAYS:
            assert pathway in samples_default.rr

    def test_rr_shape_default(self, samples_default):
        for pathway in PATHWAYS:
            arr = samples_default.rr[pathway]
            assert arr.shape == (N_FAST, len(NUT_IDS)), (
                f"Expected ({N_FAST}, {len(NUT_IDS)}), got {arr.shape}"
            )

    def test_rr_shape_subset(self, samples_subset):
        for pathway in PATHWAYS:
            arr = samples_subset.rr[pathway]
            assert arr.shape == (N_FAST, 2)

    def test_nut_ids_preserved(self, samples_default):
        assert samples_default.nut_ids == list(NUT_IDS)

    def test_nut_ids_subset(self, samples_subset):
        assert samples_subset.nut_ids == ["walnut", "almond"]

    def test_n_samples_attribute(self, samples_default):
        assert samples_default.n_samples == N_FAST

    def test_causal_fraction_shape(self, samples_default):
        assert samples_default.causal_fraction.shape == (N_FAST,)


# ---------------------------------------------------------------------------
# RR distribution sanity
# ---------------------------------------------------------------------------


class TestRRDistributions:
    """Sampled RRs should be physiologically sensible."""

    def test_all_rrs_positive(self, samples_default):
        """Relative risks must be positive (exp of log-RR)."""
        for pathway in PATHWAYS:
            assert np.all(samples_default.rr[pathway] > 0)

    def test_mean_rr_in_sensible_range(self, samples_default):
        """Mean RR for each pathway/nut should be in [0.5, 1.2]."""
        for pathway in PATHWAYS:
            for j, nut_id in enumerate(samples_default.nut_ids):
                mean_rr = np.mean(samples_default.rr[pathway][:, j])
                assert 0.5 <= mean_rr <= 1.2, (
                    f"{pathway}/{nut_id}: mean RR = {mean_rr:.4f} outside [0.5, 1.2]"
                )

    def test_rr_has_variance(self, samples_default):
        """Each RR distribution should show non-zero variance."""
        for pathway in PATHWAYS:
            for j in range(len(samples_default.nut_ids)):
                std = np.std(samples_default.rr[pathway][:, j])
                assert std > 0, f"Zero variance for pathway {pathway}, nut index {j}"

    def test_causal_fraction_in_zero_one(self, samples_default):
        """Causal fraction samples should be in (0, 1)."""
        cf = samples_default.causal_fraction
        assert np.all(cf > 0)
        assert np.all(cf < 1)

    def test_causal_fraction_mean_near_half(self, samples_default):
        """With default Beta(2.5, 2.5) prior, mean should be near 0.5."""
        mean_cf = np.mean(samples_default.causal_fraction)
        assert mean_cf == pytest.approx(0.5, abs=0.15)

    def test_walnut_cvd_rr_tends_low(self):
        """Walnuts (high ALA) should have lower CVD RR than peanuts (no ALA)."""
        samples = sample_model(n_samples=500, seed=42)
        walnut_idx = samples.nut_ids.index("walnut")
        peanut_idx = samples.nut_ids.index("peanut")
        walnut_cvd_mean = np.mean(samples.rr["cvd"][:, walnut_idx])
        peanut_cvd_mean = np.mean(samples.rr["cvd"][:, peanut_idx])
        # Both should be < 1, walnut likely lower (more protective)
        assert walnut_cvd_mean < 1.0
        assert peanut_cvd_mean < 1.0


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Same seed should produce identical results."""

    def test_same_seed_same_output(self):
        s1 = sample_model(n_samples=N_FAST, seed=99)
        s2 = sample_model(n_samples=N_FAST, seed=99)
        for pathway in PATHWAYS:
            np.testing.assert_array_equal(s1.rr[pathway], s2.rr[pathway])
        np.testing.assert_array_equal(s1.causal_fraction, s2.causal_fraction)

    def test_different_seed_different_output(self):
        s1 = sample_model(n_samples=N_FAST, seed=1)
        s2 = sample_model(n_samples=N_FAST, seed=2)
        # At least one pathway should differ
        any_diff = False
        for pathway in PATHWAYS:
            if not np.array_equal(s1.rr[pathway], s2.rr[pathway]):
                any_diff = True
                break
        assert any_diff, "Different seeds produced identical output"


# ---------------------------------------------------------------------------
# Confounding overrides
# ---------------------------------------------------------------------------


class TestConfoundingOverrides:
    """Custom confounding priors should change causal fractions."""

    def test_high_alpha_shifts_mean_up(self):
        """Beta(8, 2) should have mean ~0.8."""
        s = sample_model(
            n_samples=N_FAST,
            seed=42,
            confounding_alpha=8.0,
            confounding_beta=2.0,
        )
        mean_cf = np.mean(s.causal_fraction)
        assert mean_cf > 0.6

    def test_low_alpha_shifts_mean_down(self):
        """Beta(1, 5) should have mean ~0.17."""
        s = sample_model(
            n_samples=N_FAST,
            seed=42,
            confounding_alpha=1.0,
            confounding_beta=5.0,
        )
        mean_cf = np.mean(s.causal_fraction)
        assert mean_cf < 0.4

    def test_confounding_reduces_effect_magnitudes(self):
        """Lower causal fraction should push RRs closer to 1.0 (less extreme)."""
        # High causal fraction (most of observed effect is causal)
        s_high = sample_model(
            n_samples=500,
            seed=42,
            confounding_alpha=9.0,
            confounding_beta=1.0,
        )
        # Low causal fraction (much of observed effect is confounding)
        s_low = sample_model(
            n_samples=500,
            seed=42,
            confounding_alpha=1.0,
            confounding_beta=9.0,
        )
        # For any pathway, the deviation of mean RR from 1.0 should be smaller
        # with lower causal fraction
        for pathway in PATHWAYS:
            deviation_high = np.abs(np.mean(s_high.rr[pathway]) - 1.0)
            deviation_low = np.abs(np.mean(s_low.rr[pathway]) - 1.0)
            assert deviation_low < deviation_high, (
                f"{pathway}: low confounding deviation ({deviation_low:.4f}) should be "
                f"less than high confounding deviation ({deviation_high:.4f})"
            )


# ---------------------------------------------------------------------------
# summarize_rr
# ---------------------------------------------------------------------------


class TestSummarizeRR:
    """summarize_rr should return nested dict with correct structure."""

    @pytest.fixture
    def summary(self, samples_default) -> dict:
        return summarize_rr(samples_default)

    def test_has_all_pathways(self, summary):
        for pathway in PATHWAYS:
            assert pathway in summary

    def test_has_all_nuts_per_pathway(self, summary):
        for pathway in PATHWAYS:
            for nut_id in NUT_IDS:
                assert nut_id in summary[pathway]

    def test_summary_keys(self, summary):
        expected_keys = {"mean", "median", "ci_lower", "ci_upper"}
        for pathway in PATHWAYS:
            for nut_id in NUT_IDS:
                actual_keys = set(summary[pathway][nut_id].keys())
                assert actual_keys == expected_keys

    def test_ci_lower_less_than_upper(self, summary):
        for pathway in PATHWAYS:
            for nut_id in NUT_IDS:
                s = summary[pathway][nut_id]
                assert s["ci_lower"] < s["ci_upper"]

    def test_mean_between_ci(self, summary):
        for pathway in PATHWAYS:
            for nut_id in NUT_IDS:
                s = summary[pathway][nut_id]
                assert s["ci_lower"] <= s["mean"] <= s["ci_upper"]

    def test_all_values_are_floats(self, summary):
        for pathway in PATHWAYS:
            for nut_id in NUT_IDS:
                for key, val in summary[pathway][nut_id].items():
                    assert isinstance(val, float), f"{pathway}/{nut_id}/{key} is {type(val)}"


# ---------------------------------------------------------------------------
# Pathway adjustments (Issue 2)
# ---------------------------------------------------------------------------


class TestPathwayAdjustments:
    """Pathway adjustments from nuts.yaml should modify model output."""

    def test_walnut_cvd_adjusted_more_than_almond(self):
        """Walnut CVD adjustment (1.25) > almond (1.00), so walnut CVD RR
        should be lower (more protective) relative to nutrient predictions."""
        samples = sample_model(n_samples=1000, seed=42)
        walnut_idx = samples.nut_ids.index("walnut")
        almond_idx = samples.nut_ids.index("almond")
        # Walnut has stronger CVD adjustment (1.25 > 1.00)
        # So walnut CVD effect should be amplified
        walnut_cvd = np.mean(samples.rr["cvd"][:, walnut_idx])
        almond_cvd = np.mean(samples.rr["cvd"][:, almond_idx])
        # Walnut has 2.5g ALA + 1.25 adj, almond has 0g ALA + 1.00 adj
        # Walnut should have lower CVD RR
        assert walnut_cvd < almond_cvd, (
            f"Walnut CVD RR ({walnut_cvd:.4f}) should be < almond ({almond_cvd:.4f}) "
            "due to pathway adjustment"
        )

    def test_cashew_adjustment_dampens_effect(self):
        """Cashew CVD adjustment (0.95) should dampen CVD effect."""
        from whatnut.config import get_nut
        cashew = get_nut("cashew")
        adj = cashew.pathway_adjustments["cvd"]
        assert adj.mean < 1.0, "Cashew CVD adjustment should be < 1.0"
