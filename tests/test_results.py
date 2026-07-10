"""Tests for the results module (loads from generated data/results.json).

Covers loading of results.json, NutResult properties, PaperResults
range properties, table generators, and pathway RRs.
"""

from copy import deepcopy

import pytest

from whatnut.artifact import RESULTS_SCHEMA_VERSION
from whatnut.config import NUT_IDS
from whatnut.pipeline import generate_results_json, run_analysis
from whatnut.results import (
    RESULTS_PATH,
    NutResult,
    PaperResults,
    PathwayRR,
    get_results,
    load_results,
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

    def test_schema_version(self, results):
        assert results.schema_version == RESULTS_SCHEMA_VERSION

    def test_n_samples(self, results):
        assert results.n_samples == 10_000

    def test_start_age(self, results):
        assert results.start_age == 40

    def test_discount_rates(self, results):
        assert results.qaly_discount_rate == 0.03
        assert results.cost_discount_rate == 0.03
        assert results.undiscounted_qaly_discount_rate == 0.0
        assert results.undiscounted_cost_discount_rate == 0.03
        assert results.willingness_to_pay == 50_000

    def test_reference_case_loaded(self, results):
        assert results.reference_case["id"] == "whatnut_consumer_3pct"
        assert results.reference_case["perspective"] == "consumer_out_of_pocket"
        assert results.reference_case["health_discount_rate"] == pytest.approx(0.03)
        assert results.reference_case["cost_discount_rate"] == pytest.approx(0.03)
        assert results.reference_case["formal_reference_case"] is False

    def test_decision_and_model_metadata_loaded(self, results):
        assert results.decision_context["comparator"] == (
            "No modeled daily-nut intervention."
        )
        assert results.decision_summary["recommended_nut_id"] is None
        assert results.decision_summary["best_nut_alternative_id"] == "peanut"
        assert results.model_interval["level"] == pytest.approx(0.95)
        assert results.model_interval["posterior"] is False
        assert results.methodology_provenance["runtime_dependency"] is False
        assert len(results.sensitivity_results["confounding_prior"]) == 4

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
        num_str = icer_str.replace("$", "").replace(",", "")
        float(num_str)  # Should not raise

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

    def test_qaly_undiscounted_interval(self):
        assert r.walnut.qaly_undiscounted_ci.startswith("[")

    def test_icer_undiscounted_property(self):
        assert r.walnut.icer_undiscounted_fmt.startswith("$")

    def test_decision_metrics(self):
        assert r.peanut.nut_alternative_rank == 1
        assert 0 <= r.walnut.p_nmb_positive <= 1
        assert 0 <= r.walnut.p_optimal <= 1
        assert r.walnut.lifetime_cost > 0

    def test_default_decision_prose_is_derived_from_artifact(self):
        assert "every nut has negative expected net monetary benefit" in (
            r.decision_result_sentence
        )
        assert r.nut_ranking_summary == (
            "the top three nut alternatives are peanuts, almonds, and walnuts"
        )
        assert r.health_gain_and_icer_summary == (
            "Walnuts yield the largest expected gain "
            f"({r.walnut.life_years_fmt} life years); they also have the lowest "
            "defined expected ICER"
        )
        assert r.best_nut_alternative is r.peanut
        assert r.peanut.expected_nmb_fmt.startswith("-$")

    def test_custom_wtp_artifact_updates_decision_prose(self, tmp_path):
        analysis = run_analysis(
            n_samples=1_000,
            seed=42,
            willingness_to_pay=250_000,
        )
        path = tmp_path / "wtp-250000.json"
        generate_results_json(analysis, path)

        custom = load_results(path)

        assert custom.decision_summary["recommended_nut_id"] == "walnut"
        assert custom.best_nut_alternative.name == "Walnut"
        assert custom.best_nut_alternative.expected_net_monetary_benefit > 0
        assert custom.best_nut_alternative.expected_nmb_fmt.startswith("$")
        assert not custom.best_nut_alternative.expected_nmb_fmt.startswith("-$")
        assert "Walnuts" in custom.decision_result_sentence
        assert "comparator is preferred" not in custom.decision_result_sentence
        assert custom.nut_ranking_summary.startswith(
            "the top three nut alternatives are walnuts"
        )

    def test_decision_prose_handles_expected_nmb_ties(self):
        tied = deepcopy(get_results())
        tied.decision_summary["recommended_option_ids"] = ["walnut", "almond"]
        tied.decision_summary["recommended_nut_id"] = None

        assert tied.decision_result_sentence == (
            "expected net monetary benefit is tied between Walnuts and Almonds"
        )


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

    def test_icer_undiscounted_range(self):
        ir = r.icer_undiscounted_range
        assert isinstance(ir, str)
        assert "$" in ir

    def test_icer_ranges_are_defined_when_no_expected_ratio_exists(self, monkeypatch):
        results = get_results()
        for nut in results.nuts.values():
            monkeypatch.setattr(nut, "icer", None)
            monkeypatch.setattr(nut, "icer_undiscounted", None)

        assert results.icer_range == "undefined"
        assert results.icer_undiscounted_range == "undefined"

    def test_nut_alternative_ranking_is_complete(self):
        assert [nut.nut_alternative_rank for nut in r.nut_alternative_ranking] == list(
            range(1, len(NUT_IDS) + 1)
        )

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
        assert "Nut-only rank" in table
        assert "Option" in table
        assert "QALY" in table
        assert "95% MI" in table
        assert "E[NMB]" in table
        assert "P(optimal)" in table
        assert "No modeled nut" in table

    def test_table_3_is_ordered_by_nut_alternative_rank(self):
        table = r.table_3_qalys()
        positions = [table.index(nut.name) for nut in r.nut_alternative_ranking]
        assert positions == sorted(positions)

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

    def test_table_7_uses_materialized_sensitivities(self):
        table = r.table_7_sensitivity()
        very_skeptical = next(
            row
            for row in r.sensitivity_results["confounding_prior"]
            if row["interpretation"] == "Very skeptical"
        )

        assert "Very skeptical" in table
        assert "Base case" in table
        assert "Optimistic" in table
        assert f"{r.walnut.qaly_mean:.3f}" in table
        assert f"{very_skeptical['qaly_mean']['peanut']:.3f}" in table
        assert "<td>0.00</td>" not in table


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
