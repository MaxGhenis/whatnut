"""Compute every result and figure: ``python -m whatnut.pipeline``.

Writes results/results.json (sorted keys, 6 significant figures, no timestamps)
and paper/figures/*.png (fixed size, dpi and fonts; no software or time
metadata). Two runs on the same machine produce identical bytes.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from whatnut import data
from whatnut.lifetable import baseline_ex
from whatnut.model import (
    ANALOG_PAIR_IDS,
    ASSUMPTIONS,
    CALIBRATION_ANCHORS,
    CALIBRATION_STRATA,
    EVIDENCE_IDS,
    LDL_MEMBERS,
    MAIN,
    MAIN_MEMBERS,
    MEMBER_DESCRIPTIONS,
    MEMBERS,
    PREDIMED_BASELINE_ROLES,
    RR_ROLES,
    SCENARIO_LABEL,
    STAT_NAMES,
    Model,
    Variant,
    dial_name,
    intake_pair_subsets,
    pool_stats,
    summarize,
)

ROOT = data.ROOT
RESULTS = ROOT / "results" / "results.json"
FIGURES = ROOT / "paper" / "figures"

SEXES = tuple(ASSUMPTIONS["grid"]["sex"])
REF = ASSUMPTIONS["reference"]
DAYS = ASSUMPTIONS["days_per_year"]
SIG_FIGS = 6

# The scenarios the figures draw beside the LDL-pathway range.
FIGURE_MEMBERS = ("ldl_chd", "ldl_all", "calibrated", "face_value")


def key(x: float) -> str:
    """JSON key for a number: '28', '1.93'."""
    return f"{x:g}"


def _alias(member: str) -> str:
    """The dial at c = 1 is the face-value member; compute it once."""
    for c in ASSUMPTIONS["c_dial"]:
        if member == dial_name(c) and c == 1:
            return "face_value"
    return member


class Scenarios:
    """Summaries of ΔLE per scenario, memoized on what determines the draws."""

    def __init__(self, m: Model):
        self.m = m
        self.cache: dict[tuple, dict[str, float]] = {}

    def stats(
        self,
        sex: str,
        a0: int,
        member: str,
        delta: float,
        background: float,
        v: Variant = MAIN,
    ) -> dict[str, float]:
        m = self.m
        member = _alias(member)
        if member in LDL_MEMBERS:
            # exclude_external reaches ldl_all only (ldl_chd acts on CHD deaths)
            what: tuple = (delta, v.ldl, member == "ldl_all" and v.exclude_external)
        elif member == "cvd_only":
            what = (m.cvd_curve.delta_f(background, delta),)
        else:
            what = (
                v.curve,
                v.rr_role,
                v.anchor,
                v.exclude_external,
                m.curves[v.curve].delta_f(background, delta),
            )
        k = (sex, a0, member, v.phase_in_years, v.attenuate_with_age, *what)
        if k not in self.cache:
            gain = m.variant_gain(sex, a0, member, delta, background, v)
            self.cache[k] = summarize(gain)
        return self.cache[k]


# --------------------------------------------------------------------------
# Sections of results.json
# --------------------------------------------------------------------------


def grid(sc: Scenarios) -> dict:
    g = ASSUMPTIONS["grid"]
    return {
        sex: {
            key(a0): {
                key(d): {
                    key(b): {mem: sc.stats(sex, a0, mem, d, b) for mem in MEMBERS}
                    for b in g["background"]
                }
                for d in g["delta"]
            }
            for a0 in g["a0"]
        }
        for sex in SEXES
    }


def reference(sc: Scenarios, grid_out: dict, rounded_grid: dict) -> dict:
    m = sc.m
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    scenarios = {sex: grid_out[sex][key(a0)][key(d)][key(b)] for sex in SEXES}
    # headline numbers, derived from the rounded grid exactly as results.verify does
    cell = {sex: rounded_grid[sex][key(a0)][key(d)][key(b)] for sex in SEXES}
    headline = {
        f"{sex}_{mem}_mean_days": cell[sex][mem]["mean"] * DAYS
        for sex in SEXES
        for mem in MAIN_MEMBERS
    }
    return {
        "a0": a0,
        "delta": d,
        "background": b,
        "table_deltas": ASSUMPTIONS["reference_table_deltas"],
        "scenarios": scenarios,
        "headline_days": headline,
        "baseline_le": {sex: m.baseline_le(sex, a0) for sex in SEXES},
    }


def marginal(grid_out: dict) -> dict:
    a0, step = REF["a0"], ASSUMPTIONS["marginal_step_g"]
    return {
        "a0": a0,
        "step_g": step,
        "by_background": {
            sex: {
                key(b): grid_out[sex][key(a0)][key(step)][key(b)]
                for b in ASSUMPTIONS["grid"]["background"]
            }
            for sex in SEXES
        },
    }


def calibration(m: Model) -> dict:
    """Each stratum's ratio, and the share of the association it keeps (c) under
    both anchors: Aune's linear per-28 g estimate and the main curve's own value
    at 28 g; the linear-anchor share against each per-28 g estimate a
    sensitivity rescales the curve to; and pools of subsets of the 23
    intake-v-intake pairs."""
    rr28 = m.rows["rr28_all"]
    serving = rr28.per_grams()
    rr_curve = math.exp(float(m.curves["main"].f(serving)))
    anchors = {"linear": rr28.estimate, "curve": rr_curve}
    out: dict = {
        "rr28_row": rr28.id,
        "serving_g": serving,
        "anchor_rr": anchors,
        "rr_roles": {
            role: {"row": m.rows[role].id, "rr28": m.rows[role].estimate}
            for role in RR_ROLES
        },
        "formula": "c = ln(RR_anchor * RRR) / ln(RR_anchor), per draw",
        "strata": {},
    }
    for member, role in CALIBRATION_STRATA.items():
        r = m.rows[role]
        entry = {
            "row": r.id,
            "rrr": r.estimate,
            "rrr_ci": [r.ci_low, r.ci_high],
            "rrr_ci_level": r.ci_level,
            "rrr_pi": [r.pi_low, r.pi_high],
        }
        if role == "rrr_analog":
            pool = pool_stats([data.row(rid) for rid in ANALOG_PAIR_IDS], r.id)
            entry["pair_rows"] = list(ANALOG_PAIR_IDS)
            entry["tau2"] = pool.tau2
            entry["q"] = pool.q
        for anchor in CALIBRATION_ANCHORS:
            a = anchors[anchor]
            c = m.c(member, anchor)
            entry[anchor] = {
                "c_point": math.log(a * r.estimate) / math.log(a),
                "c_draws": summarize(c),
                "share_draws_c_above_1": float(np.mean(c > 1)),
                "share_draws_c_below_0": float(np.mean(c < 0)),
            }
        entry["linear"]["c_point_by_rr_role"] = {
            rr_role: math.log(m.rows[rr_role].estimate * r.estimate)
            / math.log(m.rows[rr_role].estimate)
            for rr_role in RR_ROLES
        }
        out["strata"][member] = entry
    subsets = intake_pair_subsets()
    out["intake_subsets"] = {
        name: {
            **pool_stats(rows, f"intake_{name}").summary(),
            "pairs": [int(r.id.rsplit("_", 1)[1]) for r in rows],
        }
        for name, rows in subsets.items()
    }
    out["intake_subsets_note"] = (
        "Pools of Schwingshackl 2021's 23 intake-v-intake pairs "
        "(data/calibration/schwingshackl2021_intake_pairs.csv; 'pairs' are its line "
        "numbers): all; core, without pregnancy or colorectal outcomes; protective, "
        "cohort RR below 1"
    )
    return out


# Sensitivity rows: (id, variant, {column: scenario}). Columns are the scenarios
# a choice can move; a row leaves out the columns it does not change.
SENSITIVITY_ROWS = (
    (
        "main",
        MAIN,
        {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
    ),
    (
        "curve_as_printed",
        Variant(curve="pchip_as_printed"),
        {"face_value": "face_value", "calibrated": "calibrated"},
    ),
    (
        "curve_linear_plateau",
        Variant(curve="linear_plateau"),
        {"face_value": "face_value", "calibrated": "calibrated"},
    ),
    (
        "curve_from_any",
        Variant(curve="from_any"),
        {"face_value": "face_value", "calibrated": "calibrated"},
    ),
    (
        "rr_fu10",
        Variant(rr_role="rr28_fu10"),
        {"face_value": "face_value", "calibrated": "calibrated"},
    ),
    (
        "rr_large",
        Variant(rr_role="rr28_large"),
        {"face_value": "face_value", "calibrated": "calibrated"},
    ),
    (
        "exclude_external",
        Variant(exclude_external=True),
        {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
    ),
    (
        "attenuate_with_age",
        Variant(attenuate_with_age=True),
        {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
    ),
    (
        "phase_in_0",
        Variant(phase_in_years=0),
        {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
    ),
    (
        "phase_in_20",
        Variant(phase_in_years=20),
        {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
    ),
    ("ldl_all_trials", Variant(ldl="tree_all_trials"), {"ldl_all": "ldl_all"}),
)
BASELINE_2021_ROW = (
    "baseline_2021",
    MAIN,
    {"face_value": "face_value", "calibrated": "calibrated", "ldl_all": "ldl_all"},
)


def sensitivity(sc: Scenarios, sc2021: Scenarios | None) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    rows: dict = {}
    todo = [(sc, *row) for row in SENSITIVITY_ROWS]
    if sc2021 is not None:
        todo.append((sc2021, *BASELINE_2021_ROW))
    for s, rid, v, cols in todo:
        rows[rid] = {
            "columns": cols,
            "stats": {
                sex: {col: s.stats(sex, a0, mem, d, b, v) for col, mem in cols.items()}
                for sex in SEXES
            },
        }
    calibrations = {
        member: {
            anchor: {
                sex: sc.stats(sex, a0, member, d, b, Variant(anchor=anchor))
                for sex in SEXES
            }
            for anchor in CALIBRATION_ANCHORS
        }
        for member in CALIBRATION_STRATA
    }
    serving = ASSUMPTIONS["reference_table_deltas"][-1]
    at_serving = {
        name: {
            sex: {
                mem: sc.stats(sex, a0, mem, serving, b, Variant(curve=name))
                for mem in ("face_value", "calibrated")
            }
            for sex in SEXES
        }
        for name in sc.m.curves
    }
    out = {
        "a0": a0,
        "delta": d,
        "background": b,
        "rows": rows,
        "calibrations": calibrations,
        "curves_at_serving": {"delta": serving, "curves": at_serving},
    }
    if sc2021 is not None:
        out["baseline_2021"] = {
            "life_tables": data.life_table_source("2021"),
            "cause_shares_year": sc2021.m.shares[SEXES[0]].year,
        }
    return out


def curves(m: Model) -> dict:
    grams = list(range(ASSUMPTIONS["figure_dose_max_g"] + 1))
    out = {
        name: {
            "kind": curve.kind,
            "start_g": curve.start_g,
            "rr_by_gram": {key(g): math.exp(float(curve.f(g))) for g in grams},
        }
        for name, curve in m.curves.items()
    }
    out["cvd_main"] = {
        "kind": m.cvd_curve.kind,
        "start_g": m.cvd_curve.start_g,
        "rr_by_gram": {key(g): math.exp(float(m.cvd_curve.f(g))) for g in grams},
    }
    return out


def ala_counted(background: float, nut_ala: float) -> float:
    """Grams of a nut's ALA inside the observed range [max(bg, lo), hi]."""
    lo, hi = ASSUMPTIONS["ala_support_g"]
    return max(0, min(background + nut_ala, hi) - max(background, lo))


ALA_MEMBERS = ("face_value", "calibrated")
ALA_SLOPES = ("ala", "ala_fixed")


def ala(m: Model) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    comp = data.composition()
    basis = data.composition_basis_g()
    backgrounds = {
        "average": {sex: m.rows[f"ala_background_{sex}"].estimate for sex in SEXES},
        "high": {sex: ASSUMPTIONS["ala_background_high_g"] for sex in SEXES},
    }
    out: dict = {
        "slope_rows": {s: m.rows[s].id for s in ALA_SLOPES},
        "support_g": ASSUMPTIONS["ala_support_g"],
        "background_g": backgrounds,
        "background_rows": {sex: m.rows[f"ala_background_{sex}"].id for sex in SEXES},
        "by_background": {},
    }
    base = {
        (sex, mem): m.variant_gain(sex, a0, mem, d, b)
        for sex in SEXES
        for mem in ALA_MEMBERS
    }
    for bg_name, bgs in backgrounds.items():
        per_nut = {}
        for nut in ASSUMPTIONS["nuts"]:
            nut_ala = d * comp[nut]["ala_g"] / basis
            entry: dict = {"ala_basis": comp[nut]["ala_basis"], "nut_ala_g": nut_ala}
            for sex in SEXES:
                counted = ala_counted(bgs[sex], nut_ala)
                entry[sex] = {"counted_ala_g": counted}
                for mem in ALA_MEMBERS:
                    for slope in ALA_SLOPES:
                        gain = m.variant_gain(
                            sex, a0, mem, d, b, ala_g=counted, ala_role=slope
                        )
                        entry[sex][f"{mem}:{slope}"] = {
                            "total": summarize(gain),
                            "increment": summarize(gain - base[(sex, mem)]),
                        }
            per_nut[nut] = entry
        out["by_background"][bg_name] = per_nut
    return out


COST_MEMBERS = (
    "calibrated",
    "calibrated_mortality",
    "face_value",
    "ldl_all",
    "ldl_chd",
)


def cost(m: Model) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    prices = data.prices_by_nut()
    dates = data.price_dates()
    tree_excluded = set(ASSUMPTIONS["tree_nuts_exclude"])
    kg_per_year = d / ASSUMPTIONS["g_per_kg"] * DAYS
    # per sex and member: (discounted LY gained, discounted person-years treated,
    # undiscounted LY gained, undiscounted person-years treated), per nut group
    memo: dict[tuple, tuple[float, float, float, float]] = {}

    def outcomes(sex: str, mem: str, group: str) -> tuple[float, float, float, float]:
        k = (sex, mem, group if mem in LDL_MEMBERS else "class")
        if k not in memo:
            structure, beta = m.scenario(mem, d, b, Variant(ldl=group))
            w = m.discount_weights(sex, a0)
            ly_disc = m.gain(sex, a0, structure, beta, weights=w)
            ly = m.gain(sex, a0, structure, beta)
            memo[k] = (
                float(np.mean(ly_disc)),
                m.baseline_le(sex, a0, w) + float(np.mean(ly_disc)),
                float(np.mean(ly)),
                m.baseline_le(sex, a0) + float(np.mean(ly)),
            )
        return memo[k]

    by_nut = {}
    for nut in ASSUMPTIONS["nuts"]:
        p = prices[nut]
        usd_year = p["median_usd_per_kg"] * kg_per_year
        group = "peanut" if nut in tree_excluded else "tree"
        entry: dict = {
            "usd_per_kg": p["median_usd_per_kg"],
            "usd_per_kg_min": p["min_usd_per_kg"],
            "usd_per_kg_max": p["max_usd_per_kg"],
            "n_retailers": p["n_retailers"],
            "retailers": p["retailers"],
            "price_dates": list(dates[nut]),
            "usd_per_year": usd_year,
            "ldl_source": EVIDENCE_IDS[
                "ldl_peanut" if group == "peanut" else "ldl_tree"
            ],
        }
        for sex in SEXES:
            entry[sex] = {}
            for mem in COST_MEMBERS:
                ly_disc, py_disc, ly, py = outcomes(sex, mem, group)
                entry[sex][mem] = {
                    "discounted_life_years": ly_disc,
                    "discounted_cost_usd": usd_year * py_disc,
                    "usd_per_life_year": (usd_year * py_disc / ly_disc)
                    if ly_disc > 0
                    else None,
                    "life_years": ly,
                    "usd_per_life_year_undiscounted": (usd_year * py / ly)
                    if ly > 0
                    else None,
                }
        by_nut[nut] = entry
    return {
        "a0": a0,
        "delta": d,
        "background": b,
        "discount_rate": ASSUMPTIONS["discount_rate"],
        "price": (
            "median of the primary retail rows per nut (data/prices/prices_by_nut.csv)"
        ),
        "ratio": "mean discounted cost / mean discounted life-years gained",
        "by_nut": by_nut,
    }


def mean_phase_in_share(follow_up: float, phase: float) -> float:
    """Mean of the linear phase-in min(t / T, 1) over t in [0, T_f]: T_f / 2T if
    T_f <= T, else 1 - T / 2T_f (1 with no phase-in)."""
    if phase <= 0:
        return 1
    if follow_up <= phase:
        return follow_up / (2 * phase)
    return 1 - phase / (2 * follow_up)


def predimed_check(m: Model) -> dict:
    """PREDIMED's contrast on the main curve at face value (c = 1): each baseline
    intake group b gets log HR f(b + nut-arm change) - f(max(0, b + control-arm
    change)); the full-effect HR is exp of their size-weighted mean, and the
    phased HR scales it by the mean phase-in share over the trial's median
    follow-up (mean_phase_in_share)."""
    f = m.curves["main"].f
    groups = [m.rows[role] for role in PREDIMED_BASELINE_ROLES]
    nut, ctl = m.rows["predimed_change_nuts"], m.rows["predimed_change_control"]
    trial = m.rows["predimed_death"]
    fu = re.search(r"median follow-up ([\d.]+) years", trial.population or "")
    if not fu:
        raise data.DataIntegrityError(f"{trial.id}: no median follow-up in population")
    follow_up = float(fu.group(1))
    phase = ASSUMPTIONS["phase_in_years"]
    share = mean_phase_in_share(follow_up, phase)
    sizes = [g.count() for g in groups]
    total = sum(sizes)
    log_hr = [
        float(f(g.estimate + nut.estimate) - f(max(0, g.estimate + ctl.estimate)))
        for g in groups
    ]
    mean_log_hr = sum(n * x for n, x in zip(sizes, log_hr)) / total
    return {
        "groups": [
            {"row": g.id, "baseline_g": g.estimate, "n": n, "log_hr": x}
            for g, n, x in zip(groups, sizes, log_hr)
        ],
        "n": total,
        "eaters_share": sum(n for g, n in zip(groups, sizes) if g.estimate > 0) / total,
        "mean_baseline_g": sum(n * g.estimate for g, n in zip(groups, sizes)) / total,
        "change_rows": {"nuts": nut.id, "control": ctl.id},
        "change_g": {"nuts": nut.estimate, "control": ctl.estimate},
        "curve": "main",
        "c": 1,
        "full_hr": math.exp(mean_log_hr),
        "follow_up_years": follow_up,
        "phase_in_years": phase,
        "mean_phase_in_share": share,
        "phased_hr": math.exp(mean_log_hr * share),
        "trial_row": trial.id,
        "trial_hr": trial.estimate,
        "trial_ci": [trial.ci_low, trial.ci_high],
    }


def fadnes(m: Model, m2021: Model | None) -> dict:
    t = data.fadnes_targets()
    hr = t["relative_risk"]["hr_at_optimal_25g"]
    lo = t["main_target"]["intake_change_g_per_day"]["from"]
    hi = t["main_target"]["intake_change_g_per_day"]["to"]
    years = t["phase_in"]["years_to_full_effect"]
    change = f"{lo:g}->{hi:g}"
    aune_g, aune_rr = data.aune_curve("all_cause_mortality")
    rows = []
    for tr in t["all_nut_gains_table"]:
        if not str(tr["change"]).startswith(change):
            continue
        sex, a0 = tr["sex"], int(tr["start_age"])
        beta = np.array([math.log(hr)])
        ours = float(m.gain(sex, a0, "all", beta, years)[0])
        theirs, ui, source = tr["years"], [tr["ui95_low"], tr["ui95_high"]], "yaml"
        target = m.rows[f"fadnes_{sex}"]
        if a0 == min(int(x["start_age"]) for x in t["all_nut_gains_table"]):
            # the headline targets are evidence rows
            theirs, ui, source = (
                target.estimate,
                [target.ci_low, target.ci_high],
                target.id,
            )
        row = {
            "sex": sex,
            "start_age": a0,
            "theirs": theirs,
            "theirs_ui95": ui,
            "target_source": source,
            "ours": ours,
            "rel_diff": ours / theirs - 1,
            "locator": tr["locator"],
        }
        if m2021 is not None:
            row["ours_2021_baseline"] = float(
                m2021.gain(sex, a0, "all", beta, years)[0]
            )
        rows.append(row)
    rows.sort(key=lambda r: (r["start_age"], r["sex"]))
    main_age = min(r["start_age"] for r in rows)
    return {
        "inputs": {
            "hr": hr,
            "hr_source": (
                "data/curves/fadnes2022_targets.yaml relative_risk.hr_at_optimal_25g"
            ),
            "aune_s15_rr_at_dose": dict(zip(map(key, aune_g), aune_rr))[key(hi)],
            "dose_from_g": lo,
            "dose_to_g": hi,
            "phase_in_years": years,
            "phase_in_shape": "linear in log hazard ratio",
            "baseline_theirs": t["mortality_data"]["source"],
            "baseline_ours": data.life_table_source(),
        },
        "their_baseline_le": t["mortality_data"]["typical_diet_LE_us"],
        "main_start_age": main_age,
        "rows": rows,
    }


def baseline_le(m: Model) -> dict:
    """The engine's baseline life expectancy against the published table: every
    age's largest gap, and the table at the decades and the grid's ages."""
    omega = m.base[SEXES[0]].omega
    shown = sorted({*ASSUMPTIONS["grid"]["a0"], *range(0, omega + 1, 10)})
    out: dict = {"max_gap_days": {}}
    for sex in SEXES:
        ours = baseline_ex(m.base[sex])
        gap = np.abs(np.asarray(ours) - m.base[sex].ex_published)
        out["max_gap_days"][sex] = float(np.max(gap)) * DAYS
        out[sex] = {
            key(a): {
                "model": float(ours[a]),
                "published": float(m.base[sex].ex_published[a]),
            }
            for a in shown
        }
    return out


def figure_data(sc: Scenarios) -> dict:
    a0, d = REF["a0"], REF["delta"]
    step = ASSUMPTIONS["marginal_step_g"]
    grams = range(ASSUMPTIONS["figure_dose_max_g"] + 1)
    lo_age, hi_age = ASSUMPTIONS["figure_age_range"]
    ages = range(lo_age, hi_age + 1)
    bgs = range(ASSUMPTIONS["figure_background_max_g"] + 1)

    def series(xs, fn: Callable[[float], dict]) -> dict[str, list[float]]:
        cols = [fn(x) for x in xs]
        return {s: [c[s] for c in cols] for s in STAT_NAMES}

    def panels(xs, fn: Callable[[str, str, float], dict]) -> dict:
        return {
            sex: {
                mem: series(xs, lambda x, sex=sex, mem=mem: fn(sex, mem, x))
                for mem in FIGURE_MEMBERS
            }
            for sex in SEXES
        }

    m = sc.m
    max_g = ASSUMPTIONS["figure_dose_max_g"]
    return {
        "dose_curves": {
            "grams": list(grams),
            "curves": {
                name: [math.exp(float(curve.f(g))) for g in grams]
                for name, curve in m.curves.items()
            },
            "aune_points": data.aune_points("all_cause_mortality"),
            "bop": [p for p in data.bop_curve() if p["g"] <= max_g],
        },
        "days_by_dose": {
            "a0": a0,
            "grams": list(grams),
            **panels(grams, lambda sex, mem, g: sc.stats(sex, a0, mem, g, 0)),
        },
        "days_by_age": {
            "delta": d,
            "ages": list(ages),
            **panels(ages, lambda sex, mem, a: sc.stats(sex, a, mem, d, 0)),
        },
        "marginal_by_background": {
            "a0": a0,
            "step_g": step,
            "backgrounds": list(bgs),
            **panels(bgs, lambda sex, mem, bg: sc.stats(sex, a0, mem, step, bg)),
        },
    }


# --------------------------------------------------------------------------
# Serialization
# --------------------------------------------------------------------------


def rounded(obj):
    """Round every float to SIG_FIGS significant figures; tuples become lists."""
    if isinstance(obj, dict):
        return {str(k): rounded(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [rounded(v) for v in obj]
    if isinstance(obj, (bool, str)) or obj is None:
        return obj
    if isinstance(obj, (int, np.integer)):
        return int(obj)
    x = float(obj)
    if not math.isfinite(x):
        return None
    x = float(f"{x:.{SIG_FIGS}g}")
    return x + 0  # -0.0 -> 0.0


def dumps(obj) -> str:
    return json.dumps(rounded(obj), sort_keys=True, indent=1, ensure_ascii=False) + "\n"


def meta(m: Model) -> dict:
    rows = {}
    for rid in sorted(data.ROWS_USED):
        r = data.evidence()[rid]
        rows[rid] = {
            "estimate": r.estimate,
            "ci_low": r.ci_low,
            "ci_high": r.ci_high,
            "ci_level": r.ci_level,
            "pi_low": r.pi_low,
            "pi_high": r.pi_high,
            "unit": r.unit,
        }
    return {
        "n": m.n,
        "seed": m.seed,
        "days_per_year": DAYS,
        "phase_in_years": ASSUMPTIONS["phase_in_years"],
        "discount_rate": ASSUMPTIONS["discount_rate"],
        "assumptions": ASSUMPTIONS,
        "evidence_rows": rows,
        "data_files": dict(sorted(data.READS.items())),
        "baseline": {
            "life_tables": data.life_table_source(),
            "cause_shares_year": m.shares[SEXES[0]].year,
        },
        "members": MEMBER_DESCRIPTIONS,
        "main_members": list(MAIN_MEMBERS),
        "scenario_labels": SCENARIO_LABEL,
        "grid_axes": {
            **ASSUMPTIONS["grid"],
            "member": list(MEMBERS),
            "stat": list(STAT_NAMES),
        },
        "units": (
            "Life-expectancy changes are in years (multiply by days_per_year for days)."
        ),
        "generator": "python -m whatnut.pipeline",
    }


def compute(n: int | None = None, seed: int | None = None) -> dict:
    """Every result, as a plain dict (unrounded)."""
    data.READS.clear()
    data.ROWS_USED.clear()
    m = Model(
        n=ASSUMPTIONS["mc_n"] if n is None else n,
        seed=ASSUMPTIONS["mc_seed"] if seed is None else seed,
    )
    sc = Scenarios(m)
    try:
        m2021: Model | None = Model(n=m.n, seed=m.seed, vintage="2021")
    except FileNotFoundError:
        m2021 = None  # no archived 2021 baseline on disk
    out: dict = {}
    out["grid"] = grid(sc)
    out["reference"] = reference(sc, out["grid"], rounded(out["grid"]))
    out["marginal_10g"] = marginal(out["grid"])
    out["calibration"] = calibration(m)
    out["c_dial"] = {dial_name(c): c for c in ASSUMPTIONS["c_dial"]}
    out["sensitivity"] = sensitivity(sc, None if m2021 is None else Scenarios(m2021))
    out["curves"] = curves(m)
    out["ala"] = ala(m)
    out["cost"] = cost(m)
    out["predimed_check"] = predimed_check(m)
    out["fadnes"] = fadnes(m, m2021)
    out["baseline_le"] = baseline_le(m)
    out["figures"] = figure_data(sc)
    out["meta"] = meta(m)
    return out


def run(
    results_path: Path = RESULTS,
    figures_dir: Path = FIGURES,
    n: int | None = None,
    seed: int | None = None,
) -> dict:
    """Compute, write results.json and the figures; return the rounded results."""
    text = dumps(compute(n, seed))
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(text, encoding="utf-8")
    res = json.loads(text)
    write_figures(res, figures_dir)
    return res


# --------------------------------------------------------------------------
# Figures
# --------------------------------------------------------------------------

# Cosmetic constants only (tests/test_no_literals.py allows floats here and in
# model.ASSUMPTIONS). Colors: the dataviz reference palette's first three
# categorical slots, validated all-pairs on white (CVD ΔE >= 9.2).
STYLE = {
    "dpi": 200,
    "width_in": 6.5,
    "height_in": 3.4,
    "tall_height_in": 3.9,
    "font": "DejaVu Sans",
    "font_size": 8.5,
    "surface": "#ffffff",
    "ink": "#0b0b0b",
    "ink_secondary": "#52514e",
    "ink_muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
    "blue": "#2a78d6",
    "orange": "#eb6834",
    "aqua": "#1baf7a",
    "line_width": 1.6,
    "hairline": 0.6,
    "band_alpha": 0.14,
    "ldl_alpha": 0.45,
    "marker_size": 5.5,
    "interval_80_width": 3.2,
    "interval_95_width": 1.0,
    "row_offset": 0.17,
    "errorbar_width": 1.2,
    "rr_axis_top": 1.02,
}

SEX_COLOR = {"female": "blue", "male": "orange"}
SEX_LABEL = {"female": "Women", "male": "Men"}

FIGURE_FILES = (
    "dose_curves.png",
    "days_by_dose.png",
    "days_by_age.png",
    "marginal_by_background.png",
    "scenarios_reference.png",
    "cost_per_life_year.png",
)


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    s = STYLE
    plt.rcParams.update(
        {
            "font.family": s["font"],
            "font.size": s["font_size"],
            "text.color": s["ink"],
            "axes.labelcolor": s["ink_secondary"],
            "axes.edgecolor": s["axis"],
            "axes.linewidth": s["hairline"],
            "axes.facecolor": s["surface"],
            "figure.facecolor": s["surface"],
            "savefig.facecolor": s["surface"],
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "axes.axisbelow": True,
            "grid.color": s["grid"],
            "grid.linewidth": s["hairline"],
            "grid.linestyle": "-",
            "xtick.color": s["ink_muted"],
            "ytick.color": s["ink_muted"],
            "xtick.labelcolor": s["ink_secondary"],
            "ytick.labelcolor": s["ink_secondary"],
            "xtick.major.width": s["hairline"],
            "ytick.major.width": s["hairline"],
            "legend.frameon": False,
            "lines.solid_capstyle": "round",
            "lines.solid_joinstyle": "round",
            "svg.hashsalt": "whatnut",
            "path.simplify": False,
        }
    )
    return plt


def _days(xs) -> np.ndarray:
    return np.asarray(xs, dtype=float) * DAYS


def _thousands(ax, axis: str = "y") -> None:
    from matplotlib.ticker import FuncFormatter

    fmt = FuncFormatter(lambda v, _: f"{v:,.0f}".replace("-", "\N{MINUS SIGN}"))
    (ax.yaxis if axis == "y" else ax.xaxis).set_major_formatter(fmt)


def _save(fig, path: Path) -> None:
    fig.savefig(path, dpi=STYLE["dpi"], metadata={"Software": None})


def fig_dose_curves(res: dict, path: Path, plt) -> None:
    s, fd = STYLE, res["figures"]["dose_curves"]
    g = fd["grams"]
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["height_in"]), layout="constrained"
    )
    bop = fd["bop"]
    ax.fill_between(
        [p["g"] for p in bop],
        [p["lo"] for p in bop],
        [p["hi"] for p in bop],
        color=s["aqua"],
        alpha=s["band_alpha"],
        linewidth=0,
    )
    ax.plot(
        [p["g"] for p in bop],
        [p["rr"] for p in bop],
        color=s["aqua"],
        lw=s["line_width"],
        label="IHME: nuts and seeds, ischemic heart disease",
    )
    ax.plot(
        g,
        fd["curves"]["linear_plateau"],
        color=s["ink_muted"],
        lw=s["line_width"],
        linestyle=(0, (4, 3)),
        label="Smooth curve through per-28 g estimate",
    )
    ax.plot(
        g,
        fd["curves"]["main"],
        color=s["blue"],
        lw=s["line_width"],
        label="Model's curve (Aune, held at its minimum)",
    )
    pts = [p for p in fd["aune_points"] if p["lo"] is not None]
    ax.errorbar(
        [p["g"] for p in pts],
        [p["rr"] for p in pts],
        yerr=[
            [p["rr"] - p["lo"] for p in pts],
            [p["hi"] - p["rr"] for p in pts],
        ],
        fmt="o",
        color=s["orange"],
        markersize=s["marker_size"],
        elinewidth=s["errorbar_width"],
        capsize=0,
        label="Aune 2016 points, 95% CI",
    )
    ax.axhline(1, color=s["axis"], lw=s["hairline"])
    ax.set_xlim(g[0], g[-1])
    ax.set_ylim(top=s["rr_axis_top"])
    ax.set_xlabel("Nuts eaten (g/day)")
    ax.set_ylabel("Relative risk vs no nuts")
    fig.legend(loc="outside lower center", ncols=2)
    _save(fig, path)
    plt.close(fig)


def _scenario_panels(fd: dict, xs: list, xlabel: str, path: Path, plt) -> None:
    """Women and men side by side: the LDL-pathway range (coronary to all
    deaths, means), the main calibration's 80% interval and mean, and face value
    in ink (orange and blue mean the sexes in the other figures)."""
    s = STYLE
    fig, axes = plt.subplots(
        1, 2, figsize=(s["width_in"], s["height_in"]), sharey=True, layout="constrained"
    )
    for ax, sex in zip(axes, SEXES):
        d = fd[sex]
        ax.fill_between(
            xs,
            _days(d["ldl_chd"]["mean"]),
            _days(d["ldl_all"]["mean"]),
            color=s["aqua"],
            alpha=s["ldl_alpha"],
            linewidth=0,
            label=f"{SCENARIO_LABEL['ldl_chd'].split(',')[0]} (coronary to all deaths)",
        )
        ax.fill_between(
            xs,
            _days(d["calibrated"]["p10"]),
            _days(d["calibrated"]["p90"]),
            color=s["blue"],
            alpha=s["band_alpha"],
            linewidth=0,
            label=f"{SCENARIO_LABEL['calibrated']}, 80% interval",
        )
        ax.plot(
            xs,
            _days(d["calibrated"]["mean"]),
            color=s["blue"],
            lw=s["line_width"],
            label=SCENARIO_LABEL["calibrated"],
        )
        ax.plot(
            xs,
            _days(d["face_value"]["mean"]),
            color=s["ink"],
            lw=s["line_width"],
            label=SCENARIO_LABEL["face_value"],
        )
        ax.set_title(
            SEX_LABEL[sex], loc="left", color=s["ink"], fontsize=s["font_size"]
        )
        ax.set_xlim(xs[0], xs[-1])
        ax.set_xlabel(xlabel)
        _thousands(ax)
    for ax in axes:
        ax.axhline(0, color=s["axis"], lw=s["hairline"])
    axes[0].set_ylabel("Life expectancy gained (days)")
    handles, labels = axes[0].get_legend_handles_labels()
    order = [3, 2, 1, 0]
    fig.legend(
        [handles[i] for i in order],
        [labels[i] for i in order],
        loc="outside lower center",
        ncols=2,
    )
    _save(fig, path)
    plt.close(fig)


def fig_days_by_dose(res: dict, path: Path, plt) -> None:
    fd = res["figures"]["days_by_dose"]
    _scenario_panels(fd, fd["grams"], "Nuts added (g/day)", path, plt)


def fig_days_by_age(res: dict, path: Path, plt) -> None:
    fd = res["figures"]["days_by_age"]
    _scenario_panels(fd, fd["ages"], "Age when nuts start (years)", path, plt)


def fig_marginal(res: dict, path: Path, plt) -> None:
    """The step (fd['step_g'] grams) is in the caption; the panel label names only
    the axis, so the two panels' labels fit side by side."""
    fd = res["figures"]["marginal_by_background"]
    _scenario_panels(fd, fd["backgrounds"], "Grams already eaten a day", path, plt)


def fig_scenarios(res: dict, path: Path, plt) -> None:
    from matplotlib.lines import Line2D

    s = STYLE
    ref = res["reference"]
    rows = list(reversed(res["meta"]["main_members"]))  # face value on top
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["tall_height_in"]), layout="constrained"
    )
    n = len(rows)
    for i, mem in enumerate(rows):
        y0 = n - 1 - i
        for sex, sign in zip(SEXES, (1, -1)):
            st, color = ref["scenarios"][sex][mem], s[SEX_COLOR[sex]]
            y = y0 + sign * s["row_offset"]
            ax.plot(
                _days([st["p2_5"], st["p97_5"]]),
                [y, y],
                color=color,
                lw=s["interval_95_width"],
            )
            ax.plot(
                _days([st["p10"], st["p90"]]),
                [y, y],
                color=color,
                lw=s["interval_80_width"],
            )
            ax.plot(
                _days([st["mean"]]),
                [y],
                "o",
                color=color,
                markersize=s["marker_size"],
                markeredgecolor=s["surface"],
                markeredgewidth=s["hairline"] * 2,
            )
    ax.set_yticks(range(n))
    ax.set_yticklabels([SCENARIO_LABEL[mem] for mem in reversed(rows)])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.axvline(0, color=s["axis"], lw=s["hairline"])
    ax.set_xlabel(
        f"Life expectancy gained (days), age {ref['a0']}, "
        f"{ref['background']} to {ref['delta']} g/day"
    )
    _thousands(ax, "x")
    handles = [
        Line2D(
            [],
            [],
            color=s[SEX_COLOR[sex]],
            marker="o",
            lw=s["interval_80_width"],
            markersize=s["marker_size"],
            markeredgecolor=s["surface"],
        )
        for sex in SEXES
    ] + [
        Line2D([], [], color=s["ink_muted"], lw=s["interval_80_width"]),
        Line2D([], [], color=s["ink_muted"], lw=s["interval_95_width"]),
    ]
    labels = [SEX_LABEL[sex] for sex in SEXES] + ["80% interval", "95% interval"]
    fig.legend(handles, labels, loc="outside lower center", ncols=4)
    _save(fig, path)
    plt.close(fig)


NUT_LABEL = {
    "walnut": "Walnut",
    "almond": "Almond",
    "pistachio": "Pistachio",
    "pecan": "Pecan",
    "hazelnut": "Hazelnut",
    "macadamia": "Macadamia",
    "cashew": "Cashew",
    "peanut": "Peanut",
}

# filled markers: the main calibration; hollow: face value
COST_MARKERS = (("calibrated", True), ("face_value", False))


def fig_cost(res: dict, path: Path, plt) -> None:
    from matplotlib.lines import Line2D

    s, c = STYLE, res["cost"]
    nuts = sorted(c["by_nut"], key=lambda k: c["by_nut"][k]["usd_per_year"])
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["tall_height_in"]), layout="constrained"
    )
    n = len(nuts)
    for i, nut in enumerate(nuts):
        y0 = n - 1 - i
        for sex, sign in zip(SEXES, (1, -1)):
            color = s[SEX_COLOR[sex]]
            for member, filled in COST_MARKERS:
                v = c["by_nut"][nut][sex][member]["usd_per_life_year"]
                ax.plot(
                    [v],
                    [y0 + sign * s["row_offset"]],
                    "o",
                    color=color,
                    markerfacecolor=color if filled else s["surface"],
                    markersize=s["marker_size"],
                    markeredgewidth=s["hairline"] * 2,
                )
    ax.set_yticks(range(n))
    ax.set_yticklabels(
        [
            f"{NUT_LABEL[nut]}, ${c['by_nut'][nut]['usd_per_year']:,.0f}/yr"
            for nut in reversed(nuts)
        ]
    )
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.set_xlim(left=0)
    ax.set_xlabel(
        f"Cost per life-year gained (US$, {c['discount_rate']:.0%} discounting), "
        f"{c['delta']} g/day from age {c['a0']}"
    )
    _thousands(ax, "x")
    handles = [
        Line2D(
            [],
            [],
            color=s[SEX_COLOR[sex]],
            marker="o",
            lw=0,
            markersize=s["marker_size"],
        )
        for sex in SEXES
    ] + [
        Line2D(
            [],
            [],
            color=s["ink_secondary"],
            marker="o",
            lw=0,
            markersize=s["marker_size"],
            markerfacecolor=s["ink_secondary"] if filled else s["surface"],
        )
        for _, filled in COST_MARKERS
    ]
    labels = [SEX_LABEL[x] for x in SEXES] + [
        SCENARIO_LABEL[mem] for mem, _ in COST_MARKERS
    ]
    fig.legend(handles, labels, loc="outside lower center", ncols=4)
    _save(fig, path)
    plt.close(fig)


def write_figures(res: dict, figures_dir: Path = FIGURES) -> list[Path]:
    plt = _plt()
    figures_dir.mkdir(parents=True, exist_ok=True)
    makers = (
        fig_dose_curves,
        fig_days_by_dose,
        fig_days_by_age,
        fig_marginal,
        fig_scenarios,
        fig_cost,
    )
    paths = []
    for name, maker in zip(FIGURE_FILES, makers):
        p = figures_dir / name
        maker(res, p, plt)
        paths.append(p)
    return paths


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, default=RESULTS)
    ap.add_argument("--figures", type=Path, default=FIGURES)
    ap.add_argument(
        "-n", type=int, default=None, help="Monte Carlo draws (default: ASSUMPTIONS)"
    )
    args = ap.parse_args(argv)
    t0 = time.perf_counter()
    res = run(args.results, args.figures, n=args.n)
    ref = res["reference"]["scenarios"]
    for sex in SEXES:
        row = ", ".join(
            f"{mem} {ref[sex][mem]['mean'] * DAYS:,.0f}" for mem in MAIN_MEMBERS
        )
        print(f"{sex}: days gained, age {REF['a0']}, 0 -> {REF['delta']} g/day: {row}")
    print(
        f"wrote {args.results} and {len(FIGURE_FILES)} figures in "
        f"{time.perf_counter() - t0:.1f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
