"""Tests for the results module (loads from generated data/results.json).

Covers loading of results.json, NutResult properties, PaperResults
range properties, table generators, and pathway RRs.
"""

import pytest

from whatnut.config import NUT_IDS
from whatnut.results import (
    RESULTS_PATH,
    NutResult,
    PaperResults,
    PathwayRR,
    get_results,
    r,
)


# ---------------------------------------------------------------------------
# Results file existence and loading
# ---------------------------------------------------------------------------


class TestResultsLoading:
    """results.json should exist and load successfully."""

    def test_results_json_exists(self):
        assert RESULTS_PATH.exists(), f"Missing: {RESULTS_PATH}"

    def test_results_json_is_file(self):
        assert RESULTS_PATH.is_file()

    def test_get_results_returns_paper_results(self):
        results = get_results()
        assert isinstance(results, PaperResults)

    def test_lazy_proxy_works(self):
        """The module-level `r` object should proxy to PaperResults."""
        assert r.seed is not None
        assert r.n_samples > 0


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------


class TestResultParameters:
    """Loaded results should have correct parameters."""

    @pytest.fixture
    def results(self) -> PaperResults:
        return get_results()

    def test_seed(self, results):
        assert results.seed == 42

    def test_n_samples(self, results):
        assert results.n_samples == 10_000

    def test_start_age(self, results):
        assert results.start_age == 40

    def test_discount_rates(self, results):
        assert results.qaly_discount_rate == 0.0
        assert results.cost_discount_rate == 0.03

    def test_confounding(self, results):
        assert results.confounding_alpha == pytest.approx(1.5)
        assert results.confounding_beta == pytest.approx(6.0)
        assert results.confounding_mean == pytest.approx(0.2)


# ---------------------------------------------------------------------------
# NutResult properties
# ---------------------------------------------------------------------------


class TestNutResultProperties:
    """NutResult formatted properties should return correct strings."""

    def test_walnut_qaly_returns_string(self):
        assert isinstance(r.walnut.qaly, str)
        # Should be a number formatted to 2 decimal places
        float(r.walnut.qaly)  # Should not raise

    def test_walnut_qaly_ci_format(self):
        ci = r.walnut.qaly_ci
        assert ci.startswith("[")
        assert ci.endswith("]")
        assert "," in ci

    def test_walnut_icer_fmt(self):
        icer_str = r.walnut.icer_fmt
        assert icer_str.startswith("$")
        # Remove $ and commas, should be a valid number
        num_str = icer_str.replace("$", "").replace(",", "")
        float(num_str)  # Should not raise

    def test_walnut_icer_ci_fmt(self):
        ci = r.walnut.icer_ci_fmt
        assert ci.startswith("[")
        assert ci.endswith("]")

    def test_life_years_fmt(self):
        ly = r.walnut.life_years_fmt
        assert isinstance(ly, str)
        float(ly)  # Should not raise

    def test_months_property(self):
        assert r.walnut.months == pytest.approx(r.walnut.life_years * 12)

    def test_months_fmt(self):
        m = r.walnut.months_fmt
        assert isinstance(m, str)
        float(m)

    def test_qaly_undiscounted_property(self):
        assert r.walnut.qaly_undiscounted == r.walnut.qaly_undiscounted_mean

    def test_qaly_undiscounted_fmt(self):
        s = r.walnut.qaly_undiscounted_fmt
        assert isinstance(s, str)
        float(s)


# ---------------------------------------------------------------------------
# PaperResults convenience accessors
# ---------------------------------------------------------------------------


class TestConvenienceAccessors:
    """Named nut accessors should return correct NutResult."""

    def test_walnut_accessor(self):
        assert isinstance(r.walnut, NutResult)
        assert r.walnut.name == "Walnut"

    def test_almond_accessor(self):
        assert isinstance(r.almond, NutResult)
        assert r.almond.name == "Almond"

    def test_peanut_accessor(self):
        assert isinstance(r.peanut, NutResult)
        assert r.peanut.name == "Peanut"

    def test_pecan_accessor(self):
        assert isinstance(r.pecan, NutResult)

    def test_macadamia_accessor(self):
        assert isinstance(r.macadamia, NutResult)

    def test_cashew_accessor(self):
        assert isinstance(r.cashew, NutResult)

    def test_pistachio_accessor(self):
        assert isinstance(r.pistachio, NutResult)


# ---------------------------------------------------------------------------
# Range properties
# ---------------------------------------------------------------------------


class TestRangeProperties:
    """Range properties should return correctly formatted strings."""

    def test_qaly_range_format(self):
        qr = r.qaly_range
        assert isinstance(qr, str)
        assert "-" in qr
        parts = qr.split("-")
        assert len(parts) == 2
        lo, hi = float(parts[0]), float(parts[1])
        assert lo <= hi

    def test_qaly_undiscounted_range(self):
        qr = r.qaly_undiscounted_range
        assert isinstance(qr, str)
        assert "-" in qr

    def test_icer_range(self):
        ir = r.icer_range
        assert isinstance(ir, str)
        assert "$" in ir

    def test_life_years_range(self):
        lr = r.life_years_range
        assert isinstance(lr, str)
        assert "-" in lr

    def test_months_range(self):
        mr = r.months_range
        assert isinstance(mr, str)
        assert "-" in mr

    def test_cvd_effect_range(self):
        er = r.cvd_effect_range
        assert isinstance(er, str)
        assert "-" in er

    def test_cancer_effect_range(self):
        er = r.cancer_effect_range
        assert isinstance(er, str)


# ---------------------------------------------------------------------------
# Table generators
# ---------------------------------------------------------------------------


class TestTableGenerators:
    """Table generators should produce valid markdown tables."""

    def test_table_3_qalys_is_html(self):
        table = r.table_3_qalys()
        assert isinstance(table, str)
        assert table.startswith("<table>")
        assert "<thead>" in table
        assert "<tbody>" in table

    def test_table_3_contains_all_nuts(self):
        table = r.table_3_qalys()
        for nut_id in NUT_IDS:
            assert nut_id.capitalize() in table, (
                f"Missing {nut_id.capitalize()} in table 3"
            )

    def test_table_3_has_columns(self):
        table = r.table_3_qalys()
        assert "Life Years" in table
        assert "QALY" in table
        assert "ICER" in table

    def test_table_4_pathway_rrs_is_html(self):
        table = r.table_4_pathway_rrs()
        assert isinstance(table, str)
        assert table.startswith("<table>")
        assert "<thead>" in table
        assert "<tbody>" in table

    def test_table_4_contains_all_nuts(self):
        table = r.table_4_pathway_rrs()
        for nut_id in NUT_IDS:
            assert nut_id.capitalize() in table

    def test_table_4_has_pathway_columns(self):
        table = r.table_4_pathway_rrs()
        assert "CVD" in table
        assert "Cancer" in table
        assert "Other" in table


# ---------------------------------------------------------------------------
# Pathway RRs
# ---------------------------------------------------------------------------


class TestPathwayRRs:
    """Pathway RRs should be populated for all nuts."""

    @pytest.fixture
    def results(self) -> PaperResults:
        return get_results()

    def test_pathway_rrs_dict_populated(self, results):
        assert len(results.pathway_rrs) == len(NUT_IDS)

    def test_all_nuts_have_pathway_rrs(self, results):
        for nut_id in NUT_IDS:
            assert nut_id in results.pathway_rrs

    def test_pathway_rr_structure(self, results):
        for nut_id, prr in results.pathway_rrs.items():
            assert isinstance(prr, PathwayRR)
            assert prr.cvd > 0
            assert prr.cancer > 0
            assert prr.other > 0

    def test_pathway_rrs_in_sensible_range(self, results):
        for nut_id, prr in results.pathway_rrs.items():
            assert 0.5 <= prr.cvd <= 1.2, f"{nut_id} CVD RR = {prr.cvd}"
            assert 0.5 <= prr.cancer <= 1.2, f"{nut_id} cancer RR = {prr.cancer}"
            assert 0.5 <= prr.other <= 1.2, f"{nut_id} other RR = {prr.other}"

    def test_pathway_rrs_match_nut_results(self, results):
        """PathwayRR values should match the corresponding NutResult values."""
        for nut_id in NUT_IDS:
            prr = results.pathway_rrs[nut_id]
            nr = results.nuts[nut_id]
            assert prr.cvd == nr.rr_cvd
            assert prr.cancer == nr.rr_cancer
            assert prr.other == nr.rr_other


# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------


class TestDerivedConstants:
    """PaperResults should have correctly computed derived values."""

    @pytest.fixture
    def results(self) -> PaperResults:
        return get_results()

    def test_nice_lower_usd(self, results):
        expected = int(results.nice_lower_gbp * results.gbp_usd_rate)
        assert results.nice_lower_usd == expected

    def test_nice_upper_usd(self, results):
        expected = int(results.nice_upper_gbp * results.gbp_usd_rate)
        assert results.nice_upper_usd == expected

    def test_pathway_contributions_are_integers(self, results):
        assert isinstance(results.cvd_contribution, int)
        assert isinstance(results.cancer_contribution, int)
        assert isinstance(results.other_contribution, int)
