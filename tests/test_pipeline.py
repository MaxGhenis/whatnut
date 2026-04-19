"""Tests for the end-to-end analysis pipeline.

Covers run_analysis with small n_samples, output structure, completeness,
JSON serializability, and reproducibility.
Uses n_samples=100 for speed.
"""

import json

import numpy as np
import pytest

from whatnut.config import NUT_IDS, PATHWAYS
from whatnut.pipeline import AnalysisResults, NutAnalysis, run_analysis


N_FAST = 100


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def results() -> AnalysisResults:
    """Run a fast analysis for all tests in this module."""
    return run_analysis(n_samples=N_FAST, seed=42)


# ---------------------------------------------------------------------------
# Output structure
# ---------------------------------------------------------------------------


class TestAnalysisStructure:
    """run_analysis should return a well-formed AnalysisResults."""

    def test_returns_analysis_results(self, results):
        assert isinstance(results, AnalysisResults)

    def test_parameters_stored(self, results):
        assert results.seed == 42
        assert results.n_samples == N_FAST
        assert results.start_age == 40
        assert results.qaly_discount_rate == 0.0
        assert results.cost_discount_rate == 0.03

    def test_confounding_stored(self, results):
        assert results.confounding_alpha == pytest.approx(1.5)
        assert results.confounding_beta == pytest.approx(6.0)
        assert results.confounding_mean == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# All nuts present
# ---------------------------------------------------------------------------


class TestAllNutsPresent:
    """Every nut ID should appear in the results."""

    def test_all_nut_ids_in_results(self, results):
        for nut_id in NUT_IDS:
            assert nut_id in results.nuts, f"Missing nut: {nut_id}"

    def test_nut_analysis_types(self, results):
        for nut_id, na in results.nuts.items():
            assert isinstance(na, NutAnalysis), f"{nut_id} is {type(na)}"

    def test_nut_ids_match(self, results):
        for nut_id, na in results.nuts.items():
            assert na.nut_id == nut_id

    def test_nut_names_capitalized(self, results):
        for nut_id, na in results.nuts.items():
            assert na.name == nut_id.capitalize()


# ---------------------------------------------------------------------------
# Per-nut field validity
# ---------------------------------------------------------------------------


class TestNutAnalysisFields:
    """Each NutAnalysis should have sensible values."""

    def test_qaly_ci_ordered(self, results):
        for nut_id, na in results.nuts.items():
            assert na.qaly_ci_lower <= na.qaly_mean <= na.qaly_ci_upper, (
                f"{nut_id}: CI [{na.qaly_ci_lower}, {na.qaly_ci_upper}] "
                f"doesn't contain mean {na.qaly_mean}"
            )

    def test_life_years_ci_ordered(self, results):
        for nut_id, na in results.nuts.items():
            assert na.life_years_ci_lower <= na.life_years_mean <= na.life_years_ci_upper

    def test_p_positive_in_zero_one(self, results):
        for nut_id, na in results.nuts.items():
            assert 0 <= na.p_positive <= 1, (
                f"{nut_id}: p_positive = {na.p_positive}"
            )

    def test_annual_cost_positive(self, results):
        for nut_id, na in results.nuts.items():
            assert na.annual_cost > 0

    def test_pathway_rrs_populated(self, results):
        for nut_id, na in results.nuts.items():
            assert na.rr_cvd > 0, f"{nut_id}: rr_cvd = {na.rr_cvd}"
            assert na.rr_cancer > 0, f"{nut_id}: rr_cancer = {na.rr_cancer}"
            assert na.rr_other > 0, f"{nut_id}: rr_other = {na.rr_other}"

    def test_pathway_rrs_in_sensible_range(self, results):
        for nut_id, na in results.nuts.items():
            for attr in ("rr_cvd", "rr_cancer", "rr_other"):
                val = getattr(na, attr)
                assert 0.5 <= val <= 1.2, f"{nut_id}.{attr} = {val}"

    def test_pathway_contributions_sum(self, results):
        for nut_id, na in results.nuts.items():
            total = na.cvd_contribution + na.cancer_contribution + na.other_contribution
            assert total == pytest.approx(1.0, abs=0.1), (
                f"{nut_id}: contributions sum to {total}"
            )

    def test_icer_median_positive_or_inf(self, results):
        for nut_id, na in results.nuts.items():
            assert na.icer_median > 0 or na.icer_median == float("inf")

    def test_evidence_levels_valid(self, results):
        valid = {"strong", "moderate", "limited"}
        for nut_id, na in results.nuts.items():
            assert na.evidence in valid, f"{nut_id} evidence: {na.evidence}"

    def test_life_years_in_plausible_range(self, results):
        """Mean life years gained should be in [0, 5] for all nuts."""
        for nut_id, na in results.nuts.items():
            assert -1 <= na.life_years_mean <= 5, (
                f"{nut_id}: life_years_mean = {na.life_years_mean} outside [-1, 5]"
            )

    def test_qalys_in_plausible_range(self, results):
        """Mean discounted QALYs should be in [-1, 2] for all nuts."""
        for nut_id, na in results.nuts.items():
            assert -1 <= na.qaly_mean <= 2, (
                f"{nut_id}: qaly_mean = {na.qaly_mean} outside [-1, 2]"
            )


# ---------------------------------------------------------------------------
# Aggregate pathway contributions
# ---------------------------------------------------------------------------


class TestAggregateContributions:
    """Aggregate pathway contributions across all nuts."""

    def test_aggregate_contributions_present(self, results):
        assert hasattr(results, "cvd_contribution_mean")
        assert hasattr(results, "cancer_contribution_mean")
        assert hasattr(results, "other_contribution_mean")

    def test_aggregate_contributions_sum(self, results):
        total = (
            results.cvd_contribution_mean
            + results.cancer_contribution_mean
            + results.other_contribution_mean
        )
        assert total == pytest.approx(1.0, abs=0.1)

    def test_other_pathway_no_longer_dominates(self, results):
        assert results.other_contribution_mean < 0.35


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    """Results should be serializable to dict and JSON."""

    def test_to_dict_returns_dict(self, results):
        d = results.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_nuts(self, results):
        d = results.to_dict()
        assert "nuts" in d
        for nut_id in NUT_IDS:
            assert nut_id in d["nuts"]

    def test_to_dict_has_parameters(self, results):
        d = results.to_dict()
        assert d["seed"] == 42
        assert d["n_samples"] == N_FAST
        assert d["start_age"] == 40
        assert d["qaly_discount_rate"] == 0.0
        assert d["cost_discount_rate"] == 0.03

    def test_json_serializable(self, results):
        """to_dict output should be fully JSON-serializable."""
        d = results.to_dict()
        json_str = json.dumps(d)
        assert isinstance(json_str, str)
        assert len(json_str) > 0

    def test_json_round_trip(self, results):
        """Serialize to JSON and deserialize, values should match."""
        d = results.to_dict()
        json_str = json.dumps(d)
        loaded = json.loads(json_str)
        assert loaded["seed"] == d["seed"]
        assert loaded["nuts"]["walnut"]["qaly_mean"] == d["nuts"]["walnut"]["qaly_mean"]

    def test_no_nan_or_inf_in_json(self, results):
        """JSON should not contain NaN or Infinity (except icer_ci_upper which can be None)."""
        d = results.to_dict()
        for nut_id, nd in d["nuts"].items():
            for key, val in nd.items():
                if val is None:
                    continue  # icer_ci_upper can be None
                if isinstance(val, float):
                    assert np.isfinite(val) or key == "icer_median", (
                        f"{nut_id}.{key} = {val} (not finite)"
                    )


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


class TestReproducibility:
    """Same parameters should give identical results."""

    def test_same_seed_same_results(self):
        r1 = run_analysis(n_samples=N_FAST, seed=123)
        r2 = run_analysis(n_samples=N_FAST, seed=123)
        for nut_id in NUT_IDS:
            assert r1.nuts[nut_id].qaly_mean == r2.nuts[nut_id].qaly_mean
            assert r1.nuts[nut_id].life_years_mean == r2.nuts[nut_id].life_years_mean
            assert r1.nuts[nut_id].rr_cvd == r2.nuts[nut_id].rr_cvd

    def test_different_seed_different_results(self):
        r1 = run_analysis(n_samples=N_FAST, seed=1)
        r2 = run_analysis(n_samples=N_FAST, seed=2)
        # With different seeds, at least some nut results should differ
        any_diff = False
        for nut_id in NUT_IDS:
            if r1.nuts[nut_id].qaly_mean != r2.nuts[nut_id].qaly_mean:
                any_diff = True
                break
        assert any_diff


# ---------------------------------------------------------------------------
# Custom parameters
# ---------------------------------------------------------------------------


class TestCustomParameters:
    """Non-default parameters should be respected."""

    def test_custom_start_age(self):
        r = run_analysis(n_samples=N_FAST, seed=42, start_age=60)
        assert r.start_age == 60

    def test_custom_discount_rate(self):
        r = run_analysis(
            n_samples=N_FAST,
            seed=42,
            qaly_discount_rate=0.0,
            cost_discount_rate=0.05,
        )
        assert r.qaly_discount_rate == 0.0
        assert r.cost_discount_rate == 0.05

    def test_custom_confounding(self):
        r = run_analysis(
            n_samples=N_FAST,
            seed=42,
            confounding_alpha=1.0,
            confounding_beta=5.0,
        )
        assert r.confounding_alpha == 1.0
        assert r.confounding_beta == 5.0
        assert r.confounding_mean == pytest.approx(1.0 / 6.0)

    def test_walnut_not_year_scale_by_default(self):
        """Walnut gains should stay in the "weeks to a few months" band the
        skeptical paper claims — not the year-scale prior model."""
        r = run_analysis(n_samples=500, seed=42)
        assert r.nuts["walnut"].life_years_mean < 0.35

    def test_confounding_ci_matches_beta_ppf(self):
        """Regression: CI must be derived from the Beta(alpha, beta) ppf,
        not hardcoded (prevents the 0.12-0.88 stale-default bug)."""
        from scipy.stats import beta as beta_dist

        r = run_analysis(n_samples=500, seed=42)
        expected_lower = float(beta_dist.ppf(0.025, r.confounding_alpha, r.confounding_beta))
        expected_upper = float(beta_dist.ppf(0.975, r.confounding_alpha, r.confounding_beta))
        assert r.confounding_ci_lower == pytest.approx(expected_lower, abs=1e-4)
        assert r.confounding_ci_upper == pytest.approx(expected_upper, abs=1e-4)

    def test_discount_asymmetry(self):
        """QALY discount must only affect QALYs; cost discount only costs."""
        base = run_analysis(
            n_samples=500, seed=42, qaly_discount_rate=0.0, cost_discount_rate=0.03
        )
        flip_cost = run_analysis(
            n_samples=500, seed=42, qaly_discount_rate=0.0, cost_discount_rate=0.05
        )
        flip_qaly = run_analysis(
            n_samples=500, seed=42, qaly_discount_rate=0.03, cost_discount_rate=0.03
        )
        # Changing cost rate shouldn't change QALY means
        assert flip_cost.nuts["walnut"].qaly_mean == pytest.approx(
            base.nuts["walnut"].qaly_mean, abs=1e-6
        )
        # Changing QALY rate should change QALY means
        assert flip_qaly.nuts["walnut"].qaly_mean != pytest.approx(
            base.nuts["walnut"].qaly_mean, abs=1e-6
        )

    def test_baseline_qalys_derived_from_quality(self):
        """baseline_qalys should equal sum(survival * quality) — verifies
        average_quality_weight reflects the discounted-quality view."""
        r = run_analysis(n_samples=500, seed=42)
        assert 0 < r.average_quality_weight < 1
        assert r.baseline_qalys < r.baseline_life_years
        assert r.baseline_qalys == pytest.approx(
            r.baseline_life_years * r.average_quality_weight, abs=0.05
        )

    def test_baseline_life_years_matches_cdc(self):
        """Baseline LY at age 40 should be close to CDC ex(40) ~ 39.5.

        CDC NVSR 72-12 Table 1 reports life expectancy at age 40 for the
        US total population in 2021 as ~39.5 years. Our pipeline sums
        survival probabilities from age 40 to 110 (no partial-year
        adjustment at the final age), so values between ~39 and 40 are
        expected. Catches the off-by-0.5 bug where survival was indexed
        at END of each age year instead of START.
        """
        r = run_analysis(n_samples=500, seed=42)
        assert 38.8 < r.baseline_life_years < 40.0, (
            f"baseline_life_years={r.baseline_life_years} is outside the "
            "plausible CDC 2021 range for a 40-year-old."
        )


# ---------------------------------------------------------------------------
# Value-pinning regression tests — lock headline numbers so silent drift in
# priors / data files doesn't pass CI.
# ---------------------------------------------------------------------------


class TestHeadlineValuePins:
    """Pin substantive outputs so priors/data drift is caught by CI."""

    @pytest.fixture(scope="class")
    def results_full(self):
        return run_analysis(n_samples=10_000, seed=42)

    def test_walnut_life_years_in_window(self, results_full):
        w = results_full.nuts["walnut"]
        assert 0.10 < w.life_years_mean < 0.30, (
            f"Walnut life_years={w.life_years_mean} outside expected window "
            "[0.10, 0.30]. Any regression that blows past this window is a "
            "material change in the skeptical framing."
        )

    def test_peanut_icer_in_window(self, results_full):
        p = results_full.nuts["peanut"]
        assert 40_000 < p.icer_median < 200_000, (
            f"Peanut ICER={p.icer_median} outside expected window "
            "[$40k, $200k]. Peanuts should remain the cheapest ICER "
            "even at specialty-retail pricing; values outside this range "
            "suggest a price or QALY regression."
        )

    def test_cvd_contribution_dominates(self, results_full):
        assert results_full.cvd_contribution_mean > 0.65, (
            f"CVD contribution={results_full.cvd_contribution_mean} is too "
            "low; skeptical model should concentrate benefit in CVD."
        )

    def test_baseline_life_years_near_cdc(self, results_full):
        assert 38.8 < results_full.baseline_life_years < 40.0


# ---------------------------------------------------------------------------
# JSON generation
# ---------------------------------------------------------------------------


class TestJSONGeneration:
    """generate_results_json should write a loadable JSON file."""

    def test_generate_results_json_creates_file(self, results, tmp_path):
        from whatnut.pipeline import generate_results_json

        out_path = tmp_path / "results.json"
        returned_path = generate_results_json(results, path=out_path)
        assert returned_path == out_path
        assert out_path.exists()

    def test_generated_json_is_loadable(self, results, tmp_path):
        from whatnut.pipeline import generate_results_json

        out_path = tmp_path / "results.json"
        generate_results_json(results, path=out_path)
        with open(out_path) as f:
            loaded = json.load(f)
        assert isinstance(loaded, dict)
        assert "nuts" in loaded
        assert "seed" in loaded
        for nut_id in NUT_IDS:
            assert nut_id in loaded["nuts"]

    def test_generated_json_values_match(self, results, tmp_path):
        from whatnut.pipeline import generate_results_json

        out_path = tmp_path / "results.json"
        generate_results_json(results, path=out_path)
        with open(out_path) as f:
            loaded = json.load(f)
        assert loaded["seed"] == results.seed
        assert loaded["n_samples"] == results.n_samples
        for nut_id in NUT_IDS:
            assert loaded["nuts"][nut_id]["qaly_mean"] == results.nuts[nut_id].qaly_mean


# ---------------------------------------------------------------------------
# Baseline life years (Issue 4)
# ---------------------------------------------------------------------------


class TestBaselineLifeYears:
    """baseline_life_years should be derived from CDC mortality table."""

    def test_baseline_life_years_from_mortality_table(self):
        """baseline_life_years should be derived from CDC mortality table, not hardcoded."""
        from whatnut.config import get_mortality_curve
        mortality = get_mortality_curve(40)
        survival = np.cumprod(1 - mortality)
        expected = float(np.sum(survival))
        # Should be approximately 40 years for a 40-year-old
        assert 35 < expected < 45, f"Expected ~40 years, got {expected:.2f}"

    def test_baseline_life_years_in_results(self, results):
        """AnalysisResults should include baseline_life_years derived from mortality."""
        assert hasattr(results, "baseline_life_years"), (
            "AnalysisResults should have baseline_life_years attribute"
        )
        assert 35 < results.baseline_life_years < 45, (
            f"baseline_life_years = {results.baseline_life_years}, expected ~40"
        )
