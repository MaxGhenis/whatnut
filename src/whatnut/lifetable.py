"""Remaining life expectancy under age-specific hazard multipliers.

Single years of age 0..omega-1 carry the table's death probabilities q_x; age
omega (100) is the open interval. With hazard h_x = -ln(1 - q_x), a person alive
at a0 survives to x + 1 with probability exp(-sum_{y=a0..x} m_y h_y), where m_y is
the hazard multiplier at age y (1 at baseline).

Person-years follow the mid-year convention: deaths in [x, x + 1) happen on
average halfway through, so L_x = (l_x + l_{x+1}) / 2. The open interval uses the
table's own e_omega (DESIGN decision 5): at baseline T_omega = l_omega * e_omega, and
under a multiplier m_omega the open interval's expectation is e_omega / m_omega
(a constant hazard scaled by m). At baseline this reproduces the published e_x
column (tests/test_lifetable.py).

Every function is vectorized over rows of ``log_mult`` (one row per Monte Carlo
draw or scenario).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from whatnut import data


@dataclass(frozen=True)
class Baseline:
    """A sex's baseline mortality: hazards for single years 0..omega-1 and e_omega."""

    sex: str
    hazard: np.ndarray  # (omega,)
    e_open: float
    omega: int
    ex_published: np.ndarray  # (omega + 1,)

    @classmethod
    def load(cls, sex: str, vintage: str | None = None) -> Baseline:
        lt = data.life_table(sex, vintage)
        q = np.asarray(lt.qx[:-1], dtype=float)
        if not np.all((q >= 0) & (q < 1)):
            raise data.DataIntegrityError(f"{sex} q_x outside [0, 1) below omega")
        return cls(
            sex=sex,
            hazard=-np.log1p(-q),
            e_open=float(lt.ex[-1]),
            omega=lt.omega,
            ex_published=np.asarray(lt.ex, dtype=float),
        )

    def ages_from(self, a0: int) -> np.ndarray:
        """Ages a0..omega (the last is the open interval)."""
        return np.arange(a0, self.omega + 1)


def person_years(base: Baseline, a0: int, log_mult: np.ndarray) -> np.ndarray:
    """Expected person-years lived at each age a0..omega by a person alive at a0.

    ``log_mult`` has shape (m, omega - a0 + 1): the log hazard multiplier at each
    age, the last column for the open interval. Returns the same shape; the last
    column is the open interval's expected years.
    """
    log_mult = np.atleast_2d(np.asarray(log_mult, dtype=float))
    h = base.hazard[a0:]
    if log_mult.shape[1] != h.size + 1:
        raise ValueError(
            f"log_mult needs {h.size + 1} columns (ages {a0}..{base.omega})"
        )
    cum = np.cumsum(h * np.exp(log_mult[:, :-1]), axis=1)
    surv = np.exp(-cum)  # l at ages a0+1..omega, with l_a0 = 1
    l_start = np.hstack([np.ones((log_mult.shape[0], 1)), surv])  # l at a0..omega
    py = np.empty_like(log_mult)
    py[:, :-1] = (l_start[:, :-1] + l_start[:, 1:]) / 2
    py[:, -1] = l_start[:, -1] * base.e_open * np.exp(-log_mult[:, -1])
    return py


def life_expectancy(
    base: Baseline, a0: int, log_mult: np.ndarray, weights: np.ndarray | None = None
) -> np.ndarray:
    """Remaining life expectancy at a0 for each row of ``log_mult`` (m,).

    With ``weights`` (one per age a0..omega), returns the weighted sum of
    person-years instead, e.g. discounted life-years.
    """
    py = person_years(base, a0, log_mult)
    if weights is None:
        return py.sum(axis=1)
    return py @ weights


def baseline_ex(base: Baseline) -> np.ndarray:
    """e_x at every age 0..omega with no intervention."""
    out = np.empty(base.omega + 1)
    for a in range(base.omega):
        out[a] = life_expectancy(base, a, np.zeros((1, base.omega - a + 1)))[0]
    out[base.omega] = base.e_open
    return out


def phase_in(a0: int, omega: int, years: int) -> np.ndarray:
    """Share of the full effect at each age a0..omega (DESIGN: linear from 0 at a0
    to 1 at a0 + T).

    Each single year of age gets the ramp's average over that year, which for a
    linear ramp with integer a0 and T is its value at mid-year, (x - a0 + 1/2) / T.
    T = 0 means the full effect from a0.
    """
    ages = np.arange(a0, omega + 1)
    if years == 0:
        return np.ones(ages.shape)
    return np.clip((ages - a0 + 1 / 2) / years, 0, 1)
