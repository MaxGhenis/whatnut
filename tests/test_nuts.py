"""Tests for nut data module.

TDD: Define expected nut properties and evidence linkage.
"""

import pytest
from whatnut.nuts import NUTS, Nut, get_nut


class TestNutStructure:
    """Each nut must have required properties."""

    def test_nuts_not_empty(self):
        assert len(NUTS) >= 7  # At least: walnut, almond, macadamia, pistachio, peanut, pecan, cashew

    def test_each_nut_has_required_fields(self):
        required = ["id", "name", "nutrients", "evidence_sources", "adjustment_factor"]
        for nut in NUTS:
            for field in required:
                assert hasattr(nut, field), f"Nut {nut.id} missing {field}"


class TestNutNutrients:
    """Nutrient data must be sourced and validated."""

    def test_nutrients_have_usda_source(self):
        for nut in NUTS:
            assert "usda_fdc" in nut.nutrients.sources, f"{nut.id} nutrients not USDA sourced"

    def test_nutrients_per_100g(self):
        """All nutrient values should be per 100g for consistency."""
        for nut in NUTS:
            assert nut.nutrients.serving_size_g == 100

    def test_macadamia_protein_lowest(self):
        """Macadamias have lowest protein per 100g."""
        mac = get_nut("macadamia")
        for nut in NUTS:
            if nut.id != "macadamia":
                assert mac.nutrients.protein_g <= nut.nutrients.protein_g

    def test_macadamia_omega_ratio_good(self):
        """Macadamias have omega-6:3 ratio around 6:1."""
        mac = get_nut("macadamia")
        ratio = mac.nutrients.omega6_g / mac.nutrients.omega3_g
        assert 4 < ratio < 8, f"Macadamia omega ratio {ratio} not ~6:1"

    def test_almond_omega_ratio_high(self):
        """Almonds have very high omega-6:3 ratio (>1000:1)."""
        almond = get_nut("almond")
        ratio = almond.nutrients.omega6_g / almond.nutrients.omega3_g
        assert ratio > 500, f"Almond omega ratio {ratio} should be >500:1"


class TestNutEvidence:
    """Each nut's evidence must be properly linked."""

    def test_walnut_has_strong_evidence(self):
        walnut = get_nut("walnut")
        # Walnuts have PREDIMED, WAHA trials
        assert walnut.evidence_strength == "strong"
        assert len(walnut.evidence_sources) >= 2

    def test_macadamia_has_limited_evidence(self):
        mac = get_nut("macadamia")
        assert mac.evidence_strength in ["limited", "moderate"]

    def test_evidence_sources_exist(self):
        """All referenced sources must exist in SOURCES."""
        from whatnut.evidence import get_source
        for nut in NUTS:
            for source_id in nut.evidence_sources:
                source = get_source(source_id)
                assert source is not None, f"Nut {nut.id} references unknown source {source_id}"


class TestAdjustmentFactors:
    """Adjustment factors must be justified and bounded."""

    def test_adjustment_factors_reasonable(self):
        """All adjustment factors should be within plausible range."""
        for nut in NUTS:
            af = nut.adjustment_factor
            assert 0.8 < af.mean < 1.3, f"{nut.id} adjustment mean {af.mean} out of range"
            assert 0.01 < af.sd < 0.3, f"{nut.id} adjustment SD {af.sd} out of range"

    def test_walnut_adjustment_highest(self):
        """Walnuts should have highest mean adjustment (best evidence + omega-3)."""
        walnut = get_nut("walnut")
        for nut in NUTS:
            if nut.id != "walnut":
                assert walnut.adjustment_factor.mean >= nut.adjustment_factor.mean

    def test_low_evidence_higher_uncertainty(self):
        """Nuts with limited evidence should have higher SD."""
        walnut = get_nut("walnut")
        mac = get_nut("macadamia")
        assert mac.adjustment_factor.sd > walnut.adjustment_factor.sd
