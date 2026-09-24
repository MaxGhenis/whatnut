"""End-to-end: determinism, the Fadnes reproduction, monotonicity, scenario order."""

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
    nonincreasing in log RR and the LDL pathway is linear)."""
    res, _ = fresh_run("a")
    for sex, a0, bg, mem in itertools.product(
        SEXES, GRID["a0"], GRID["background"], MEMBERS
    ):
        means = [cell(res, sex, a0, d, bg)[mem]["mean"] for d in GRID["delta"]]
        assert all(b >= a for a, b in zip(means, means[1:])), (sex, a0, bg, mem, means)


def test_monotone_in_dose_every_stat_when_c_positive():
    res, _ = fresh_run("a")
    members = ["face_value", "calibrated_diet", "cvd_only", "ldl_chd", "ldl_all"]
    members += [m for m in MEMBERS if m.startswith("c_")]
    strata = res["calibration"]["strata"]
    assert strata["calibrated_diet"]["linear"]["share_draws_c_below_0"] == 0
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
        for mem in ("calibrated", "face_value"):
            v = fm[sex][mem]["mean"]
            assert all(b <= a for a, b in zip(v, v[1:]))


def test_scenario_ordering():
    """ldl_chd <= ldl_all everywhere; the LDL pathway sits below face value (c = 1)
    from zero background. (From 15 g/day the cohort curve is flat, so face value is
    zero there while the linear LDL pathway is not.) At the reference case the
    calibrations order by their ratios."""
    res, _ = fresh_run("a")
    for sex, a0, d, bg in itertools.product(
        SEXES, GRID["a0"], GRID["delta"], GRID["background"]
    ):
        c = cell(res, sex, a0, d, bg)
        assert 0 < c["ldl_chd"]["mean"] <= c["ldl_all"]["mean"]
        if bg == 0:
            assert c["ldl_all"]["mean"] <= c["face_value"]["mean"]
            assert c["ldl_all"]["p90"] <= c["face_value"]["p10"]
    strata = res["calibration"]["strata"]
    for sex in SEXES:
        ref = res["reference"]["scenarios"][sex]
        assert (
            ref["ldl_chd"]["mean"]
            <= ref["ldl_all"]["mean"]
            <= ref["calibrated_mortality"]["mean"]
            <= ref["calibrated"]["mean"]
            <= ref["face_value"]["mean"]
        )
        by_rrr = sorted(strata, key=lambda k: -strata[k]["rrr"])
        means = [ref[k]["mean"] for k in by_rrr]
        assert means == sorted(means), by_rrr
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
    rows = res["sensitivity"]["rows"]
    for sex in SEXES:
        for col in ("face_value", "calibrated", "ldl_all"):
            t0, t10, t20 = (
                rows[r]["stats"][sex][col]["mean"]
                for r in ("phase_in_0", "main", "phase_in_20")
            )
            assert t0 > t10 > t20 > 0
            assert (
                rows["main"]["stats"][sex][col]
                == (res["reference"]["scenarios"][sex][col])
            )


def test_sensitivities_move_the_expected_way():
    """Each sensitivity that removes part of the association lowers the gain;
    the plateau curve (90% of the per-28 g effect at 15 g) raises it."""
    res, _ = fresh_run("a")
    rows = res["sensitivity"]["rows"]
    for sex in SEXES:
        main = rows["main"]["stats"][sex]["face_value"]["mean"]
        for rid in (
            "curve_from_any",
            "rr_fu10",
            "rr_large",
            "exclude_external",
            "attenuate_with_age",
        ):
            assert 0 < rows[rid]["stats"][sex]["face_value"]["mean"] < main, rid
        assert rows["curve_linear_plateau"]["stats"][sex]["face_value"]["mean"] > main
        # the printed curve and the running minimum agree up to 15 g
        for col in ("face_value", "calibrated"):
            assert rows["curve_as_printed"]["stats"][sex][col]["mean"] == (
                pytest.approx(rows["main"]["stats"][sex][col]["mean"], rel=1e-6)
            )


def test_ala_channel():
    """The ALA channel adds only for ALA inside Naghshi's range, so nothing at a
    5 g/day background, and walnut adds the most at the mean background."""
    res, _ = fresh_run("a")
    ala = res["ala"]["by_background"]
    bgs = res["ala"]["background_g"]
    for nut, e in ala["high"].items():
        for sex in SEXES:
            assert e[sex]["counted_ala_g"] == 0
            assert e[sex]["face_value:ala"]["increment"]["mean"] == 0
    lo, hi = ASSUMPTIONS["ala_support_g"]
    for sex in SEXES:
        counted = {nut: e[sex]["counted_ala_g"] for nut, e in ala["average"].items()}
        assert max(counted, key=counted.get) == "walnut"
        w = ala["average"]["walnut"]
        expect = min(bgs["average"][sex] + w["nut_ala_g"], hi) - bgs["average"][sex]
        assert counted["walnut"] == pytest.approx(expect, rel=1e-5)
        rand = w[sex]["face_value:ala"]["increment"]["mean"]
        fixed = w[sex]["face_value:ala_fixed"]["increment"]["mean"]
        assert rand > fixed > 0  # the fixed-effect slope (0.99) is flatter


def test_cost_per_life_year_is_ratio_of_means():
    res, _ = fresh_run("a")
    c = res["cost"]["by_nut"]
    for nut, e in c.items():
        assert e["usd_per_year"] == pytest.approx(
            e["usd_per_kg"] * ASSUMPTIONS["reference"]["delta"] / 1000 * 365.25,
            rel=1e-5,
        )
        for sex in SEXES:
            x = e[sex]["face_value"]
            assert x["usd_per_life_year"] == pytest.approx(
                x["discounted_cost_usd"] / x["discounted_life_years"], rel=1e-4
            )
            # discounting shrinks life-years gained decades away
            assert x["discounted_life_years"] < x["life_years"]
    # class effect: every nut gains the same; only the price differs
    ly = {nut: c[nut]["male"]["calibrated"]["life_years"] for nut in c}
    assert len(set(ly.values())) == 1
    # the peanut LDL pathway uses peanut trials, the tree-nut one Del Gobbo's
    assert c["peanut"]["ldl_source"] != c["walnut"]["ldl_source"]
    assert (
        c["peanut"]["male"]["ldl_all"]["life_years"]
        != c["walnut"]["male"]["ldl_all"]["life_years"]
    )


def test_figures_written():
    _, out = fresh_run("a")
    for name in FIGURE_FILES:
        p = out / "figures" / name
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
        assert b"Software" not in p.read_bytes()[:4096]
