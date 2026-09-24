"""End-to-end: determinism, the Fadnes reproduction, monotonicity, bracket order."""

from __future__ import annotations

import itertools
import json

import pytest

from tests.helpers import fresh_run
from whatnut.model import ASSUMPTIONS, MEMBERS
from whatnut.pipeline import FIGURE_FILES

GRID = ASSUMPTIONS["grid"]
SEXES = GRID["sex"]


def cell(res, sex, a0, delta, bg):
    return res["grid"][sex][str(a0)][str(delta)][str(bg)]


def test_pipeline_is_byte_deterministic():
    """Two runs write identical results.json and identical figures."""
    (_, a), (_, b) = fresh_run("a"), fresh_run("b")
    assert (a / "results.json").read_bytes() == (b / "results.json").read_bytes()
    for name in FIGURE_FILES:
        pa, pb = a / "figures" / name, b / "figures" / name
        assert pa.read_bytes() == pb.read_bytes(), name


def test_results_json_is_canonical():
    _, out = fresh_run("a")
    text = (out / "results.json").read_text(encoding="utf-8")
    obj = json.loads(text)
    assert text == json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n"

    def floats(o):
        if isinstance(o, dict):
            for v in o.values():
                yield from floats(v)
        elif isinstance(o, list):
            for v in o:
                yield from floats(v)
        elif isinstance(o, float):
            yield o

    assert all(float(f"{x:.6g}") == x for x in floats(obj))
    for word in ("fetched_at", "generated_at", "timestamp"):
        assert word not in text


def test_fadnes_reproduction_within_15_percent():
    """DESIGN decision 6: HR 0.84 at 25 g/day, 10-year linear phase-in, 0 -> 25 g
    from age 20, all-cause, on our 2023 baseline; within 15% of Fadnes 2022."""
    res, _ = fresh_run("a")
    fd = res["fadnes"]
    print("\nFadnes 2022 reproduction (years of life expectancy, 0 -> 25 g/day):")
    print(f"{'sex':7} {'age':>3} {'ours':>7} {'theirs':>7} {'gap':>7}")
    for row in fd["rows"]:
        print(
            f"{row['sex']:7} {row['start_age']:>3} {row['ours']:7.3f} "
            f"{row['theirs']:7.2f} {row['rel_diff']:+7.1%}"
        )
    main = [r for r in fd["rows"] if r["start_age"] == fd["main_start_age"]]
    assert {r["sex"] for r in main} == set(SEXES)
    for row in main:
        assert abs(row["ours"] / row["theirs"] - 1) <= 0.15, row
    assert fd["inputs"]["hr"] == fd["inputs"]["aune_s15_rr_at_dose"]


def test_monotone_in_dose():
    """Delta LE is nondecreasing in delta (every member's mean; the curves are
    nonincreasing in log RR and the floor is linear)."""
    res, _ = fresh_run("a")
    for sex, a0, bg, mem in itertools.product(
        SEXES, GRID["a0"], GRID["background"], MEMBERS
    ):
        means = [cell(res, sex, a0, d, bg)[mem]["mean"] for d in GRID["delta"]]
        assert all(b >= a for a, b in zip(means, means[1:])), (sex, a0, bg, mem, means)


def test_monotone_in_dose_every_stat_when_c_positive():
    res, _ = fresh_run("a")
    members = ["face_value", "calibrated", "cvd_only", "floor_low", "floor_high"]
    members += [m for m in MEMBERS if m.startswith("c_")]
    assert res["calibration"]["calibrated"]["share_draws_c_below_0"] == 0
    for sex, a0, bg, mem in itertools.product(
        SEXES, GRID["a0"], GRID["background"], members
    ):
        for stat in ("mean", "p10", "p90", "p2_5", "p97_5"):
            v = [cell(res, sex, a0, d, bg)[mem][stat] for d in GRID["delta"]]
            assert all(b >= a for a, b in zip(v, v[1:])), (sex, a0, bg, mem, stat, v)


def test_marginal_value_nonincreasing_in_background():
    res, _ = fresh_run("a")
    mg = res["marginal_10g"]["by_background"]
    for sex, mem in itertools.product(SEXES, MEMBERS):
        v = [mg[sex][str(b)][mem]["mean"] for b in GRID["background"]]
        assert all(b <= a for a, b in zip(v, v[1:])), (sex, mem, v)
    # and on the fine grid behind the marginal figure
    fm = res["figures"]["marginal_by_background"]
    for sex in SEXES:
        v = fm[sex]["calibrated"]["mean"]
        assert all(b <= a for a, b in zip(v, v[1:]))


def test_bracket_ordering():
    """floor_low <= floor_high everywhere; the floor sits below face value (c = 1)
    from zero background. (From 20 g/day the cohort curve is flat, so face value is
    zero while the linear LDL floor is not; see DESIGN, Deviations.)"""
    res, _ = fresh_run("a")
    for sex, a0, d, bg in itertools.product(
        SEXES, GRID["a0"], GRID["delta"], GRID["background"]
    ):
        c = cell(res, sex, a0, d, bg)
        assert 0 < c["floor_low"]["mean"] <= c["floor_high"]["mean"]
        if bg == 0:
            assert c["floor_high"]["mean"] <= c["face_value"]["mean"]
            assert c["floor_high"]["p90"] <= c["face_value"]["p10"]
    for sex in SEXES:
        ref = res["reference"]["bracket"][sex]
        assert (
            ref["floor_low"]["mean"]
            <= ref["floor_high"]["mean"]
            <= ref["face_value"]["mean"]
        )
        assert ref["c_0.1"]["mean"] < ref["c_0.33"]["mean"] < ref["c_1"]["mean"]
        assert ref["c_1"] == ref["face_value"]


def test_interval_stats_are_ordered():
    res, _ = fresh_run("a")
    for sex, a0, d, bg, mem in itertools.product(
        SEXES, GRID["a0"], GRID["delta"], GRID["background"], MEMBERS
    ):
        s = cell(res, sex, a0, d, bg)[mem]
        assert s["p2_5"] <= s["p10"] <= s["p90"] <= s["p97_5"]
        assert s["p2_5"] <= s["mean"] <= s["p97_5"]


def test_phase_in_sensitivity_orders_as_expected():
    """Reaching full effect sooner gains more; T = 10 is the main case."""
    res, _ = fresh_run("a")
    pi = res["phase_in"]
    for sex in SEXES:
        for mem in ("face_value", "calibrated", "floor_high"):
            t0, t10, t20 = (pi[t][sex][mem]["mean"] for t in ("0", "10", "20"))
            assert t0 > t10 > t20 > 0
            assert pi["10"][sex][mem] == res["reference"]["bracket"][sex][mem]


def test_ala_channel():
    """The ALA channel adds only for ALA inside Naghshi's range, so nothing at a
    5 g/day background, and walnut adds the most at the mean background."""
    res, _ = fresh_run("a")
    ala = res["ala"]["by_background"]
    lo_bg, hi_bg = (
        str(x)
        for x in (res["ala"]["background_g"][0], ASSUMPTIONS["ala_background_high_g"])
    )
    for nut, e in ala[hi_bg].items():
        assert e["counted_ala_g"] == 0
        for sex in SEXES:
            assert e[sex]["face_value"]["increment"]["mean"] == 0
    counted = {nut: e["counted_ala_g"] for nut, e in ala[lo_bg].items()}
    assert max(counted, key=counted.get) == "walnut"
    lo, hi = ASSUMPTIONS["ala_support_g"]
    assert counted["walnut"] == pytest.approx(
        hi - res["ala"]["background_g"][0], rel=1e-5
    )
    for sex in SEXES:
        assert ala[lo_bg]["walnut"][sex]["face_value"]["increment"]["mean"] > 0


def test_cost_per_life_year_is_ratio_of_means():
    res, _ = fresh_run("a")
    c = res["cost"]["by_nut"]
    for nut, e in c.items():
        assert e["usd_per_year"] == pytest.approx(
            e["usd_per_kg"] * ASSUMPTIONS["reference"]["delta"] / 1000 * 365.25,
            rel=1e-5,
        )
        for sex in SEXES:
            x = e[sex]["calibrated"]
            assert x["usd_per_life_year"] == pytest.approx(
                x["discounted_cost_usd"] / x["discounted_life_years"], rel=1e-4
            )
            # discounting shrinks life-years gained decades away
            assert x["discounted_life_years"] < x["life_years"]
    # class effect: every tree nut gains the same; only the price differs
    ly = {nut: c[nut]["male"]["calibrated"]["life_years"] for nut in c}
    assert len(set(ly.values())) == 1
    # the peanut floor uses peanut trials, the tree-nut floor Del Gobbo's
    assert c["peanut"]["floor_ldl_source"] != c["walnut"]["floor_ldl_source"]
    assert (
        c["peanut"]["male"]["floor_high"]["life_years"]
        != c["walnut"]["male"]["floor_high"]["life_years"]
    )


def test_figures_written():
    _, out = fresh_run("a")
    for name in FIGURE_FILES:
        p = out / "figures" / name
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"Software" not in p.read_bytes()[:4096]
