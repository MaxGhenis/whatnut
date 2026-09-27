"""Dose curves, draws, calibration and the scenarios, checked against the evidence."""

from __future__ import annotations

import csv
import math

import numpy as np
import pytest

from whatnut import data
from whatnut.model import (
    ANALOG_PAIR_IDS,
    ASSUMPTIONS,
    CALIBRATION_ANCHORS,
    CALIBRATION_STRATA,
    DRAW_COLUMNS,
    RR_ROLES,
    Draws,
    Model,
    Variant,
    intake_pair_subsets,
    pool_ratios,
    pool_stats,
)
from whatnut.pipeline import ala_counted

PAIRS_CSV = data.ROOT / "data" / "calibration" / "schwingshackl2021_intake_pairs.csv"


@pytest.fixture(scope="module")
def m():
    return Model(n=4000)


def test_main_curve_is_running_minimum_of_aune_s15(m):
    g, rr = data.aune_curve("all_cause_mortality")
    f = m.curves["main"].f
    running = np.minimum.accumulate(rr)
    assert np.allclose(np.exp(f(g)), running)
    # nonincreasing everywhere, flat beyond the last point
    fine = f(np.linspace(0, 60, 601))
    assert np.all(np.diff(fine) <= 0)
    assert f(60) == f(g[-1])
    assert f(0) == 0


def test_pchip_sensitivity_keeps_the_printed_uptick(m):
    g, rr = data.aune_curve("all_cause_mortality")
    f = m.curves["pchip_as_printed"].f
    assert np.allclose(np.exp(f(g)), rr)
    assert f(28) > f(20)  # RR 0.85 at 28 g above 0.82 at 20 g, as printed


def test_linear_plateau_sensitivity(m):
    row = m.rows["rr28_all"]
    f = m.curves["linear_plateau"].f
    assert math.exp(f(row.per_grams())) == pytest.approx(row.estimate)
    share = f(ASSUMPTIONS["plateau_dose_g"]) / f(row.per_grams())
    assert share == pytest.approx(ASSUMPTIONS["plateau_share"])


def test_cvd_curve_is_s14_mortality(m):
    g, rr = data.aune_curve("cvd_mortality")
    assert np.allclose(np.exp(m.cvd_curve.f(g)), np.minimum.accumulate(rr))


def test_draws_are_one_seeded_matrix():
    a, b = Draws.make(100, 7), Draws.make(100, 7)
    assert a.z.shape == (100, len(DRAW_COLUMNS))
    assert np.array_equal(a.z, b.z)
    assert not np.array_equal(a.z, Draws.make(100, 8).z)


def test_common_random_numbers_across_scenarios(m):
    """Face value and every calibration share the RR28 draw, so each c is exactly
    the ratio of their log multipliers, draw by draw."""
    _, face = m.scenario("face_value", 28, 0)
    for member in CALIBRATION_STRATA:
        _, cal = m.scenario(member, 28, 0)
        assert np.allclose(cal / face, m.c(member, "linear")), member


def test_calibrated_multiplier_formula(m):
    """DESIGN decision 3: c = ln(RR28 x RRR) / ln(RR28), per draw; below 1 for
    the main (all-pairs) calibration, above 1 for the intake stratum (RRR 0.98)."""
    rr = m.rows["rr28_all"].estimate
    for member, role in CALIBRATION_STRATA.items():
        rrr = m.rows[role].estimate
        c_point = math.log(rr * rrr) / math.log(rr)
        med = np.median(m.c(member, "linear"))
        assert med == pytest.approx(c_point, abs=0.03), member
        assert (c_point > 1) == (rrr < 1), member


def test_curve_anchor_uses_the_curve_at_one_serving(m):
    """Anchor 'curve': c = 1 + ln RRR / ln RR_curve(28), with RR_curve(28) the
    main curve's value at Aune's serving (its running minimum, 0.82)."""
    serving = m.rows["rr28_all"].per_grams()
    rr_curve = math.exp(float(m.curves["main"].f(serving)))
    assert rr_curve == pytest.approx(min(data.aune_curve("all_cause_mortality")[1]))
    rrr = m.rows["rrr_all_cause"].estimate
    c_point = math.log(rr_curve * rrr) / math.log(rr_curve)
    med = np.median(m.c("calibrated_mortality", "curve"))
    assert med == pytest.approx(c_point, abs=0.03)
    _, lin = m.scenario("calibrated_mortality", 15, 0)
    _, cur = m.scenario("calibrated_mortality", 15, 0, Variant(anchor="curve"))
    assert np.mean(cur) > np.mean(lin)  # less protective (log RR closer to 0)


def test_calibration_is_measured_against_the_estimate_that_scales_the_curve(m):
    """DESIGN decision 12 (revised): a rescaled curve's calibration computes c
    against its own per-28 g draw, so on the linear anchor the calibrated log RR
    per serving is ln RR28(role) + ln RRR draw by draw (eq-calibration), and the
    calibrated scenario is c times the rescaled face value."""
    for member in CALIBRATION_STRATA:
        ln_rrr = m.q[f"ln_rrr:{member}"]
        for role in RR_ROLES:
            ln_rr = m.q[f"ln_rr28:{role}"]
            c = m.c(member, "linear", role)
            assert np.allclose(c * ln_rr, ln_rr + ln_rrr), (member, role)
            # the curve anchor rescales the main curve's value at 28 g the same way
            f28 = float(m.curves["main"].f(m.rows["rr28_all"].per_grams()))
            c_curve = m.c(member, "curve", role)
            ln_curve = m.q[f"scale:{role}"] * f28
            assert np.allclose(c_curve * ln_curve, ln_curve + ln_rrr), (member, role)
            v = Variant(rr_role=role)
            _, face = m.scenario("face_value", 15, 0, v)
            _, cal = m.scenario(member, 15, 0, v)
            assert np.allclose(cal, c * face), (member, role)
    # the same ratio removes a larger share of a weaker association
    rrr = m.rows["rrr_overall"].estimate
    for weaker in ("rr28_fu10", "rr28_large"):
        assert m.rows[weaker].estimate > m.rows["rr28_all"].estimate
        assert np.median(m.c("calibrated", "linear", weaker)) < np.median(
            m.c("calibrated", "linear")
        )
        rr = m.rows[weaker].estimate
        assert np.median(m.c("calibrated", "linear", weaker)) == pytest.approx(
            math.log(rr * rrr) / math.log(rr), abs=0.03
        )
    # the curve measured from 5 g keeps the main estimate, so the main c
    _, face = m.scenario("face_value", 15, 0, Variant(curve="from_any"))
    _, cal = m.scenario("calibrated", 15, 0, Variant(curve="from_any"))
    assert np.allclose(cal, m.c("calibrated", "linear") * face)
    for anchor in CALIBRATION_ANCHORS:
        assert np.array_equal(
            m.c("calibrated", anchor), m.c("calibrated", anchor, "rr28_all")
        )


def _pair_rows():
    with PAIRS_CSV.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _as_rows(lines):
    return [
        data.EvidenceRow(
            id=f"pair{i}",
            kind="calibration_corpus",
            measure="RRR",
            unit=None,
            estimate=float(x["rrr"]),
            ci_low=float(x["ci_low"]),
            ci_high=float(x["ci_high"]),
            ci_level=0.95,
            pi_low=None,
            pi_high=None,
            support=None,
            notes=None,
            source={},
            verified={},
        )
        for i, x in enumerate(lines)
    ]


def test_pooling_reproduces_the_published_intake_stratum():
    """pool_ratios on the 23 intake pairs read from Supplementary Figure 9 gives
    the published 0.98 (0.93 to 1.04), prediction interval 0.90 to 1.07."""
    lines = _pair_rows()
    assert len(lines) == 23
    pooled = pool_ratios(_as_rows(lines), "intake")
    row = data.row("schwingshackl2021_rrr_intake_vs_intake")
    for got, want in (
        (pooled.estimate, row.estimate),
        (pooled.ci_low, row.ci_low),
        (pooled.ci_high, row.ci_high),
        (pooled.pi_low, row.pi_low),
        (pooled.pi_high, row.pi_high),
    ):
        assert round(got, 2) == pytest.approx(want, abs=0.01)


def test_intake_subsets_read_through_the_manifest():
    """The pipeline reads the 23 pairs through data.intake_pairs (hash-checked),
    and the subsets are the ones the paper names: 15 without pregnancy or
    colorectal outcomes, 19 whose cohort RR is below 1."""
    data.READS.clear()
    subsets = intake_pair_subsets()
    assert "data/calibration/schwingshackl2021_intake_pairs.csv" in data.READS
    lines = _pair_rows()
    assert [len(subsets[k]) for k in ("all", "core", "protective")] == [23, 15, 19]
    for r in subsets["core"]:
        text = f"{r.exposure} {r.outcome}".lower()
        assert "pregnan" not in text and "gestational" not in text
        assert "colorectal" not in text and "preterm" not in text
    dropped = [
        x
        for x in lines
        if f"intake_pair_{lines.index(x) + 1}" not in {r.id for r in subsets["core"]}
    ]
    assert len(dropped) == 8
    assert all(
        "pregnancy" in x["topic"] or "colorectal" in x["outcome"] for x in dropped
    )
    by_id = {f"intake_pair_{i}": x for i, x in enumerate(lines, start=1)}
    assert {r.id for r in subsets["protective"]} == {
        k for k, x in by_id.items() if float(x["cohort_rr"]) < 1
    }
    # every pooled row carries its line's ratio and interval
    for r in subsets["all"]:
        x = by_id[r.id]
        assert (r.estimate, r.ci_low, r.ci_high) == (
            float(x["rrr"]),
            float(x["ci_low"]),
            float(x["ci_high"]),
        )


def test_intake_subsets_pool_as_the_paper_says():
    """The 15 core pairs pool below 1 and the 19 protective pairs at about 1, so
    the overall ratio above 1 does not come from the intake pairs; all 23 pool to
    the published stratum."""
    subsets = intake_pair_subsets()
    pools = {k: pool_stats(rows, k).summary() for k, rows in subsets.items()}
    assert round(pools["core"]["estimate"], 2) == 0.97
    assert round(pools["protective"]["estimate"], 2) == 1.00
    published = data.row("schwingshackl2021_rrr_intake_vs_intake")
    assert round(pools["all"]["estimate"], 2) == published.estimate
    for p in pools.values():
        lo, hi = p["ci"]
        assert lo < p["estimate"] < hi
        assert p["pi"][0] <= lo and hi <= p["pi"][1]


def test_pool_stats_matches_pool_ratios_and_reports_heterogeneity():
    rows = [data.row(rid) for rid in ANALOG_PAIR_IDS]
    stats, row = pool_stats(rows), pool_ratios(rows, "x")
    s = stats.summary()
    assert (s["estimate"], s["ci"], s["pi"]) == (
        row.estimate,
        [row.ci_low, row.ci_high],
        [row.pi_low, row.pi_high],
    )
    # the six nearest pairs show no variation beyond chance: Q <= k - 1, tau2 = 0
    assert stats.k == 6 and stats.q <= stats.k - 1 and stats.tau2 == 0
    # with tau2 = 0 the prediction interval is the CI widened from z to t(k - 2)
    z = data.z_for(stats.level)
    t = __import__("scipy").stats.t.ppf((1 + stats.level) / 2, stats.k - 2)
    assert stats.half_pi == pytest.approx(stats.se * t)
    assert math.log(s["ci"][1]) - stats.mu == pytest.approx(stats.se * z)


def test_analog_pairs_match_the_readings(m):
    """The six pooled evidence rows equal their lines in the 23-pair file, and
    the pool is the ALA and Mediterranean-diet subset."""
    lines = _pair_rows()
    subset = [
        x for x in lines if x["topic"] in ("alpha-linolenic acid", "Mediterranean diet")
    ]
    assert len(subset) == len(ANALOG_PAIR_IDS)
    rows = [data.row(rid) for rid in ANALOG_PAIR_IDS]
    assert sorted((r.estimate, r.ci_low, r.ci_high) for r in rows) == sorted(
        (float(x["rrr"]), float(x["ci_low"]), float(x["ci_high"])) for x in subset
    )
    pooled = m.rows["rrr_analog"]
    direct = pool_ratios(_as_rows(subset), "subset")
    assert pooled.estimate == pytest.approx(direct.estimate)
    assert pooled.pi_high == pytest.approx(direct.pi_high)


def test_lognormal_draws_match_row_intervals(m):
    """Each ratio's draws reproduce its CI at the row's own ci_level (the CTT
    CHD-death row is a 99% CI)."""
    for role, key in (
        ("ctt_chd", "ln_ctt_chd"),
        ("ctt_all", "ln_ctt_all"),
        ("ala", "ln_rr_ala"),
    ):
        row = m.rows[role]
        lo, hi = np.quantile(m.q[key], [(1 - row.ci_level) / 2, (1 + row.ci_level) / 2])
        assert math.exp(lo) == pytest.approx(row.ci_low, abs=0.01)
        assert math.exp(hi) == pytest.approx(row.ci_high, abs=0.01)
    assert m.rows["ctt_chd"].ci_level == 0.99
    assert data.z_for(0.99) == pytest.approx(2.5758, abs=1e-4)


def test_peanut_ldl_se_from_p_value(m):
    row = m.rows["ldl_peanut"]
    assert row.ci_low is None and row.p_value() == 0.472
    z = abs(row.estimate) / row.se_from_p()
    assert 2 * (1 - __import__("scipy").stats.norm.cdf(z)) == pytest.approx(0.472)


def test_ldl_pathway_is_linear_in_dose_and_ignores_background(m):
    _, b10 = m.scenario("ldl_all", 10, 0)
    _, b20 = m.scenario("ldl_all", 20, 0)
    _, b20bg = m.scenario("ldl_all", 20, 20)
    assert np.allclose(b20, 2 * b10)
    assert np.array_equal(b20, b20bg)
    # 28.4 g/day of tree nuts lowers LDL by Del Gobbo's estimate, in mmol/L
    row = m.rows["ldl_tree"]
    red = m.ldl_mmol_reduction(row.per_grams(), "tree")
    assert np.mean(red) == pytest.approx(
        -row.estimate / ASSUMPTIONS["ldl_mg_dl_per_mmol_l"], rel=0.01
    )


def test_per_draw_gain_monotone_in_dose(m):
    prev = np.zeros(m.n)
    for delta in (5, 10, 15, 20, 28, 40):
        s, beta = m.scenario("face_value", delta, 0)
        g = m.gain("female", 50, s, beta)
        assert np.all(g >= prev - 1e-12)
        prev = g


def test_zero_effect_gives_zero_gain(m):
    assert np.all(m.gain("male", 40, "all", np.zeros(5)) == 0)
    s, beta = m.scenario("face_value", 10, 28)  # beyond the plateau
    assert np.all(m.gain("male", 40, s, beta) == 0)


def test_cause_restricted_multiplier(m):
    """h' = h (1 - p + p RR): the CVD-only member equals an all-cause multiplier
    of 1 - p + p RR at every age."""
    beta = np.array([math.log(0.8)])
    lm = m.log_mult("male", 60, 0, "cvd", beta)
    p = m.cause_share("male", 60, "cvd")
    assert np.allclose(np.exp(lm[0]), 1 - p + p * 0.8)


def test_from_any_curve_ignores_the_first_grams(m):
    """Sensitivity: the curve measured from Aune's first tabulated intake, so
    nothing below it counts."""
    g0 = ASSUMPTIONS["any_vs_none_g"]
    f, main = m.curves["from_any"].f, m.curves["main"].f
    assert np.all(f(np.linspace(0, g0, 11)) == 0)
    for g in (10, 15, 28):
        assert f(g) == pytest.approx(main(g) - main(g0))


def test_age_weight(m):
    at = ASSUMPTIONS["age_attenuation"]
    w = m.age_weight("male", 40)
    ages = m.base["male"].ages_from(40)
    assert np.all(w[ages <= at["from_age"]] == 1)
    assert np.all(w[ages >= at["to_age"]] == at["weight_at_end"])
    assert np.all(np.diff(w) <= 0)


def test_external_causes_left_out(m):
    """The nonexternal structure applies the multiplier to 1 - external share,
    for the cohort-curve scenarios and the all-deaths LDL pathway alike; the
    coronary LDL pathway and the cardiovascular scenario already act on one
    cause, so the choice does not touch them."""
    beta = np.array([math.log(0.8)])
    lm = m.log_mult("male", 40, 0, "nonexternal", beta)
    p = 1 - m.cause_share("male", 40, "external")
    assert np.allclose(np.exp(lm[0]), 1 - p + p * 0.8)
    assert 0 < p.min() and p.max() < 1
    ext = Variant(exclude_external=True)
    for member in ("face_value", "calibrated", "ldl_all"):
        s_main, b_main = m.scenario(member, 15, 0)
        s_ext, b_ext = m.scenario(member, 15, 0, ext)
        assert (s_main, s_ext) == ("all", "nonexternal"), member
        assert np.array_equal(b_main, b_ext), member
        # every draw's gain shrinks toward zero (harmful draws included)
        g_main = m.exact_gain("male", 40, s_main, b_main)
        g_ext = m.exact_gain("male", 40, s_ext, b_ext)
        assert np.all(np.abs(g_ext) <= np.abs(g_main)), member
        assert np.all(np.sign(g_ext) == np.sign(g_main)), member
        assert 0 < np.mean(g_ext) < np.mean(g_main), member
    for member in ("ldl_chd", "cvd_only"):
        assert m.scenario(member, 15, 0, ext)[0] == m.scenario(member, 15, 0)[0]


def test_interpolated_gain_matches_exact(m):
    """gain() interpolates the life table on a grid of multipliers; the error
    against evaluating every draw is under 0.001 day (DESIGN decision 15)."""
    days = ASSUMPTIONS["days_per_year"]
    for member in ("face_value", "calibrated", "calibrated_mortality", "ldl_chd"):
        for v in (Variant(), Variant(attenuate_with_age=True)):
            s, beta = m.scenario(member, 15, 0, v)
            a = m.gain("female", 30, s, beta, attenuate=v.attenuate_with_age)
            b = m.exact_gain("female", 30, s, beta, attenuate=v.attenuate_with_age)
            assert np.max(np.abs(a - b)) * days < 0.001, member


def test_ala_counted_inside_support():
    lo, hi = ASSUMPTIONS["ala_support_g"]
    assert ala_counted(0, 0.2) == 0  # below the observed range
    assert ala_counted(0, 1) == pytest.approx(1 - lo)
    assert ala_counted(2, 2.54) == pytest.approx(hi - 2)
    assert ala_counted(5, 2.54) == 0


def test_discount_weights(m):
    w = m.discount_weights("female", 40)
    r = ASSUMPTIONS["discount_rate"]
    assert w[0] == pytest.approx((1 + r) ** -0.5)
    assert np.all(np.diff(w) < 0)
