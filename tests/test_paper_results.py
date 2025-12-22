"""Tests for paper_results module - ensures all inline expressions work."""

import pytest
from whatnut.paper_results import r, PaperResults, NutResult


class TestPaperResultsImport:
    """Test that the paper_results module imports correctly."""

    def test_r_singleton_exists(self):
        """The 'r' singleton must exist for paper imports."""
        assert r is not None
        assert isinstance(r, PaperResults)


class TestNutAccessors:
    """Test all nut accessors used in {eval} expressions."""

    @pytest.mark.parametrize(
        "nut_name",
        ["walnut", "almond", "peanut", "pecan", "macadamia", "cashew", "pistachio"],
    )
    def test_nut_accessor_exists(self, nut_name):
        """Each nut must have an accessor property."""
        nut = getattr(r, nut_name)
        assert isinstance(nut, NutResult)

    @pytest.mark.parametrize(
        "nut_name",
        ["walnut", "almond", "peanut", "pecan", "macadamia", "cashew", "pistachio"],
    )
    def test_nut_qaly_format(self, nut_name):
        """QALY must format as string for inline use."""
        nut = getattr(r, nut_name)
        qaly = nut.qaly
        assert isinstance(qaly, str)
        # Should be a decimal number like "0.20"
        float(qaly)  # Should not raise

    @pytest.mark.parametrize(
        "nut_name",
        ["walnut", "almond", "peanut", "pecan", "macadamia", "cashew", "pistachio"],
    )
    def test_nut_qaly_ci_format(self, nut_name):
        """QALY CI must format as bracketed range."""
        nut = getattr(r, nut_name)
        ci = nut.qaly_ci
        assert isinstance(ci, str)
        assert ci.startswith("[")
        assert ci.endswith("]")
        assert "," in ci

    @pytest.mark.parametrize(
        "nut_name",
        ["walnut", "almond", "peanut", "pecan", "macadamia", "cashew", "pistachio"],
    )
    def test_nut_icer_format(self, nut_name):
        """ICER must format with dollar sign."""
        nut = getattr(r, nut_name)
        icer = nut.icer_fmt
        assert isinstance(icer, str)
        assert icer.startswith("$")


class TestDerivedValues:
    """Test derived values used in paper inline expressions."""

    def test_cvd_contribution(self):
        """CVD contribution percentage must be integer."""
        assert isinstance(r.cvd_contribution, int)
        assert 0 <= r.cvd_contribution <= 100

    def test_cvd_effect_range(self):
        """CVD effect range must be formatted string."""
        range_str = r.cvd_effect_range
        assert isinstance(range_str, str)
        assert "-" in range_str
        # Should be like "0.83-0.89"
        parts = range_str.split("-")
        assert len(parts) == 2
        float(parts[0])
        float(parts[1])

    def test_cancer_effect_range(self):
        """Cancer effect range must be formatted string."""
        range_str = r.cancer_effect_range
        assert isinstance(range_str, str)
        assert "-" in range_str

    def test_allergy_prevalence(self):
        """Allergy prevalence bounds must be numeric."""
        assert isinstance(r.allergy_prevalence_lower, (int, float))
        assert isinstance(r.allergy_prevalence_upper, (int, float))
        assert r.allergy_prevalence_lower < r.allergy_prevalence_upper


class TestTableGenerators:
    """Test table generation methods."""

    def test_table_3_diagnostics(self):
        """MCMC diagnostics table must be valid markdown."""
        table = r.table_3_diagnostics()
        assert isinstance(table, str)
        assert "|" in table
        assert "R-hat" in table

    def test_table_3_qalys(self):
        """QALY table must be valid markdown."""
        table = r.table_3_qalys()
        assert isinstance(table, str)
        assert "|" in table
        assert "QALY" in table

    def test_table_4_pathway_rrs(self):
        """Pathway RR table must be valid markdown."""
        table = r.table_4_pathway_rrs()
        assert isinstance(table, str)
        assert "|" in table
        assert "CVD" in table


class TestValueRanges:
    """Test that values are in plausible ranges."""

    def test_qaly_values_positive(self):
        """Mean QALY should be positive for all nuts."""
        for nut in r.nuts.values():
            assert nut.qaly_mean > 0, f"{nut.name} has non-positive QALY"

    def test_qaly_values_reasonable(self):
        """QALY gains should be less than 5 years (plausibility check)."""
        for nut in r.nuts.values():
            assert nut.qaly_mean < 5, f"{nut.name} has implausibly high QALY"

    def test_icer_values_positive(self):
        """ICER should be positive for all nuts."""
        for nut in r.nuts.values():
            assert nut.icer > 0, f"{nut.name} has non-positive ICER"

    def test_probability_bounds(self):
        """P(positive) should be between 0 and 1."""
        for nut in r.nuts.values():
            assert 0 <= nut.p_positive <= 1, f"{nut.name} has invalid probability"
