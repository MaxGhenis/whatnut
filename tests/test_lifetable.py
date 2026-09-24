"""The baseline reproduces the published life tables; the engine is exact."""

from __future__ import annotations

import math

import numpy as np
import pytest

from whatnut.data import SEXES
from whatnut.lifetable import Baseline, baseline_ex, life_expectancy, phase_in


@pytest.mark.parametrize("sex", SEXES)
def test_baseline_reproduces_published_ex_at_every_age(sex):
    """DESIGN decision 5: mid-year convention with the table's own e_omega
    reproduces e_x within 0.01 years at every age."""
    base = Baseline.load(sex)
    ours = baseline_ex(base)
    gap = np.abs(ours - base.ex_published)
    worst = int(np.argmax(gap))
    print(f"{sex}: max |e_x - published| = {gap.max():.5f} years at age {worst}")
    assert gap.max() < 0.01


def _loop_le(base: Baseline, a0: int, mult: list[float]) -> float:
    """Scalar reference implementation of the life table (no numpy tricks)."""
    alive, total = 1.0, 0.0
    for i, a in enumerate(range(a0, base.omega)):
        nxt = alive * math.exp(-base.hazard[a] * mult[i])
        total += (alive + nxt) / 2
        alive = nxt
    return total + alive * base.e_open / mult[-1]


@pytest.mark.parametrize("sex", SEXES)
@pytest.mark.parametrize("a0", [0, 40, 85, 99])
def test_vectorized_engine_matches_scalar_loop(sex, a0):
    base = Baseline.load(sex)
    rng = np.random.default_rng(1)
    log_mult = rng.normal(0, 0.2, size=(3, base.omega - a0 + 1))
    got = life_expectancy(base, a0, log_mult)
    for i in range(3):
        want = _loop_le(base, a0, list(np.exp(log_mult[i])))
        assert got[i] == pytest.approx(want, rel=1e-12)


def test_open_interval_scales_with_multiplier():
    base = Baseline.load("female")
    a0 = base.omega
    lm = np.log(np.array([[2.0]]))
    assert life_expectancy(base, a0, lm)[0] == pytest.approx(base.e_open / 2)


def test_lower_hazard_raises_life_expectancy():
    base = Baseline.load("male")
    n = base.omega - 40 + 1
    e = life_expectancy(
        base, 40, np.vstack([np.zeros(n), np.full(n, -0.1), np.full(n, 0.1)])
    )
    assert e[1] > e[0] > e[2]


def test_phase_in_is_linear_mid_year_ramp():
    phi = phase_in(40, 100, 10)
    assert phi[0] == pytest.approx(1 / 20)
    assert phi[9] == pytest.approx(19 / 20)
    assert np.all(phi[10:] == 1)
    assert np.all(np.diff(phi) >= 0)
    # two years in, the average effect over the two years is 10% and the ramp is at 20%
    assert phi[:2].mean() == pytest.approx(1 / 10)
    assert np.all(phase_in(40, 100, 0) == 1)
    assert phase_in(40, 100, 20)[19] == pytest.approx(39 / 40)
