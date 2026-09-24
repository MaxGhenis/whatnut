"""Dose curves, draws and the bracket, checked against the evidence rows."""

from __future__ import annotations

import math

import numpy as np
import pytest

from whatnut import data
from whatnut.model import ASSUMPTIONS, DRAW_COLUMNS, Draws, Model
from whatnut.pipeline import ala_counted


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
    """Face value and calibrated share the RR28 draw, so c_cal is exactly the
    ratio of their log multipliers, draw by draw."""
    _, face = m.scenario("face_value", 28, 0)
    _, cal = m.scenario("calibrated", 28, 0)
    assert np.allclose(cal / face, m.q["c_calibrated"])


def test_calibrated_multiplier_formula(m):
    """DESIGN decision 3: c_cal = ln(RR28 x RRR) / ln(RR28); above 1 for the
    intake-v-intake stratum (RRR 0.98)."""
    rr = m.rows["rr28_all"].estimate
    rrr = m.rows["rrr_intake"].estimate
    c_point = math.log(rr * rrr) / math.log(rr)
    assert c_point > 1
    assert np.median(m.q["c_calibrated"]) == pytest.approx(c_point, rel=0.02)
    rrr_all = m.rows["rrr_all_cause"].estimate
    assert math.log(rr * rrr_all) / math.log(rr) < 1


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


def test_floor_is_linear_in_dose_and_ignores_background(m):
    _, b10 = m.scenario("floor_high", 10, 0)
    _, b20 = m.scenario("floor_high", 20, 0)
    _, b20bg = m.scenario("floor_high", 20, 20)
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
