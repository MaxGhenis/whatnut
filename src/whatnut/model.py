"""Dose curves, the scenarios' causal multipliers, Monte Carlo draws.

From age a0, nut intake moves from B to B + delta g/day and stays there. The
hazard at age a is multiplied by

    M(a) = exp(phi(a) * c * [f(B + delta) - f(B)])

for the cohort-curve scenarios, where f is a log relative risk curve with
f(0) = 0, c the causal multiplier and phi the phase-in (lifetable.phase_in).
Cause-restricted scenarios apply the multiplier to one cause's share p(a) of the
hazard: M(a) = 1 - p(a) + p(a) * exp(phi(a) * beta).

Every effect size is read from data/evidence.yaml by row id (EVIDENCE_IDS) and
every curve point from data/curves/; structural constants live in ASSUMPTIONS.
Each draw's scenario reduces to one scalar log hazard multiplier beta, so the
engine evaluates the life table on a fine grid of multipliers spanning the draws
and interpolates (Model.gain; Model.exact_gain evaluates every draw).
A Variant names the choices a sensitivity changes from the main case.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.optimize import brentq
from scipy.stats import t as student_t

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
    # each draw's gain depends on the draw only through its scalar log
    # multiplier, so the engine evaluates the life table on this many evenly
    # spaced multipliers spanning the draws and interpolates linearly (tests
    # check the error against exact evaluation is under 0.001 day)
    "gain_grid_points": 1025,
    # --- intervention ---
    # linear phase-in to full effect: Fadnes et al. 2022's 10 years (DESIGN
    # "Intervention"), with 0 and 20 as sensitivities
    "phase_in_years": 10,
    "phase_in_sensitivity_years": [0, 10, 20],
    # costs and life-years both discounted at 3% (DESIGN "Cost")
    "discount_rate": 0.03,
    # --- scenarios (DESIGN "Scenarios") ---
    "c_dial": [0.1, 0.33, 1],
    # modeling choice: the cardiovascular-only scenario takes the CVD curve at
    # face value
    "cvd_only_c": 1,
    # --- dose curve sensitivity (b) (DESIGN decision 2): 90% of the per-28 g
    # effect reached at 15 g/day; Aune 2016 reports no further reduction above
    # 15-20 g/day (row aune2016_allcause_per28g, notes)
    "plateau_dose_g": 15,
    "plateau_share": 0.9,
    # --- any-versus-none sensitivity (DESIGN decision 12): Aune's first
    # tabulated intake above zero (Table S15; tests check it against the curve).
    # The curve is measured from here, so the step from none to this much
    # counts for nothing.
    "any_vs_none_g": 5,
    # --- age sensitivity (DESIGN decision 12), a modeling choice: the log
    # relative risk keeps full strength to 65, falls linearly to half at 85 and
    # stays at half
    "age_attenuation": {"from_age": 65, "to_age": 85, "weight_at_end": 0.5},
    # --- LDL pathway (DESIGN decision 4) ---
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
    # --- calibration: subsets of Schwingshackl 2021's 23 intake-v-intake pairs
    # (data/calibration/; DESIGN decision 3, revised). 'core' drops the pairs
    # whose topic or outcome names these words (pregnancy outcomes, colorectal
    # cancer and adenoma); 'protective' keeps pairs whose cohort RR is below 1.
    "intake_pairs_core_exclude": {"topic": ["pregnancy"], "outcome": ["colorectal"]},
    # --- outputs (DESIGN "Outputs") ---
    "grid": {
        "sex": ["female", "male"],
        "a0": [30, 40, 50, 60, 70],
        "delta": [5, 10, 15, 20, 28, 40],
        "background": [0, 10, 20, 28],
    },
    # reference case: age 40, from no nuts to 15 g/day, the intake at which the
    # main curve first reaches its lowest relative risk (tests check)
    "reference": {"a0": 40, "delta": 15, "background": 0},
    # the reference table adds one Aune serving (28 g) beside the reference dose
    "reference_table_deltas": [15, 28],
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
    # sensitivities: the same curve rescaled to other per-28 g estimates
    "rr28_fu10": "aune2016_allcause_fu10plus",
    "rr28_large": "aune2016_allcause_per28g_excl_small_studies",
    "rr28_cvd": "aune2016_cvd_per28g_mortality",
    # calibration strata (Schwingshackl 2021); the main calibration uses all
    # 71 pairs (DESIGN decision 3)
    "rrr_overall": "schwingshackl2021_rrr_overall",
    "rrr_all_cause": "schwingshackl2021_rrr_all_cause",
    "rrr_protective": "schwingshackl2021_rrr_overall_cohort_rr_below_1",
    "rrr_intake": "schwingshackl2021_rrr_intake_vs_intake",
    # the LDL pathway is randomized evidence only: Del Gobbo's randomized trials
    "ldl_tree": "delgobbo2015_ldl_per28g_rct",
    # sensitivity: all 61 controlled trials, randomized and nonrandomized
    "ldl_tree_all_trials": "delgobbo2015_ldl_per28g",
    "ldl_peanut": "jafariazad2020_peanut_ldl",
    "ctt_chd": "ctt2010_chd_death_per_mmol",
    "ctt_all": "ctt2010_all_cause_per_mmol",
    "ala": "naghshi2021_ala_all_cause_per_g",
    "ala_fixed": "naghshi2021_ala_all_cause_per_g_fixed",
    "ala_background_female": "wweia_1720_ala_women",
    "ala_background_male": "wweia_1720_ala_men",
    # reference data: the baseline's sources and the reproduction targets
    "baseline_life_tables": "nvsr7406_life_tables_2023",
    "baseline_deaths": "nchs_mortality_2023",
    "fadnes_female": "fadnes2022_us_women_25g",
    "fadnes_male": "fadnes2022_us_men_25g",
    # the check of PREDIMED's contrast against the main curve
    # (pipeline.predimed_check): baseline intake groups, each arm's change, and
    # the trial's all-cause hazard ratio and median follow-up
    "predimed_baseline_never": "guaschferre2013_predimed_baseline_nuts_never",
    "predimed_baseline_1to3": "guaschferre2013_predimed_baseline_nuts_1to3",
    "predimed_baseline_over3": "guaschferre2013_predimed_baseline_nuts_over3",
    "predimed_change_nuts": "guaschferre2013_predimed_nut_change_nut_arm",
    "predimed_change_control": "guaschferre2013_predimed_nut_change_control_arm",
    "predimed_death": "predimed2018_nuts_all_cause_death",
}

PREDIMED_BASELINE_ROLES = (
    "predimed_baseline_never",
    "predimed_baseline_1to3",
    "predimed_baseline_over3",
)

# The Schwingshackl pairs nearest to nuts (DESIGN decision 13): the three ALA
# and three Mediterranean-diet intake pairs, pooled here by random effects.
ANALOG_PAIR_IDS = (
    "schwingshackl2021_pair_ala_cvd",
    "schwingshackl2021_pair_ala_cvd_mortality",
    "schwingshackl2021_pair_ala_chd",
    "schwingshackl2021_pair_med_cvd_mortality",
    "schwingshackl2021_pair_med_cv_events",
    "schwingshackl2021_pair_med_all_cause",
)

# One column of standard-normal draws per uncertain input, in this order.
# Alternative per-28 g estimates (rr28_fu10, rr28_large) and the fixed-effect
# ALA slope reuse their main input's column (common random numbers).
DRAW_COLUMNS = (
    "rr28_all",
    "rr28_cvd",
    "rrr_overall",
    "rrr_all_cause",
    "rrr_protective",
    "rrr_intake",
    "rrr_analog",
    "ldl_tree",
    "ldl_tree_all_trials",
    "ldl_peanut",
    "ctt_chd",
    "ctt_all",
    "ala",
)

CALIBRATION_STRATA = {
    "calibrated": "rrr_overall",
    "calibrated_mortality": "rrr_all_cause",
    "calibrated_protective": "rrr_protective",
    "calibrated_analog": "rrr_analog",
    "calibrated_diet": "rrr_intake",
}

CALIBRATION_ANCHORS = ("linear", "curve")

# The per-28 g estimates a Variant can scale the curve by (Variant.rr_role). Each
# calibration's c is computed against the estimate that scales the curve.
RR_ROLES = ("rr28_all", "rr28_fu10", "rr28_large")


def dial_name(c: float) -> str:
    return f"c_{c:g}"


MEMBERS = (
    "ldl_chd",
    "ldl_all",
    "cvd_only",
    "calibrated_mortality",
    "calibrated",
    "calibrated_protective",
    "calibrated_analog",
    "calibrated_diet",
    "face_value",
    *(dial_name(c) for c in ASSUMPTIONS["c_dial"]),
)

# The scenarios the paper reports throughout; the other calibrations are
# sensitivities.
MAIN_MEMBERS = (
    "ldl_chd",
    "ldl_all",
    "cvd_only",
    "calibrated_mortality",
    "calibrated",
    "face_value",
)

LDL_MEMBERS = ("ldl_chd", "ldl_all")

MEMBER_DESCRIPTIONS = {
    "ldl_chd": (
        "LDL pathway, coronary deaths: randomized nut-trial LDL change x CTT "
        "CHD-death slope, applied to coronary deaths only"
    ),
    "ldl_all": (
        "LDL pathway, all deaths: randomized nut-trial LDL change x CTT all-cause "
        "slope, applied to all deaths"
    ),
    "cvd_only": (
        "Cardiovascular deaths only: Aune CVD-mortality curve applied to the "
        "cardiovascular share of deaths (c = 1)"
    ),
    "calibrated_mortality": (
        "Mortality calibration: cohort curve scaled by Schwingshackl's RRR for "
        "all-cause-mortality pairs"
    ),
    "calibrated": (
        "Main calibration: cohort curve scaled by Schwingshackl's RRR, all 71 pairs"
    ),
    "calibrated_protective": (
        "Cohort curve scaled by Schwingshackl's RRR for pairs whose cohort estimate "
        "was protective"
    ),
    "calibrated_analog": (
        "Cohort curve scaled by the pooled RRR of the six ALA and Mediterranean-diet "
        "intake pairs"
    ),
    "calibrated_diet": (
        "Cohort curve scaled by Schwingshackl's RRR, dietary intake vs intake pairs"
    ),
    "face_value": "Aune all-cause cohort curve at face value (c = 1)",
    **{
        dial_name(c): f"Aune all-cause cohort curve with c = {c:g}"
        for c in ASSUMPTIONS["c_dial"]
    },
}

# The one name each scenario goes by in the paper's prose, tables and figures.
SCENARIO_LABEL = {
    "ldl_chd": "LDL pathway, coronary deaths",
    "ldl_all": "LDL pathway, all deaths",
    "cvd_only": "Cardiovascular deaths only",
    "calibrated_mortality": "Mortality calibration",
    "calibrated": "Main calibration",
    "calibrated_protective": "Protective-pairs calibration",
    "calibrated_analog": "Nearest-pairs calibration",
    "calibrated_diet": "Diet calibration",
    "face_value": "Face value",
}

STAT_NAMES = ("mean", *ASSUMPTIONS["percentiles"])


def summarize(x: np.ndarray) -> dict[str, float]:
    """Mean and the percentile stats of a vector of draws."""
    pct = ASSUMPTIONS["percentiles"]
    qs = np.percentile(x, list(pct.values()))
    return {"mean": float(np.mean(x)), **{k: float(v) for k, v in zip(pct, qs)}}


@dataclass(frozen=True)
class Variant:
    """The choices a sensitivity changes from the main case (the defaults)."""

    curve: str = "main"  # key of Model.curves
    rr_role: str = "rr28_all"  # the per-28 g estimate that scales the curve
    anchor: str = "linear"  # calibration anchor (CALIBRATION_ANCHORS)
    ldl: str = "tree"  # LDL input of the LDL-pathway scenarios
    # leave external-cause deaths out (cohort-curve scenarios and ldl_all)
    exclude_external: bool = False
    attenuate_with_age: bool = False  # ASSUMPTIONS["age_attenuation"]
    phase_in_years: int | None = None  # None: ASSUMPTIONS["phase_in_years"]


MAIN = Variant()


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
    start_g: float = 0  # intakes below this count as none (f measured from here)

    def _f(self, g: np.ndarray) -> np.ndarray:
        if self.kind == "running_min_linear":
            return np.interp(g, self.g, self.log_rr)  # flat beyond the last point
        if self.kind == "pchip":
            gi = np.clip(g, self.g[0], self.g[-1])
            return PchipInterpolator(self.g, self.log_rr)(gi)
        if self.kind == "plateau":
            x = self.plateau_x
            return self.log_rr_serving * (1 - x**g) / (1 - x**self.serving_g)
        raise ValueError(self.kind)

    def f(self, grams) -> np.ndarray:
        g = np.asarray(grams, dtype=float)
        if self.start_g:
            s = np.full(g.shape, self.start_g)
            return self._f(np.maximum(g, s)) - self._f(s)
        return self._f(g)

    def delta_f(self, background: float, delta: float) -> float:
        return float(self.f(background + delta) - self.f(background))


def aune_running_min(outcome: str, name: str, start_g: float = 0) -> Curve:
    """DESIGN decision 2 main case: Aune's points made nonincreasing by a running
    minimum, linear in log RR between points, flat beyond the last point."""
    g, rr = data.aune_curve(outcome)
    return Curve(
        name=name,
        kind="running_min_linear",
        g=g,
        log_rr=tuple(np.log(np.minimum.accumulate(rr))),
        start_g=start_g,
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
# Pooling calibration pairs
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Pool:
    """A DerSimonian-Laird random-effects pool of k ratios on the log scale."""

    k: int
    mu: float  # pooled ln ratio
    se: float  # its standard error
    tau2: float  # between-row variance of ln ratio (0 when Q <= k - 1)
    q: float  # Cochran's Q
    level: float  # CI and prediction-interval level (the rows' ci_level)
    half_pi: float  # half-width of the prediction interval on the log scale

    def summary(self) -> dict[str, float | int | list[float]]:
        """Estimate, CI and prediction interval on the ratio scale, with k, tau2
        and Q, for results.json."""
        z = data.z_for(self.level)
        return {
            "estimate": math.exp(self.mu),
            "ci": [math.exp(self.mu - z * self.se), math.exp(self.mu + z * self.se)],
            "pi": [math.exp(self.mu - self.half_pi), math.exp(self.mu + self.half_pi)],
            "level": self.level,
            "k": self.k,
            "tau2": self.tau2,
            "q": self.q,
        }


def pool_stats(rows: list[data.EvidenceRow], label: str = "pool") -> Pool:
    """DerSimonian-Laird random-effects pool of ratio rows on the log scale,
    with the Higgins-Thompson-Spiegelhalter prediction interval (t, k - 2 df)."""
    level = rows[0].ci_level
    if any(r.ci_level != level for r in rows):
        raise data.DataIntegrityError(f"{label}: pooled rows mix CI levels")
    y = np.log([r.estimate for r in rows])
    v = np.array([r.log_se() for r in rows]) ** 2
    w = 1 / v
    mu_fixed = np.sum(w * y) / np.sum(w)
    q = float(np.sum(w * (y - mu_fixed) ** 2))
    k = len(rows)
    tau2 = float(max(0, (q - (k - 1)) / (np.sum(w) - np.sum(w**2) / np.sum(w))))
    ws = 1 / (v + tau2)
    mu = float(np.sum(ws * y) / np.sum(ws))
    se = float(np.sqrt(1 / np.sum(ws)))
    tq = float(student_t.ppf(1 - (1 - level) / 2, k - 2))
    half_pi = tq * math.sqrt(tau2 + se**2)
    return Pool(k=k, mu=mu, se=se, tau2=tau2, q=q, level=level, half_pi=half_pi)


def pool_ratios(rows: list[data.EvidenceRow], row_id: str) -> data.EvidenceRow:
    """pool_stats returned as a row the model reads like any other."""
    p = pool_stats(rows, row_id)
    s = p.summary()
    return data.EvidenceRow(
        id=row_id,
        kind="calibration_corpus",
        measure="RRR",
        unit=None,
        estimate=s["estimate"],
        ci_low=s["ci"][0],
        ci_high=s["ci"][1],
        ci_level=p.level,
        pi_low=s["pi"][0],
        pi_high=s["pi"][1],
        support=None,
        notes=(
            f"Random-effects (DerSimonian-Laird) pool of {p.k} rows: "
            + ", ".join(r.id for r in rows)
            + f"; tau2 = {p.tau2:.4g}, Q = {p.q:.4g}"
        ),
        source={},
        verified={},
    )


def intake_pair_subsets() -> dict[str, list[data.EvidenceRow]]:
    """Schwingshackl 2021's 23 intake-v-intake pairs (data/calibration/) as ratio
    rows ``intake_pair_<line>``, in the subsets the paper pools: all 23, the
    'core' pairs without pregnancy or colorectal outcomes
    (ASSUMPTIONS['intake_pairs_core_exclude']), and the pairs whose cohort RR was
    below 1. The rows take the CI level of the published intake stratum."""
    level = data.row(EVIDENCE_IDS["rrr_intake"]).ci_level
    drop = ASSUMPTIONS["intake_pairs_core_exclude"]
    pairs = data.intake_pairs()
    rows = [
        data.EvidenceRow(
            id=f"intake_pair_{i}",
            kind="calibration_corpus",
            measure="RRR",
            unit=None,
            estimate=p["rrr"],
            ci_low=p["ci_low"],
            ci_high=p["ci_high"],
            ci_level=level,
            pi_low=None,
            pi_high=None,
            support=None,
            notes=None,
            source={},
            verified={},
            exposure=p["topic"],
            outcome=p["outcome"],
        )
        for i, p in enumerate(pairs, start=1)
    ]

    def core(p: dict) -> bool:
        return not any(
            word in p[field].lower() for field, words in drop.items() for word in words
        )

    keep = {
        "all": [True for _ in pairs],
        "core": [core(p) for p in pairs],
        "protective": [p["cohort_rr"] < 1 for p in pairs],
    }
    return {name: [r for r, k in zip(rows, flags) if k] for name, flags in keep.items()}


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
        self.rows["rrr_analog"] = pool_ratios(
            [data.row(rid) for rid in ANALOG_PAIR_IDS], "pooled_analog_pairs"
        )
        self.draws = Draws.make(self.n, self.seed)
        sexes = ASSUMPTIONS["grid"]["sex"]
        self.base = {s: Baseline.load(s, self.vintage) for s in sexes}
        self.shares = {s: data.cause_shares(s, self.vintage) for s in sexes}
        self.curves = {
            "main": aune_running_min("all_cause_mortality", "main"),
            "pchip_as_printed": aune_pchip("all_cause_mortality", "pchip_as_printed"),
            "linear_plateau": linear_plateau(self.rows["rr28_all"], "linear_plateau"),
            "from_any": aune_running_min(
                "all_cause_mortality", "from_any", ASSUMPTIONS["any_vs_none_g"]
            ),
        }
        self.cvd_curve = aune_running_min("cvd_mortality", "cvd_main")
        self.q = self._per_draw_quantities()

    # ---- per-draw inputs -------------------------------------------------

    def _lognormal(
        self, role: str, spread: str = "ci", column: str | None = None
    ) -> np.ndarray:
        """ln of a ratio drawn lognormally: from its CI (at the row's ci_level),
        or from its prediction interval, using the draw column of ``column``
        (default: the role's own)."""
        r = self.rows[role]
        sd = r.log_se() if spread == "ci" else r.log_se_pi()
        return math.log(r.estimate) + sd * self.draws.col(column or role)

    def _per_draw_quantities(self) -> dict[str, np.ndarray]:
        q: dict[str, np.ndarray] = {}
        rr = self.rows
        # curve scale: each draw's per-28 g log RR relative to the main point
        # estimate; alternative per-28 g estimates share the main draw column
        ln_rr28 = math.log(rr["rr28_all"].estimate)
        for role in RR_ROLES:
            q[f"ln_rr28:{role}"] = self._lognormal(role, column="rr28_all")
            q[f"scale:{role}"] = q[f"ln_rr28:{role}"] / ln_rr28
        ln_rr28_cvd = self._lognormal("rr28_cvd")
        q["scale_cvd"] = ln_rr28_cvd / math.log(rr["rr28_cvd"].estimate)
        # calibrated c: the cohort log RR plus ln RRR, over the cohort log RR,
        # with RRR from its prediction interval, against the per-28 g estimate
        # that scales the curve (rr_role). Anchor 'linear' takes the cohort log
        # RR as that per-28 g estimate; 'curve' as the main curve, scaled by the
        # same draw, at that dose.
        serving = rr["rr28_all"].per_grams()
        f_serving = float(self.curves["main"].f(serving))
        for member, role in CALIBRATION_STRATA.items():
            ln_rrr = self._lognormal(role, spread="pi")
            q[f"ln_rrr:{member}"] = ln_rrr
            for rr_role in RR_ROLES:
                anchors = {
                    "linear": q[f"ln_rr28:{rr_role}"],
                    "curve": q[f"scale:{rr_role}"] * f_serving,
                }
                for anchor, ln_anchor in anchors.items():
                    q[f"c:{member}:{anchor}:{rr_role}"] = 1 + ln_rrr / ln_anchor
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
        serving_ldl = data.row(ASSUMPTIONS["peanut_ldl_serving_row"]).per_grams()
        q["ldl_peanut_per_g"] = (
            peanut.estimate + peanut.se_from_p() * self.draws.col("ldl_peanut")
        ) / serving_ldl
        # CTT log rate ratios per 1 mmol/L LDL reduction
        q["ln_ctt_chd"] = self._lognormal("ctt_chd")
        q["ln_ctt_all"] = self._lognormal("ctt_all")
        # ALA log RR per g/day: random effects, and fixed effect on the same column
        q["ln_rr_ala"] = self._lognormal("ala")
        q["ln_rr_ala_fixed"] = self._lognormal("ala_fixed", column="ala")
        return q

    def c(
        self, member: str, anchor: str = "linear", rr_role: str = "rr28_all"
    ) -> np.ndarray | float:
        """The causal multiplier for a cohort-curve member (scalar or per draw).
        A calibration's c is measured against the per-28 g estimate ``rr_role``
        that scales the curve (DESIGN decision 12, revised)."""
        if member == "face_value":
            return 1
        if member in CALIBRATION_STRATA:
            return self.q[f"c:{member}:{anchor}:{rr_role}"]
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
        v: Variant = MAIN,
        ala_g: float = 0,
        ala_role: str = "ala",
    ) -> tuple[str, np.ndarray]:
        """(structure, beta): which share of the hazard the multiplier acts on
        ('all', 'nonexternal', 'cvd' or 'chd') and each draw's full-effect log
        multiplier.

        ``ala_g`` adds the ALA channel (grams of ALA inside the observed range)
        at the same causal multiplier as the class effect."""
        if member == "ldl_chd":
            return "chd", self.q["ln_ctt_chd"] * self.ldl_mmol_reduction(delta, v.ldl)
        if member == "ldl_all":
            structure = "nonexternal" if v.exclude_external else "all"
            beta = self.q["ln_ctt_all"] * self.ldl_mmol_reduction(delta, v.ldl)
            return structure, beta
        if member == "cvd_only":
            dfc = self.cvd_curve.delta_f(background, delta)
            return "cvd", ASSUMPTIONS["cvd_only_c"] * self.q["scale_cvd"] * dfc
        df = self.curves[v.curve].delta_f(background, delta)
        log_rr = self.q[f"scale:{v.rr_role}"] * df
        if ala_g:
            ala_key = "ln_rr_ala" if ala_role == "ala" else "ln_rr_ala_fixed"
            log_rr = log_rr + ala_g * self.q[ala_key]
        structure = "nonexternal" if v.exclude_external else "all"
        return structure, self.c(member, v.anchor, v.rr_role) * log_rr

    # ---- life-table engine -----------------------------------------------

    def cause_share(self, sex: str, a0: int, cause: str) -> np.ndarray:
        ages = self.base[sex].ages_from(a0)
        if cause == "nonexternal":
            return 1 - np.asarray(self.shares[sex].at_ages(ages, "external"))
        return np.asarray(self.shares[sex].at_ages(ages, cause))

    def age_weight(self, sex: str, a0: int) -> np.ndarray:
        """ASSUMPTIONS['age_attenuation']: the share of the log relative risk kept
        at each age a0..omega."""
        at = ASSUMPTIONS["age_attenuation"]
        ages = self.base[sex].ages_from(a0)
        ramp = np.clip((ages - at["from_age"]) / (at["to_age"] - at["from_age"]), 0, 1)
        return 1 - (1 - at["weight_at_end"]) * ramp

    def log_mult(
        self,
        sex: str,
        a0: int,
        years: int,
        structure: str,
        beta: np.ndarray,
        attenuate: bool = False,
    ) -> np.ndarray:
        phi = phase_in(a0, self.base[sex].omega, years)
        if attenuate:
            phi = phi * self.age_weight(sex, a0)
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
        attenuate: bool = False,
    ) -> np.ndarray:
        """Change in (weighted) remaining life expectancy at a0, per draw."""
        beta = np.asarray(beta, dtype=float)
        if not np.any(beta):
            return np.zeros(beta.shape)
        return self.exact_gain(
            sex, a0, structure, beta, years, weights, attenuate, interpolate=True
        )

    def exact_gain(
        self,
        sex: str,
        a0: int,
        structure: str,
        beta: np.ndarray,
        years: int | None = None,
        weights: np.ndarray | None = None,
        attenuate: bool = False,
        interpolate: bool = False,
    ) -> np.ndarray:
        """gain() evaluated for every draw, or (``interpolate``) on
        ASSUMPTIONS['gain_grid_points'] multipliers spanning the draws."""
        years = ASSUMPTIONS["phase_in_years"] if years is None else years
        beta = np.asarray(beta, dtype=float)
        base = self.base[sex]
        e0 = self.baseline_le(sex, a0, weights)
        points = beta.ravel()
        if interpolate:
            lo, hi = float(points.min()), float(points.max())
            n = ASSUMPTIONS["gain_grid_points"] if hi > lo else 1
            points = np.linspace(lo, hi, n)
        out = np.empty(points.shape)
        step = max(1, (1 << 22) // (base.omega - a0 + 1))  # ~4M cells per chunk
        for i in range(0, points.size, step):
            lm = self.log_mult(
                sex, a0, years, structure, points[i : i + step], attenuate
            )
            out[i : i + step] = life_expectancy(base, a0, lm, weights) - e0
        if not interpolate:
            return out.reshape(beta.shape)
        if points.size == 1:
            return np.full(beta.shape, out[0])
        return np.interp(beta, points, out)

    def variant_gain(
        self,
        sex: str,
        a0: int,
        member: str,
        delta: float,
        background: float,
        v: Variant = MAIN,
        **kw,
    ) -> np.ndarray:
        """gain() for a member under a Variant."""
        structure, beta = self.scenario(member, delta, background, v, **kw)
        return self.gain(
            sex,
            a0,
            structure,
            beta,
            years=v.phase_in_years,
            attenuate=v.attenuate_with_age,
        )

    def discount_weights(self, sex: str, a0: int) -> np.ndarray:
        """Discount factor for person-years at each age a0..omega: mid-year for
        single years; the open interval at its baseline midpoint."""
        base = self.base[sex]
        t = np.arange(base.omega - a0 + 1) + 1 / 2
        t[-1] = base.omega - a0 + base.e_open / 2
        return (1 + ASSUMPTIONS["discount_rate"]) ** -t
