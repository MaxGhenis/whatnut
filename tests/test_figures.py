"""Regression tests for paper figure generation."""

from whatnut import figures
from whatnut.config import NUT_IDS
from whatnut.results import get_results


def test_every_configured_nut_has_an_explicit_chart_color():
    assert set(NUT_IDS) <= set(figures.COLORS["nuts"])


def test_all_figures_generate_from_committed_results(monkeypatch, tmp_path):
    monkeypatch.setattr(figures, "FIGURE_DIR", tmp_path)

    generated = figures.generate_all_figures()

    assert set(generated) == {
        "architecture",
        "pathway_rrs",
        "forest",
        "cause_fractions",
        "confounding",
        "nutrients",
        "icer",
    }
    for path in generated.values():
        assert path.exists()
        assert path.stat().st_size > 10_000


def test_icer_figure_handles_no_defined_expected_ratios(monkeypatch, tmp_path):
    monkeypatch.setattr(figures, "FIGURE_DIR", tmp_path)
    for nut in get_results().nuts.values():
        monkeypatch.setattr(nut, "icer", None)

    path = figures.fig7_icer_comparison()

    assert path.exists()
    assert path.stat().st_size > 10_000
