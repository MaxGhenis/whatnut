"""Tests for the config module: YAML loading, dataclasses, validation.

Covers YAML loading for all 5 data files, typed accessors, nutrient matrix,
mortality/quality curve interpolation, cause fractions, and validation.
"""

import numpy as np
import pytest

from whatnut.config import (
    DATA_DIR,
    NUT_IDS,
    NUTRIENTS,
    PATHWAYS,
    ConfoundingPrior,
    NutProfile,
    NutrientPrior,
    get_all_nuts,
    get_cause_fractions,
    get_confounding_prior,
    get_evidence_registry,
    get_mortality_curve,
    get_mortality_rate,
    get_nut,
    get_nutrient_matrix,
    get_nutrient_prior,
    get_pathway_priors,
    get_quality_curve,
    get_quality_weight,
    load_cause_fractions,
    load_mortality,
    load_nuts_yaml,
    load_priors,
    load_quality_weights,
    validate,
)

# ---------------------------------------------------------------------------
# YAML file loading
# ---------------------------------------------------------------------------


class TestYAMLLoading:
    """All 5 YAML data files should load without errors."""

    def test_priors_yaml_loads(self):
        data = load_priors()
        assert isinstance(data, dict)
        assert "cvd" in data
        assert "cancer" in data
        assert "other" in data
        assert "confounding" in data
        assert "substitution_contrasts" in data

    def test_nuts_yaml_loads(self):
        data = load_nuts_yaml()
        assert isinstance(data, dict)
        for nut_id in NUT_IDS:
            assert nut_id in data, f"Missing nut: {nut_id}"

    def test_mortality_yaml_loads(self):
        data = load_mortality()
        assert isinstance(data, dict)
        assert "rates" in data
        assert len(data["rates"]) > 0

    def test_quality_weights_yaml_loads(self):
        data = load_quality_weights()
        assert isinstance(data, dict)
        assert "weights" in data
        assert len(data["weights"]) > 0

    def test_cause_fractions_yaml_loads(self):
        data = load_cause_fractions()
        assert isinstance(data, dict)
        assert "fractions" in data
        assert len(data["fractions"]) > 0

    def test_data_dir_exists(self):
        assert DATA_DIR.exists()
        assert DATA_DIR.is_dir()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


class TestValidation:
    """validate() should return an empty error list for the shipped data."""

    def test_validate_passes_with_no_errors(self):
        errors = validate()
        assert errors == [], f"Validation errors: {errors}"


# ---------------------------------------------------------------------------
# Nut profiles
# ---------------------------------------------------------------------------


class TestNutProfiles:
    """get_nut should return correctly-typed NutProfile objects."""

    @pytest.fixture
    def walnut(self) -> NutProfile:
        return get_nut("walnut")

    def test_get_nut_returns_nut_profile(self, walnut):
        assert isinstance(walnut, NutProfile)

    def test_walnut_id(self, walnut):
        assert walnut.id == "walnut"

    def test_walnut_has_all_model_nutrients(self, walnut):
        for nutrient in NUTRIENTS:
            assert nutrient in walnut.nutrients, f"Missing nutrient: {nutrient}"

    def test_walnut_ala_omega3_is_highest(self):
        """Walnuts have the highest ALA omega-3 of all nuts."""
        walnut = get_nut("walnut")
        for nut_id in NUT_IDS:
            if nut_id == "walnut":
                continue
            other = get_nut(nut_id)
            assert walnut.nutrients["ala_omega3"] > other.nutrients["ala_omega3"], (
                f"Walnut ALA ({walnut.nutrients['ala_omega3']}) should be "
                f"greater than {nut_id} ALA ({other.nutrients['ala_omega3']})"
            )

    def test_nut_profiles_have_no_hand_curated_mortality_adjustment(self, walnut):
        assert not hasattr(walnut, "pathway_adjustments")

    def test_walnut_annual_cost(self, walnut):
        expected = walnut.cost_per_kg_usd * 10.22
        assert walnut.annual_cost == pytest.approx(expected, rel=1e-6)

    def test_get_nut_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown nut"):
            get_nut("brazil")

    def test_get_all_nuts_returns_all(self):
        nuts = get_all_nuts()
        assert len(nuts) == len(NUT_IDS)
        returned_ids = {n.id for n in nuts}
        assert returned_ids == set(NUT_IDS)

    def test_all_nuts_have_positive_cost(self):
        for nut_id in NUT_IDS:
            nut = get_nut(nut_id)
            assert nut.cost_per_kg_usd > 0
            assert nut.annual_cost > 0

    def test_nut_profiles_do_not_encode_evidence_tiers(self):
        for nut_id in NUT_IDS:
            nut = get_nut(nut_id)
            assert not hasattr(nut, "evidence")


# ---------------------------------------------------------------------------
# Nutrient matrix
# ---------------------------------------------------------------------------


class TestNutrientMatrix:
    """get_nutrient_matrix should build correct (n_nuts x n_nutrients) arrays."""

    def test_default_shape(self):
        X = get_nutrient_matrix()
        assert X.shape == (len(NUT_IDS), len(NUTRIENTS))

    def test_custom_nut_ids_shape(self):
        X = get_nutrient_matrix(["walnut", "almond"])
        assert X.shape == (2, len(NUTRIENTS))

    def test_values_match_nut_profiles(self):
        X = get_nutrient_matrix()
        for i, nut_id in enumerate(NUT_IDS):
            nut = get_nut(nut_id)
            for j, nutrient in enumerate(NUTRIENTS):
                assert X[i, j] == pytest.approx(nut.nutrients[nutrient], abs=1e-10), (
                    f"Mismatch at {nut_id}/{nutrient}: "
                    f"matrix={X[i, j]}, profile={nut.nutrients[nutrient]}"
                )

    def test_no_negative_values_except_omega6(self):
        """All nutrient values should be non-negative (omega6 could be edge case)."""
        X = get_nutrient_matrix()
        for i, nut_id in enumerate(NUT_IDS):
            for j, nutrient in enumerate(NUTRIENTS):
                if nutrient != "omega6":
                    assert X[i, j] >= 0, f"{nut_id}/{nutrient} is negative: {X[i, j]}"

    def test_walnut_ala_column_value(self):
        """Spot check: walnut ALA should be ~2.5 g/28g.

        USDA SR Legacy reports 9.08 g per 100 g (walnut FDC 170187 PUFA
        18:3), which scales to 2.542 g per 28 g serving.
        """
        X = get_nutrient_matrix()
        walnut_idx = NUT_IDS.index("walnut")
        ala_idx = NUTRIENTS.index("ala_omega3")
        assert X[walnut_idx, ala_idx] == pytest.approx(2.542, abs=0.01)


# ---------------------------------------------------------------------------
# Priors
# ---------------------------------------------------------------------------


class TestPriors:
    """Typed prior accessors should return correct dataclass instances."""

    def test_nutrient_prior_structure(self):
        prior = get_nutrient_prior("cvd", "ala_omega3")
        assert isinstance(prior, NutrientPrior)
        assert prior.mean < 0  # Protective effect
        assert prior.sd > 0
        assert prior.unit == "g"
        assert prior.outcome == "CVD mortality"
        assert prior.source_url
        assert prior.applicable_actions == ("gross_addition",)

    def test_pathway_priors_complete(self):
        for pathway in PATHWAYS:
            priors = get_pathway_priors(pathway)
            assert len(priors) == len(NUTRIENTS)
            for nutrient in NUTRIENTS:
                assert nutrient in priors
                assert isinstance(priors[nutrient], NutrientPrior)

    def test_confounding_prior(self):
        prior = get_confounding_prior()
        assert isinstance(prior, ConfoundingPrior)
        assert prior.alpha == pytest.approx(1.5)
        assert prior.beta == pytest.approx(6.0)
        assert prior.mean == pytest.approx(0.20)
        assert 0 < prior.ci_lower < prior.ci_upper < 1

    def test_substitution_only_fats_are_inactive_for_gross_addition(self):
        for nutrient in ("omega6", "saturated_fat"):
            prior = get_nutrient_prior("cvd", nutrient)
            assert prior.mean == 0
            assert prior.sd == 0
            assert prior.applicable_actions == ()

    def test_evidence_registry_classifies_every_coefficient(self):
        registry = get_evidence_registry()
        active = registry["active_coefficients"]
        excluded = registry["structurally_excluded_coefficients"]

        assert len(active) == 4
        assert len(excluded) == len(PATHWAYS) * len(NUTRIENTS) - 4
        assert {(item["pathway"], item["nutrient"]) for item in active} == {
            ("cvd", "ala_omega3"),
            ("cvd", "fiber"),
            ("cvd", "magnesium"),
            ("cancer", "fiber"),
        }
        assert registry["deferred_substitution_contrasts"]


# ---------------------------------------------------------------------------
# Mortality curve interpolation
# ---------------------------------------------------------------------------


class TestMortality:
    """Mortality rates and curve interpolation."""

    def test_mortality_at_known_age(self):
        """Rate at age 40 should match the CDC NVSR 72-12 Table 1 value.

        Exact qx(40) for the US total population in 2021 is 0.002916
        (Arias & Xu 2023). This replaces a prior hand-rounded value of
        0.00193 that diverged ~33% from the cited source.
        """
        rate = get_mortality_rate(40)
        assert rate == pytest.approx(0.002916, rel=0.01)

    def test_complete_single_age_table_is_retained(self):
        rates = load_mortality()["rates"]
        assert set(rates) == set(range(101))
        assert rates[41] == pytest.approx(0.003078)
        assert rates[99] == pytest.approx(0.323082)
        assert rates[100] == 1.0

    def test_mortality_increases_with_age(self):
        curve = get_mortality_curve(40, 100)
        for i in range(1, len(curve)):
            assert curve[i] >= curve[i - 1], f"Mortality decreased at age {40 + i}"

    def test_mortality_in_valid_range(self):
        curve = get_mortality_curve(0, 100)
        assert np.all(curve >= 0)
        assert np.all(curve <= 1)

    def test_mortality_curve_length(self):
        curve = get_mortality_curve(40)
        assert len(curve) == 61  # ages 40..100 inclusive

    def test_adjacent_published_single_age_values(self):
        """Adjacent adult ages come directly from the CDC table."""
        rate_40 = get_mortality_rate(40)
        rate_42 = get_mortality_rate(42)
        rate_45 = get_mortality_rate(45)
        assert rate_40 < rate_42 < rate_45

    def test_extrapolation_beyond_terminal_age_is_rejected(self):
        with pytest.raises(ValueError, match="between 0 and 100"):
            get_mortality_rate(105)


# ---------------------------------------------------------------------------
# Quality-of-life curve interpolation
# ---------------------------------------------------------------------------


class TestQualityCurve:
    """Quality weight interpolation and curve generation."""

    def test_quality_at_known_age(self):
        weight = get_quality_weight(40)
        assert weight == pytest.approx(0.89, rel=0.01)

    def test_quality_decreases_with_age(self):
        curve = get_quality_curve(40, 100)
        for i in range(1, len(curve)):
            assert curve[i] <= curve[i - 1], f"Quality increased at age {40 + i}"

    def test_quality_in_valid_range(self):
        curve = get_quality_curve(20, 100)
        assert np.all(curve > 0)
        assert np.all(curve <= 1)

    def test_quality_curve_length(self):
        curve = get_quality_curve(40)
        assert len(curve) == 61

    def test_interpolation_between_ages(self):
        w_40 = get_quality_weight(40)
        w_42 = get_quality_weight(42)
        w_45 = get_quality_weight(45)
        assert w_45 < w_42 < w_40

    def test_extrapolation_has_floor(self):
        """Very old ages should not drop below floor (0.3)."""
        weight = get_quality_weight(120)
        assert weight >= 0.3


# ---------------------------------------------------------------------------
# Cause fractions
# ---------------------------------------------------------------------------


class TestCauseFractions:
    """Cause-of-death fractions should be valid proportions summing to ~1."""

    def test_fractions_sum_to_one_at_known_ages(self):
        raw = load_cause_fractions()["fractions"]
        for age, fracs in raw.items():
            total = fracs["cvd"] + fracs["cancer"] + fracs["other"]
            assert total == pytest.approx(1.0, abs=0.01), (
                f"Cause fractions at age {age} sum to {total}"
            )

    def test_fractions_sum_to_approximately_one_interpolated(self):
        """Interpolated fractions should also sum to ~1."""
        for age in [35, 42, 55, 67, 85]:
            cvd, cancer, other = get_cause_fractions(age)
            total = cvd + cancer + other
            assert total == pytest.approx(1.0, abs=0.02), (
                f"Interpolated fractions at age {age} sum to {total}"
            )

    def test_all_fractions_non_negative(self):
        for age in range(20, 101):
            cvd, cancer, other = get_cause_fractions(age)
            assert cvd >= 0
            assert cancer >= 0
            assert other >= 0

    def test_cvd_increases_with_age(self):
        """CVD fraction should generally increase with age."""
        cvd_40 = get_cause_fractions(40)[0]
        cvd_80 = get_cause_fractions(80)[0]
        assert cvd_80 > cvd_40

    def test_returns_tuple_of_three(self):
        result = get_cause_fractions(50)
        assert isinstance(result, tuple)
        assert len(result) == 3


# ---------------------------------------------------------------------------
# Unit consistency (Issue 1: magnesium/phytosterol 10x unit error)
# ---------------------------------------------------------------------------


class TestUnitConsistency:
    """Nutrient priors should produce plausible per-serving contributions."""

    def test_magnesium_uses_identified_cvd_mortality_estimate(self):
        """An imprecise estimate stays continuous rather than being zeroed by p-value."""
        prior = get_nutrient_prior("cvd", "magnesium")
        assert prior.mean == pytest.approx(-0.000304592)
        assert prior.sd == pytest.approx(0.000183229)
        assert prior.applicable_actions == ("gross_addition",)

    def test_phytosterol_contribution_plausible(self):
        """Phytosterol contribution to log-RR should be small (< 0.10 per serving)."""
        prior = get_nutrient_prior("cvd", "phytosterols")
        peanut = get_nut("peanut")
        ps = peanut.nutrients["phytosterols"]  # ~62 mg
        contribution = abs(prior.mean * ps)
        assert contribution < 0.10, (
            f"Phytosterol contribution {contribution:.4f} too large (unit error?)"
        )

    def test_total_nutrient_log_rr_plausible(self):
        """Total nutrient-predicted log-RR should be in [-0.5, 0] for CVD."""
        X = get_nutrient_matrix()
        priors = get_pathway_priors("cvd")
        mu = np.array([priors[n].mean for n in NUTRIENTS])
        log_rrs = X @ mu
        for i, nid in enumerate(NUT_IDS):
            assert -0.5 < log_rrs[i] < 0, (
                f"{nid} CVD log-RR {log_rrs[i]:.3f} outside [-0.5, 0]"
            )


# ---------------------------------------------------------------------------
# Scientific parameter accuracy (fixes for methodology review)
# ---------------------------------------------------------------------------


class TestScientificParameters:
    """Verify corrected scientific parameters from methodology review."""

    def test_ala_cvd_prior_mean_is_minus_005(self):
        """Fix 1: ALA CVD prior should be -0.05 (Naghshi 2021: RR 0.95/g)."""
        prior = get_nutrient_prior("cvd", "ala_omega3")
        assert prior.mean == pytest.approx(-0.05, abs=0.005), (
            f"ALA CVD prior mean is {prior.mean}, expected -0.05 "
            "(Naghshi 2021: RR 0.95 per 1g/day, ln(0.95)=-0.051)"
        )

    def test_ala_cancer_prior_mean_is_zero(self):
        """Fix 2: ALA cancer prior should be 0.0 (non-significant per-gram)."""
        prior = get_nutrient_prior("cancer", "ala_omega3")
        assert prior.mean == pytest.approx(0.0, abs=0.005), (
            f"ALA cancer prior mean is {prior.mean}, expected 0.0 "
            "(Naghshi 2021: per-gram RR 1.03, non-significant)"
        )

    def test_phytosterol_cvd_contribution_small(self):
        """Fix 3: Phytosterol contribution for pistachio (61mg) should be < 0.01."""
        prior = get_nutrient_prior("cvd", "phytosterols")
        pistachio = get_nut("pistachio")
        ps = pistachio.nutrients["phytosterols"]  # 61 mg
        contribution = abs(prior.mean * ps)
        assert contribution < 0.01, (
            f"Phytosterol CVD contribution for pistachio = {contribution:.4f}, "
            "expected < 0.01 (per-mg coefficient should be ~-0.0001)"
        )

    def test_phytosterol_unit_is_mg(self):
        """Fix 3: Phytosterol unit should be 'mg' (not 'mg (effect per 10mg)')."""
        prior = get_nutrient_prior("cvd", "phytosterols")
        assert prior.unit == "mg", f"Phytosterol unit is '{prior.unit}', expected 'mg'"

    def test_magnesium_cvd_prior_refuses_outcome_mismatch(self):
        """Bagheri's CVD-mortality estimate replaces Fang's stroke estimate."""
        prior = get_nutrient_prior("cvd", "magnesium")
        assert prior.mean == pytest.approx(-0.000304592)
        assert prior.sd == pytest.approx(0.000183229)
        assert prior.outcome == "CVD mortality"
        assert "Bagheri 2021" in prior.source

    def test_magnesium_unit_is_mg(self):
        """Fix 4: Magnesium unit should be 'mg' (not 'mg (effect per 10mg)')."""
        prior = get_nutrient_prior("cvd", "magnesium")
        assert prior.unit == "mg", f"Magnesium unit is '{prior.unit}', expected 'mg'"

    def test_fiber_priors_are_cause_specific_mortality_estimates(self):
        cvd = get_nutrient_prior("cvd", "fiber")
        cancer = get_nutrient_prior("cancer", "fiber")
        assert cvd.mean == pytest.approx(-0.0139262)
        assert cvd.sd == pytest.approx(0.00204191)
        assert cancer.mean == pytest.approx(-0.00943107)
        assert cancer.sd == pytest.approx(0.00140976)


# ---------------------------------------------------------------------------
# Version consistency (Issue 3)
# ---------------------------------------------------------------------------


def test_version_matches_pyproject():
    """__init__.__version__ should match pyproject.toml version."""
    import sys

    import pytest

    if sys.version_info < (3, 11):
        pytest.skip("tomllib requires Python 3.11+")
    from pathlib import Path

    import tomllib

    import whatnut

    pyproject = Path(__file__).parent.parent / "pyproject.toml"
    with open(pyproject, "rb") as f:
        data = tomllib.load(f)
    assert whatnut.__version__ == data["project"]["version"]
