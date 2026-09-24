"""Dose curves, the bracket of causal multipliers, Monte Carlo draws, scenarios.

From age a0, nut intake moves from B to B + delta g/day and stays there. The
hazard at age a is multiplied by

    M(a) = exp(phi(a) * c * [f(B + delta) - f(B)])

for the all-cause members of the bracket, where f is a log relative risk curve
with f(0) = 0, c the causal multiplier and phi the phase-in (lifetable.phase_in).
Cause-restricted members apply the multiplier to one cause's share p(a) of the
hazard: M(a) = 1 - p(a) + p(a) * exp(phi(a) * beta).

Every effect size is read from data/evidence.yaml by row id (EVIDENCE_IDS) and
every curve point from data/curves/; structural constants live in ASSUMPTIONS.
Each draw's scenario reduces to one scalar log hazard multiplier beta, so the
engine evaluates the life table for all draws at once (lifetable.person_years).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq

from whatnut import data
from whatnut.lifetable import Baseline, life_expectancy, phase_in

# Every non-evidence number the model uses. Float literals anywhere else in
# src/whatnut fail tests/test_no_literals.py.
ASSUMPTIONS = {
    # --- unit conversions ---
    # LDL cholesterol: mg/dL per mmol/L (DESIGN decision 4; cholesterol's molar
    # mass, 386.65 g/mol, over 10)
    "ldl_mg_dl_per_mmol_l": 38.67,
    # Julian year; paper/fill_paper.py prints days with the same constant
    "days_per_year": 365.25,
    "g_per_kg": 1000,
    # --- Monte Carlo (DESIGN "Uncertainty") ---
    "mc_n": 20_000,
    "mc_seed": 20260923,  # modeling choice: the date the design was fixed
    # mean plus 80% and 95% intervals (DESIGN "Uncertainty")
    "percentiles": {"p10": 10, "p90": 90, "p2_5": 2.5, "p97_5": 97.5},
    # --- intervention ---
    # linear phase-in to full effect: Fadnes et al. 2022's 10 years (DESIGN
    # "Intervention"), with 0 and 20 as sensitivities
    "phase_in_years": 10,
    "phase_in_sensitivity_years": [0, 10, 20],
    # costs and life-years both discounted at 3% (DESIGN "Cost")
    "discount_rate": 0.03,
    # --- bracket (DESIGN "Bracket") ---
    "c_dial": [0.1, 0.33, 1],
    # modeling choice: the CVD-only carve-out takes the CVD curve at face value
    "cvd_only_c": 1,
    # --- dose curve sensitivity (b) (DESIGN decision 2): 90% of the per-28 g
    # effect reached at 15 g/day; Aune 2016 reports no further reduction above
    # 15-20 g/day (row aune2016_allcause_per28g, notes)
    "plateau_dose_g": 15,
    "plateau_share": 0.9,
    # --- randomized floor (DESIGN decision 4) ---
    # Jafari Azad 2020 prints no doses in the abstract (full text paywalled);
    # modeling choice: read its WMD as the effect of one serving of the size Del
    # Gobbo 2015 standardizes to (the per-g/day dose of this row's unit)
    "peanut_ldl_serving_row": "delgobbo2015_ldl_per28g",
    # --- ALA sensitivity (DESIGN decision 7) ---
    # Naghshi 2021's included intakes span 0.35-3.0 g/day (row
    # naghshi2021_ala_all_cause_per_g, support); tests check this against the row
    "ala_support_g": [0.35, 3.0],
    # second background scenario: a seed-heavy diet
    "ala_background_high_g": 5,
    # --- outputs (DESIGN "Outputs") ---
    "grid": {
        "sex": ["female", "male"],
        "a0": [30, 40, 50, 60, 70],
        "delta": [5, 10, 15, 20, 28, 40],
        "background": [0, 10, 20, 28],
    },
    # reference case: age 40, from no nuts to 28 g/day (one Aune serving)
    "reference": {"a0": 40, "delta": 28, "background": 0},
    "marginal_step_g": 10,
    "nuts": [
        "walnut",
        "almond",
        "pistachio",
        "pecan",
        "hazelnut",
        "macadamia",
        "cashew",
        "peanut",
    ],
    "tree_nuts_exclude": ["peanut"],  # peanuts are legumes (Del Gobbo 2015)
    # figure ranges (DESIGN; brief): grams 0-40, background 0-30, start ages 20-80
    "figure_dose_max_g": 40,
    "figure_background_max_g": 30,
    "figure_age_range": [20, 80],
}

# Evidence rows the model reads, by role.
EVIDENCE_IDS = {
    "rr28_all": "aune2016_allcause_per28g",
    "rr28_cvd": "aune2016_cvd_per28g_mortality",
    "rrr_intake": "schwingshackl2021_rrr_intake_vs_intake",
    "rrr_all_cause": "schwingshackl2021_rrr_all_cause",
    "rrr_overall": "schwingshackl2021_rrr_overall",
    # the floor is randomized evidence only: Del Gobbo's randomized trials
    "ldl_tree": "delgobbo2015_ldl_per28g_rct",
    # sensitivity: all 61 controlled trials, randomized and nonrandomized
    "ldl_tree_all_trials": "delgobbo2015_ldl_per28g",
    "ldl_peanut": "jafariazad2020_peanut_ldl",
    "ctt_chd": "ctt2010_chd_death_per_mmol",
    "ctt_all": "ctt2010_all_cause_per_mmol",
    "ala": "naghshi2021_ala_all_cause_per_g",
    "ala_background": "wweia_1720_ala_adults",
    # reference data: the baseline's sources and the reproduction targets
    "baseline_life_tables": "nvsr7406_life_tables_2023",
    "baseline_deaths": "nchs_mortality_2023",
    "fadnes_female": "fadnes2022_us_women_25g",
    "fadnes_male": "fadnes2022_us_men_25g",
}

# One column of standard-normal draws per uncertain input, in this order.
DRAW_COLUMNS = (
    "rr28_all",
    "rr28_cvd",
    "rrr_intake",
    "rrr_all_cause",
    "rrr_overall",
    "ldl_tree",
    "ldl_tree_all_trials",
    "ldl_peanut",
    "ctt_chd",
    "ctt_all",
    "ala",
)

CALIBRATION_STRATA = {
    "calibrated": "rrr_intake",
    "calibrated_all_cause": "rrr_all_cause",
    "calibrated_overall": "rrr_overall",
}


def dial_name(c: float) -> str:
    return f"c_{c:g}"


MEMBERS = (
    "floor_low",
    "floor_high",
    "cvd_only",
    "calibrated_all_cause",
    "calibrated_overall",
    "calibrated",
    "face_value",
    *(dial_name(c) for c in ASSUMPTIONS["c_dial"]),
)

MEMBER_DESCRIPTIONS = {
    "floor_low": (
        "Randomized floor, low: nut-trial LDL change x CTT CHD-death slope, "
        "CHD deaths only"
    ),
    "floor_high": (
        "Randomized floor, high: nut-trial LDL change x CTT all-cause slope, all deaths"
    ),
    "cvd_only": (
        "Aune CVD-mortality curve applied to the CVD share of deaths only (c = 1)"
    ),
    "calibrated_all_cause": (
        "Cohort curve x Schwingshackl RRR, all-cause-mortality stratum"
    ),
    "calibrated_overall": "Cohort curve x Schwingshackl RRR, overall",
    "calibrated": (
        "Cohort curve x Schwingshackl RRR, dietary intake vs intake stratum"
    ),
    "face_value": "Aune all-cause cohort curve at face value (c = 1)",
    **{
        dial_name(c): f"Aune all-cause cohort curve with c = {c:g}"
        for c in ASSUMPTIONS["c_dial"]
    },
}

STAT_NAMES = ("mean", *ASSUMPTIONS["percentiles"])


def summarize(x: np.ndarray) -> dict[str, float]:
    """Mean and the percentile stats of a vector of draws."""
    pct = ASSUMPTIONS["percentiles"]
    qs = np.percentile(x, list(pct.values()))
    return {"mean": float(np.mean(x)), **{k: float(v) for k, v in zip(pct, qs)}}


# --------------------------------------------------------------------------
# Dose curves
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Curve:
    """A log relative risk curve f(g) with f(0) = 0, at the point estimates."""

    name: str
    kind: str  # running_min_linear | pchip | plateau
    g: tuple[float, ...] = ()
    log_rr: tuple[float, ...] = ()
    log_rr_serving: float = 0
    serving_g: float = 0
    plateau_x: float = 0  # exp(-1/k) for the plateau shape

    def f(self, grams) -> np.ndarray:
        g = np.asarray(grams, dtype=float)
        if self.kind == "running_min_linear":
            return np.interp(g, self.g, self.log_rr)  # flat beyond the last point
        if self.kind == "pchip":
            gi = np.clip(g, self.g[0], self.g[-1])
            return PchipInterpolator(self.g, self.log_rr)(gi)
        if self.kind == "plateau":
            x = self.plateau_x
            return self.log_rr_serving * (1 - x**g) / (1 - x**self.serving_g)
        raise ValueError(self.kind)

    def delta_f(self, background: float, delta: float) -> float:
        return float(self.f(background + delta) - self.f(background))


def aune_running_min(outcome: str, name: str) -> Curve:
    """DESIGN decision 2 main case: Aune's points made nonincreasing by a running
    minimum, linear in log RR between points, flat beyond the last point."""
    g, rr = data.aune_curve(outcome)
    return Curve(
        name=name,
        kind="running_min_linear",
        g=g,
        log_rr=tuple(np.log(np.minimum.accumulate(rr))),
    )


def aune_pchip(outcome: str, name: str) -> Curve:
    """Sensitivity (a): the points as printed, PCHIP in log RR, flat beyond."""
    g, rr = data.aune_curve(outcome)
    return Curve(name=name, kind="pchip", g=g, log_rr=tuple(np.log(rr)))


def linear_plateau(row: data.EvidenceRow, name: str) -> Curve:
    """Sensitivity (b): f(g) = ln(RR28) (1 - e^(-g/k)) / (1 - e^(-28/k)), with k
    such that the share ASSUMPTIONS['plateau_share'] of the per-serving effect is
    reached at ASSUMPTIONS['plateau_dose_g']."""
    serving = row.per_grams()
    dose, share = ASSUMPTIONS["plateau_dose_g"], ASSUMPTIONS["plateau_share"]
    eps = np.finfo(float).eps

    def gap(x: float) -> float:
        return (1 - x**dose) / (1 - x**serving) - share

    x = brentq(gap, eps, 1 - eps)
    return Curve(
        name=name,
        kind="plateau",
        log_rr_serving=math.log(row.estimate),
        serving_g=serving,
        plateau_x=x,
    )


# --------------------------------------------------------------------------
# Inputs and draws
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Draws:
    """The run's single matrix of standard-normal draws (common random numbers:
    every scenario reads the same columns)."""

    z: np.ndarray  # (n, len(DRAW_COLUMNS))

    @classmethod
    def make(cls, n: int, seed: int) -> Draws:
        rng = np.random.Generator(np.random.PCG64(seed))
        return cls(z=rng.standard_normal((n, len(DRAW_COLUMNS))))

    @property
    def n(self) -> int:
        return self.z.shape[0]

    def col(self, name: str) -> np.ndarray:
        return self.z[:, DRAW_COLUMNS.index(name)]


@dataclass
class Model:
    n: int = ASSUMPTIONS["mc_n"]
    seed: int = ASSUMPTIONS["mc_seed"]
    vintage: str | None = None  # None: the main baseline; e.g. "2021" for the archive
    rows: dict[str, data.EvidenceRow] = field(init=False)
    draws: Draws = field(init=False)
    base: dict[str, Baseline] = field(init=False)
    shares: dict[str, data.CauseShares] = field(init=False)
    curves: dict[str, Curve] = field(init=False)
    cvd_curve: Curve = field(init=False)
    q: dict[str, np.ndarray] = field(init=False)  # per-draw quantities

    def __post_init__(self) -> None:
        self.rows = {role: data.row(rid) for role, rid in EVIDENCE_IDS.items()}
        self.draws = Draws.make(self.n, self.seed)
        sexes = ASSUMPTIONS["grid"]["sex"]
        self.base = {s: Baseline.load(s, self.vintage) for s in sexes}
        self.shares = {s: data.cause_shares(s, self.vintage) for s in sexes}
        self.curves = {
            "main": aune_running_min("all_cause_mortality", "main"),
            "pchip_as_printed": aune_pchip("all_cause_mortality", "pchip_as_printed"),
            "linear_plateau": linear_plateau(self.rows["rr28_all"], "linear_plateau"),
        }
        self.cvd_curve = aune_running_min("cvd_mortality", "cvd_main")
        self.q = self._per_draw_quantities()

    # ---- per-draw inputs -------------------------------------------------

    def _lognormal(self, role: str, spread: str = "ci") -> np.ndarray:
        """ln of a ratio drawn lognormally: from its CI (at the row's ci_level),
        or from its prediction interval."""
        r = self.rows[role]
        sd = r.log_se() if spread == "ci" else r.log_se_pi()
        return math.log(r.estimate) + sd * self.draws.col(role)

    def _per_draw_quantities(self) -> dict[str, np.ndarray]:
        q: dict[str, np.ndarray] = {}
        rr = self.rows
        # curve scale: each draw's per-28 g log RR relative to the point estimate
        q["ln_rr28_all"] = self._lognormal("rr28_all")
        q["scale_all"] = q["ln_rr28_all"] / math.log(rr["rr28_all"].estimate)
        ln_rr28_cvd = self._lognormal("rr28_cvd")
        q["scale_cvd"] = ln_rr28_cvd / math.log(rr["rr28_cvd"].estimate)
        # calibrated c = ln(RR28 * RRR) / ln(RR28), RRR from its prediction interval
        for member, role in CALIBRATION_STRATA.items():
            ln_rrr = self._lognormal(role, spread="pi")
            q[f"c_{member}"] = 1 + ln_rrr / q["ln_rr28_all"]
        # LDL change per gram/day (mg/dL), normal from the CI or from the P value
        tree = rr["ldl_tree"]
        q["ldl_tree_per_g"] = (
            tree.estimate + tree.se() * self.draws.col("ldl_tree")
        ) / tree.per_grams()
        tree_all = rr["ldl_tree_all_trials"]
        q["ldl_tree_all_trials_per_g"] = (
            tree_all.estimate + tree_all.se() * self.draws.col("ldl_tree_all_trials")
        ) / tree_all.per_grams()
        peanut = rr["ldl_peanut"]
        serving = data.row(ASSUMPTIONS["peanut_ldl_serving_row"]).per_grams()
        q["ldl_peanut_per_g"] = (
            peanut.estimate + peanut.se_from_p() * self.draws.col("ldl_peanut")
        ) / serving
        # CTT log rate ratios per 1 mmol/L LDL reduction
        q["ln_ctt_chd"] = self._lognormal("ctt_chd")
        q["ln_ctt_all"] = self._lognormal("ctt_all")
        # ALA log RR per g/day
        q["ln_rr_ala"] = self._lognormal("ala")
        return q

    def c(self, member: str) -> np.ndarray | float:
        """The causal multiplier for a cohort-curve member (scalar or per draw)."""
        if member == "face_value":
            return 1
        if member in CALIBRATION_STRATA:
            return self.q[f"c_{member}"]
        for c in ASSUMPTIONS["c_dial"]:
            if member == dial_name(c):
                return c
        raise KeyError(member)

    # ---- scenarios --------------------------------------------------------

    def ldl_mmol_reduction(self, delta: float, nut_group: str) -> np.ndarray:
        """LDL reduction (mmol/L, positive = lower LDL) per draw for +delta g/day,
        linear in dose (DESIGN decision 4)."""
        per_g = {
            "tree": self.q["ldl_tree_per_g"],
            "tree_all_trials": self.q["ldl_tree_all_trials_per_g"],
            "peanut": self.q["ldl_peanut_per_g"],
        }[nut_group]
        return -per_g * delta / ASSUMPTIONS["ldl_mg_dl_per_mmol_l"]

    def scenario(
        self,
        member: str,
        delta: float,
        background: float,
        curve: str = "main",
        nut_group: str = "tree",
        ala_g: float = 0,
    ) -> tuple[str, np.ndarray]:
        """(structure, beta): which share of the hazard the multiplier acts on
        ('all', 'cvd' or 'chd') and each draw's full-effect log multiplier.

        ``ala_g`` adds the ALA channel (grams of ALA inside the observed range)
        at the same causal multiplier as the class effect."""
        if member == "floor_low":
            return "chd", self.q["ln_ctt_chd"] * self.ldl_mmol_reduction(
                delta, nut_group
            )
        if member == "floor_high":
            return "all", self.q["ln_ctt_all"] * self.ldl_mmol_reduction(
                delta, nut_group
            )
        if member == "cvd_only":
            dfc = self.cvd_curve.delta_f(background, delta)
            return "cvd", ASSUMPTIONS["cvd_only_c"] * self.q["scale_cvd"] * dfc
        df = self.curves[curve].delta_f(background, delta)
        log_rr = self.q["scale_all"] * df + ala_g * self.q["ln_rr_ala"]
        return "all", self.c(member) * log_rr

    # ---- life-table engine -----------------------------------------------

    def cause_share(self, sex: str, a0: int, cause: str) -> np.ndarray:
        ages = self.base[sex].ages_from(a0)
        return np.asarray(self.shares[sex].at_ages(ages, cause))

    def log_mult(
        self, sex: str, a0: int, years: int, structure: str, beta: np.ndarray
    ) -> np.ndarray:
        phi = phase_in(a0, self.base[sex].omega, years)
        x = np.multiply.outer(beta, phi)
        if structure == "all":
            return x
        p = self.cause_share(sex, a0, structure)
        return np.log1p(p * np.expm1(x))  # ln(1 - p + p e^x)

    def baseline_le(
        self, sex: str, a0: int, weights: np.ndarray | None = None
    ) -> float:
        base = self.base[sex]
        zeros = np.zeros((1, base.omega - a0 + 1))
        return float(life_expectancy(base, a0, zeros, weights)[0])

    def gain(
        self,
        sex: str,
        a0: int,
        structure: str,
        beta: np.ndarray,
        years: int | None = None,
        weights: np.ndarray | None = None,
    ) -> np.ndarray:
        """Change in (weighted) remaining life expectancy at a0, per draw."""
        years = ASSUMPTIONS["phase_in_years"] if years is None else years
        beta = np.asarray(beta, dtype=float)
        if not np.any(beta):
            return np.zeros(beta.shape)
        base = self.base[sex]
        e0 = self.baseline_le(sex, a0, weights)
        out = np.empty(beta.shape)
        step = max(1, (1 << 22) // (base.omega - a0 + 1))  # ~4M cells per chunk
        for i in range(0, beta.size, step):
            lm = self.log_mult(sex, a0, years, structure, beta[i : i + step])
            out[i : i + step] = life_expectancy(base, a0, lm, weights) - e0
        return out

    def discount_weights(self, sex: str, a0: int) -> np.ndarray:
        """Discount factor for person-years at each age a0..omega: mid-year for
        single years; the open interval at its baseline midpoint."""
        base = self.base[sex]
        t = np.arange(base.omega - a0 + 1) + 1 / 2
        t[-1] = base.omega - a0 + base.e_open / 2
        return (1 + ASSUMPTIONS["discount_rate"]) ** -t
