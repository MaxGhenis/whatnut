"""Properties of the round-2 logic that hold for every input, checked with
Hypothesis: the random-effects pool behind the calibration strata and the intake
subsets, the phase-in share and the PREDIMED check, the group sizes read from
evidence rows, and the fill's rounding (cost per life-year prints to $100).

The example tests beside each function pin the paper's own numbers; these check
the functions on inputs the paper does not use, so a change that breaks them
off the committed data still fails."""

from __future__ import annotations

import math
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from whatnut import data
from whatnut.model import (
    ASSUMPTIONS,
    PREDIMED_BASELINE_ROLES,
    aune_running_min,
    pool_stats,
)
from whatnut.pipeline import mean_phase_in_share, predimed_check

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "paper"))
import fill_paper  # noqa: E402

MINUS = "−"
SETTINGS = settings(max_examples=150, deadline=None)


def _row(row_id: str, **fields) -> data.EvidenceRow:
    base = dict(
        kind="calibration_corpus",
        measure="RRR",
        unit=None,
        estimate=None,
        ci_low=None,
        ci_high=None,
        ci_level=None,
        pi_low=None,
        pi_high=None,
        support=None,
        notes=None,
        source={},
        verified={},
    )
    return data.EvidenceRow(id=row_id, **{**base, **fields})


# --------------------------------------------------------------------------
# DerSimonian-Laird pool (model.pool_stats)
# --------------------------------------------------------------------------

# a study: ln ratio and the SE of that ln ratio
STUDY = st.tuples(
    st.floats(-1.5, 1.5, allow_nan=False), st.floats(0.02, 0.8, allow_nan=False)
)
STUDIES = st.lists(STUDY, min_size=3, max_size=12)
LEVEL = st.sampled_from([0.9, 0.95, 0.99])


def _ratio_rows(studies, level: float, shift: float = 0.0) -> list[data.EvidenceRow]:
    """Ratio rows whose CIs give back each study's SE, every ratio scaled by
    exp(shift)."""
    z = data.z_for(level)
    return [
        _row(
            f"r{i}",
            estimate=math.exp(y + shift),
            ci_low=math.exp(y + shift - z * se),
            ci_high=math.exp(y + shift + z * se),
            ci_level=level,
        )
        for i, (y, se) in enumerate(studies)
    ]


@SETTINGS
@given(STUDIES, LEVEL)
def test_pool_heterogeneity_and_intervals(studies, level):
    """tau2 >= 0 and is positive exactly when Cochran's Q exceeds k - 1; the pooled
    ratio is a weighted mean, so it lies within the rows' range; the CI holds the
    estimate and the prediction interval holds the CI (t(k - 2) > z and tau2 >= 0)."""
    p = pool_stats(_ratio_rows(studies, level))
    s = p.summary()
    assert p.k == len(studies) and p.level == level
    assert p.tau2 >= 0 and p.q >= 0
    assert (p.tau2 > 0) == (p.q > p.k - 1)
    ys = [y for y, _ in studies]
    assert min(ys) - 1e-9 <= p.mu <= max(ys) + 1e-9
    lo, hi = s["ci"]
    assert lo < s["estimate"] < hi
    assert s["pi"][0] <= lo * (1 + 1e-12) and hi <= s["pi"][1] * (1 + 1e-12)
    assert all(math.isfinite(x) for x in (*s["ci"], *s["pi"]))


@SETTINGS
@given(STUDIES, LEVEL, st.floats(-2, 2, allow_nan=False), st.randoms())
def test_pool_is_order_free_and_scale_equivariant(studies, level, shift, rnd):
    """Reordering the rows changes nothing; multiplying every ratio by a constant
    multiplies the pooled ratio and both intervals by it and leaves tau2 and Q."""
    base = pool_stats(_ratio_rows(studies, level))
    shuffled = list(studies)
    rnd.shuffle(shuffled)
    again = pool_stats(_ratio_rows(shuffled, level))
    for a, b in ((base.mu, again.mu), (base.se, again.se), (base.q, again.q)):
        assert a == pytest.approx(b, rel=1e-9, abs=1e-12)
    assert again.tau2 == pytest.approx(base.tau2, rel=1e-9, abs=1e-12)
    moved = pool_stats(_ratio_rows(studies, level, shift))
    assert moved.mu == pytest.approx(base.mu + shift, abs=1e-9)
    assert moved.se == pytest.approx(base.se, rel=1e-9)
    assert moved.q == pytest.approx(base.q, rel=1e-6, abs=1e-9)
    assert moved.tau2 == pytest.approx(base.tau2, rel=1e-6, abs=1e-9)
    assert moved.half_pi == pytest.approx(base.half_pi, rel=1e-6)


@SETTINGS
@given(STUDY, st.integers(3, 12), LEVEL)
def test_pool_of_identical_rows(study, k, level):
    """k copies of one study: no heterogeneity, the study's own ratio, and the SE
    shrunk by sqrt(k)."""
    y, se = study
    p = pool_stats(_ratio_rows([study] * k, level))
    assert p.q == pytest.approx(0, abs=1e-9) and p.tau2 == 0
    assert p.mu == pytest.approx(y, abs=1e-12)
    assert p.se == pytest.approx(se / math.sqrt(k), rel=1e-9)


@given(st.lists(STUDY, min_size=0, max_size=2))
def test_pool_refuses_fewer_than_three_rows(studies):
    """The t(k - 2) prediction interval is undefined below three rows; the pool
    says so instead of returning NaN."""
    with pytest.raises(data.DataIntegrityError, match="3 or more rows"):
        pool_stats(_ratio_rows(studies, 0.95))


def test_pool_refuses_mixed_levels():
    rows = _ratio_rows([(0.1, 0.2)] * 2, 0.95) + _ratio_rows([(0.1, 0.2)], 0.99)
    with pytest.raises(data.DataIntegrityError, match="mix CI levels"):
        pool_stats(rows)


# --------------------------------------------------------------------------
# Phase-in share and the PREDIMED check (pipeline)
# --------------------------------------------------------------------------

YEARS = st.floats(0.1, 60, allow_nan=False)


@SETTINGS
@given(YEARS, YEARS, YEARS)
def test_mean_phase_in_share_is_a_share_and_monotone(follow_up, other, phase):
    """The mean of min(t / T, 1) over [0, T_f] lies in (0, 1], grows with the
    follow-up, shrinks with a longer phase-in, and is 1/2 when T_f = T."""
    share = mean_phase_in_share(follow_up, phase)
    assert 0 < share <= 1
    lo, hi = sorted((follow_up, other))
    assert mean_phase_in_share(lo, phase) <= mean_phase_in_share(hi, phase) + 1e-15
    t_lo, t_hi = sorted((phase, other))
    assert (
        mean_phase_in_share(follow_up, t_hi)
        <= mean_phase_in_share(follow_up, t_lo) + 1e-15
    )
    assert mean_phase_in_share(phase, phase) == pytest.approx(0.5)
    assert mean_phase_in_share(follow_up, 0) == 1


MAIN_CURVE = aune_running_min("all_cause_mortality", "main")

GROUP = st.tuples(
    st.floats(0, 60, allow_nan=False).map(lambda g: round(g, 1)),
    st.integers(1, 20_000),
)


def _predimed_model(groups, nut: float, control: float, follow_up: float):
    """A stand-in for Model with the rows predimed_check reads and the main curve."""
    rows = {
        role: _row(
            role,
            kind="reference_value",
            measure="value",
            unit="g/day",
            estimate=g,
            population=f"a baseline group (n = {n:,} of the trial)",
        )
        for role, (g, n) in zip(PREDIMED_BASELINE_ROLES, groups)
    }
    rows["predimed_change_nuts"] = _row("nuts", measure="value", estimate=nut)
    rows["predimed_change_control"] = _row("control", measure="value", estimate=control)
    rows["predimed_death"] = _row(
        "death",
        measure="HR",
        estimate=1.12,
        ci_low=0.86,
        ci_high=1.47,
        ci_level=0.95,
        population=f"a trial; median follow-up {follow_up:.1f} years",
    )
    return SimpleNamespace(curves={"main": MAIN_CURVE}, rows=rows)


@SETTINGS
@given(
    st.lists(GROUP, min_size=3, max_size=3),
    st.floats(0, 40, allow_nan=False),
    st.floats(-20, 0, allow_nan=False),
    st.floats(0.1, 30, allow_nan=False),
)
def test_predimed_check_on_any_intakes(groups, nut, control, follow_up):
    """On the nonincreasing main curve, a nut arm that eats more against a control
    arm that eats less gives every baseline group a log hazard ratio at or below
    0, so full effect <= phased <= 1, and the phased ratio is the full one raised
    to the mean phase-in share; the shares and means come from the group rows."""
    pc = predimed_check(_predimed_model(groups, nut, control, follow_up))
    sizes = [n for _, n in groups]
    assert pc["n"] == sum(sizes)
    assert [g["n"] for g in pc["groups"]] == sizes
    assert all(g["log_hr"] <= 0 for g in pc["groups"])
    assert 0 < pc["full_hr"] <= pc["phased_hr"] <= 1
    share = mean_phase_in_share(
        float(f"{follow_up:.1f}"), ASSUMPTIONS["phase_in_years"]
    )
    assert pc["mean_phase_in_share"] == share
    assert pc["phased_hr"] == pytest.approx(pc["full_hr"] ** share, rel=1e-12)
    eaters = sum(n for g, n in groups if g > 0) / sum(sizes)
    assert pc["eaters_share"] == pytest.approx(eaters)
    base = [g for g, _ in groups]
    assert min(base) - 1e-9 <= pc["mean_baseline_g"] <= max(base) + 1e-9
    # a group already past the curve's minimum after the control arm's change
    # gains nothing
    floor = float(MAIN_CURVE.f(60))
    for g, (b, _) in zip(pc["groups"], groups):
        if float(MAIN_CURVE.f(max(0, b + control))) == floor:
            assert g["log_hr"] == 0


@given(st.integers(0, 10**7), st.booleans())
def test_group_size_reads_back(n, grouped):
    """EvidenceRow.count reads '(n = N' back, with or without thousands commas."""
    written = f"{n:,}" if grouped else str(n)
    row = _row("r", population=f"participants who ate nuts (n = {written} of 7,216)")
    assert row.count() == n


# --------------------------------------------------------------------------
# Rounding in the fill (cost per life-year to $100, and fixed decimals)
# --------------------------------------------------------------------------


def _parse(text: str) -> Decimal:
    body = text.replace("$", "").replace(",", "").replace("%", "")
    return -Decimal(body[1:]) if body.startswith(MINUS) else Decimal(body)


@SETTINGS
@given(st.floats(-1e7, 1e7, allow_nan=False), st.integers(-3, 3))
def test_rounding_is_nearest_half_away_from_zero(x, ndigits):
    """number() and dollars() print x rounded to 10^-ndigits: a multiple of the
    step, within half a step, ties away from zero, and never a negative zero."""
    step = Decimal(1).scaleb(-ndigits)
    exact = Decimal(repr(x))
    for v in (fill_paper.number(x, ndigits), fill_paper.dollars(x, ndigits)):
        got = _parse(v.text)
        assert got % step == 0
        err = abs(got - exact)
        assert err <= step / 2
        if err == step / 2:
            assert abs(got) > abs(exact)
        if got == 0:
            assert MINUS not in v.text, v.text
    assert fill_paper.dollars(x, -2).kind == "dollars:-2"
