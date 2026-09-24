"""Compute every result and figure: ``python -m whatnut.pipeline``.

Writes results/results.json (sorted keys, 6 significant figures, no timestamps)
and paper/figures/*.png (fixed size, dpi and fonts; no software or time
metadata). Two runs on the same machine produce identical bytes.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np

from whatnut import data
from whatnut.lifetable import baseline_ex
from whatnut.model import (
    ASSUMPTIONS,
    CALIBRATION_STRATA,
    EVIDENCE_IDS,
    MEMBER_DESCRIPTIONS,
    MEMBERS,
    STAT_NAMES,
    Model,
    dial_name,
    summarize,
)

ROOT = data.ROOT
RESULTS = ROOT / "results" / "results.json"
FIGURES = ROOT / "paper" / "figures"

SEXES = tuple(ASSUMPTIONS["grid"]["sex"])
REF = ASSUMPTIONS["reference"]
DAYS = ASSUMPTIONS["days_per_year"]
SIG_FIGS = 6


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
        years: int | None = None,
        curve: str = "main",
    ) -> dict[str, float]:
        m = self.m
        member = _alias(member)
        if member in ("floor_low", "floor_high"):
            what: tuple = (delta,)
        elif member == "cvd_only":
            what = (m.cvd_curve.delta_f(background, delta),)
        else:
            what = (curve, m.curves[curve].delta_f(background, delta))
        k = (sex, a0, member, years, *what)
        if k not in self.cache:
            structure, beta = m.scenario(member, delta, background, curve)
            self.cache[k] = summarize(m.gain(sex, a0, structure, beta, years))
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
    bracket = {sex: grid_out[sex][key(a0)][key(d)][key(b)] for sex in SEXES}
    # headline numbers, derived from the rounded grid exactly as results.verify does
    cell = {sex: rounded_grid[sex][key(a0)][key(d)][key(b)] for sex in SEXES}
    headline = {
        f"{sex}_{mem}_mean_days": cell[sex][mem]["mean"] * DAYS
        for sex, mem in (
            ("female", "calibrated"),
            ("male", "calibrated"),
            ("male", "face_value"),
        )
    }
    # floor sensitivity: Del Gobbo's 61 controlled trials, randomized and not
    all_trials = {}
    for sex in SEXES:
        all_trials[sex] = {}
        for mem in ("floor_low", "floor_high"):
            structure, _ = m.scenario(mem, d, b)
            beta = m.q[
                "ln_ctt_chd" if mem == "floor_low" else "ln_ctt_all"
            ] * m.ldl_mmol_reduction(d, "tree_all_trials")
            all_trials[sex][mem] = summarize(m.gain(sex, a0, structure, beta))
    return {
        "a0": a0,
        "delta": d,
        "background": b,
        "bracket": bracket,
        "headline_days": headline,
        "floor_all_trials": all_trials,
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
    out = {}
    rr28 = m.rows["rr28_all"].estimate
    for member, role in CALIBRATION_STRATA.items():
        r = m.rows[role]
        out[member] = {
            "row": r.id,
            "rrr": r.estimate,
            "rrr_ci": [r.ci_low, r.ci_high],
            "rrr_pi": [r.pi_low, r.pi_high],
            "rr28": rr28,
            "c_point": math.log(rr28 * r.estimate) / math.log(rr28),
            "c_draws": summarize(m.q[f"c_{member}"]),
            "share_draws_c_above_1": float(np.mean(m.q[f"c_{member}"] > 1)),
            "share_draws_c_below_0": float(np.mean(m.q[f"c_{member}"] < 0)),
        }
    return out


def phase_in(sc: Scenarios) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    return {
        key(t): {
            sex: {mem: sc.stats(sex, a0, mem, d, b, years=t) for mem in MEMBERS}
            for sex in SEXES
        }
        for t in ASSUMPTIONS["phase_in_sensitivity_years"]
    }


def curves(sc: Scenarios) -> dict:
    m = sc.m
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    step = ASSUMPTIONS["marginal_step_g"]
    members = ("face_value", "calibrated")
    grams = list(range(ASSUMPTIONS["figure_dose_max_g"] + 1))
    out = {}
    for name, curve in m.curves.items():
        out[name] = {
            "kind": curve.kind,
            "rr_by_gram": {key(g): math.exp(float(curve.f(g))) for g in grams},
            "reference": {
                sex: {mem: sc.stats(sex, a0, mem, d, b, curve=name) for mem in members}
                for sex in SEXES
            },
            "marginal": {
                sex: {
                    key(bg): {
                        mem: sc.stats(sex, a0, mem, step, bg, curve=name)
                        for mem in members
                    }
                    for bg in ASSUMPTIONS["grid"]["background"]
                }
                for sex in SEXES
            },
        }
    out["cvd_main"] = {
        "kind": m.cvd_curve.kind,
        "rr_by_gram": {key(g): math.exp(float(m.cvd_curve.f(g))) for g in grams},
    }
    return out


def ala_counted(background: float, nut_ala: float) -> float:
    """Grams of a nut's ALA inside the observed range [max(bg, lo), hi]."""
    lo, hi = ASSUMPTIONS["ala_support_g"]
    return max(0, min(background + nut_ala, hi) - max(background, lo))


def ala(m: Model) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    comp = data.composition()
    basis = data.composition_basis_g()
    backgrounds = [
        m.rows["ala_background"].estimate,
        ASSUMPTIONS["ala_background_high_g"],
    ]
    out: dict = {
        "rr_per_g_row": m.rows["ala"].id,
        "support_g": ASSUMPTIONS["ala_support_g"],
        "background_g": backgrounds,
        "background_row": m.rows["ala_background"].id,
        "by_background": {},
    }
    base = {
        (sex, mem): m.gain(sex, a0, *m.scenario(mem, d, b))
        for sex in SEXES
        for mem in ("face_value", "calibrated")
    }
    for bg in backgrounds:
        per_nut = {}
        for nut in ASSUMPTIONS["nuts"]:
            nut_ala = d * comp[nut]["ala_g"] / basis
            counted = ala_counted(bg, nut_ala)
            entry = {
                "ala_basis": comp[nut]["ala_basis"],
                "nut_ala_g": nut_ala,
                "counted_ala_g": counted,
            }
            for sex in SEXES:
                entry[sex] = {}
                for mem in ("face_value", "calibrated"):
                    gain = m.gain(sex, a0, *m.scenario(mem, d, b, ala_g=counted))
                    entry[sex][mem] = {
                        "total": summarize(gain),
                        "increment": summarize(gain - base[(sex, mem)]),
                    }
            per_nut[nut] = entry
        out["by_background"][key(bg)] = per_nut
    return out


def cost(m: Model) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    prices = data.prices_by_nut()
    dates = data.price_dates()
    members = (
        "calibrated",
        "calibrated_all_cause",
        "face_value",
        "floor_high",
        "floor_low",
    )
    tree_excluded = set(ASSUMPTIONS["tree_nuts_exclude"])
    kg_per_year = d / ASSUMPTIONS["g_per_kg"] * DAYS
    # per sex and member: (discounted LY gained, discounted person-years treated,
    # undiscounted LY gained, undiscounted person-years treated), per nut group
    memo: dict[tuple, tuple[float, float, float, float]] = {}

    def outcomes(sex: str, mem: str, group: str) -> tuple[float, float, float, float]:
        k = (sex, mem, group if mem.startswith("floor") else "class")
        if k not in memo:
            if mem.startswith("floor"):
                structure = "chd" if mem == "floor_low" else "all"
                slope = m.q["ln_ctt_chd" if mem == "floor_low" else "ln_ctt_all"]
                beta = slope * m.ldl_mmol_reduction(d, group)
            else:
                structure, beta = m.scenario(mem, d, b)
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
            "floor_ldl_source": EVIDENCE_IDS[
                "ldl_peanut" if group == "peanut" else "ldl_tree"
            ],
        }
        for sex in SEXES:
            entry[sex] = {}
            for mem in members:
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


def baseline_sensitivity_2021(sc2021: Scenarios) -> dict:
    a0, d, b = REF["a0"], REF["delta"], REF["background"]
    return {
        "life_tables": data.life_table_source("2021"),
        "cause_shares_year": sc2021.m.shares[SEXES[0]].year,
        "reference": {
            sex: {mem: sc2021.stats(sex, a0, mem, d, b) for mem in MEMBERS}
            for sex in SEXES
        },
    }


def baseline_le(m: Model) -> dict:
    ages = sorted(
        {*ASSUMPTIONS["grid"]["a0"], *range(0, m.base[SEXES[0]].omega + 1, 10)}
    )
    out = {}
    for sex in SEXES:
        ours = baseline_ex(m.base[sex])
        out[sex] = {
            key(a): {
                "model": float(ours[a]),
                "published": float(m.base[sex].ex_published[a]),
            }
            for a in ages
        }
    return out


def figure_data(sc: Scenarios) -> dict:
    a0, d = REF["a0"], REF["delta"]
    step = ASSUMPTIONS["marginal_step_g"]
    grams = range(ASSUMPTIONS["figure_dose_max_g"] + 1)
    lo_age, hi_age = ASSUMPTIONS["figure_age_range"]
    ages = range(lo_age, hi_age + 1)
    bgs = range(ASSUMPTIONS["figure_background_max_g"] + 1)
    dose_members = ("floor_low", "floor_high", "calibrated", "face_value")

    def series(xs, fn: Callable[[float], dict]) -> dict[str, list[float]]:
        cols = [fn(x) for x in xs]
        return {s: [c[s] for c in cols] for s in STAT_NAMES}

    return {
        "days_by_dose": {
            "a0": a0,
            "grams": list(grams),
            **{
                sex: {
                    mem: series(
                        grams, lambda g, sex=sex, mem=mem: sc.stats(sex, a0, mem, g, 0)
                    )
                    for mem in dose_members
                }
                for sex in SEXES
            },
        },
        "days_by_age": {
            "delta": d,
            "ages": list(ages),
            **{
                sex: {
                    "calibrated": series(
                        ages, lambda a, sex=sex: sc.stats(sex, a, "calibrated", d, 0)
                    )
                }
                for sex in SEXES
            },
        },
        "marginal_by_background": {
            "a0": a0,
            "step_g": step,
            "backgrounds": list(bgs),
            **{
                sex: {
                    mem: series(
                        bgs,
                        lambda bg, sex=sex, mem=mem: sc.stats(sex, a0, mem, step, bg),
                    )
                    for mem in ("calibrated", "face_value")
                }
                for sex in SEXES
            },
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
    out["phase_in"] = phase_in(sc)
    out["curves"] = curves(sc)
    out["ala"] = ala(m)
    out["cost"] = cost(m)
    out["fadnes"] = fadnes(m, m2021)
    out["baseline_le"] = baseline_le(m)
    if m2021 is not None:
        out["baseline_2021"] = baseline_sensitivity_2021(Scenarios(m2021))
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
    "floor_alpha": 0.45,
    "marker_size": 5.5,
    "interval_80_width": 3.2,
    "interval_95_width": 1.0,
    "row_offset": 0.17,
}

SEX_COLOR = {"female": "blue", "male": "orange"}
SEX_LABEL = {"female": "Women", "male": "Men"}

FIGURE_FILES = (
    "days_by_dose.png",
    "days_by_age.png",
    "marginal_by_background.png",
    "bracket_reference.png",
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


def fig_days_by_dose(res: dict, path: Path, plt) -> None:
    s, fd = STYLE, res["figures"]["days_by_dose"]
    g = fd["grams"]
    fig, axes = plt.subplots(
        1, 2, figsize=(s["width_in"], s["height_in"]), sharey=True, layout="constrained"
    )
    for ax, sex in zip(axes, SEXES):
        d = fd[sex]
        ax.fill_between(
            g,
            _days(d["floor_low"]["mean"]),
            _days(d["floor_high"]["mean"]),
            color=s["aqua"],
            alpha=s["floor_alpha"],
            linewidth=0,
            label="Randomized floor (low to high)",
        )
        ax.fill_between(
            g,
            _days(d["calibrated"]["p10"]),
            _days(d["calibrated"]["p90"]),
            color=s["blue"],
            alpha=s["band_alpha"],
            linewidth=0,
            label="Calibrated, 80% interval",
        )
        ax.plot(
            g,
            _days(d["calibrated"]["mean"]),
            color=s["blue"],
            lw=s["line_width"],
            label="Calibrated, mean",
        )
        ax.plot(
            g,
            _days(d["face_value"]["mean"]),
            color=s["orange"],
            lw=s["line_width"],
            label="Face value, mean",
        )
        ax.set_title(
            SEX_LABEL[sex], loc="left", color=s["ink"], fontsize=s["font_size"]
        )
        ax.set_xlim(g[0], g[-1])
        ax.set_xlabel("Nuts added (g/day)")
        _thousands(ax)
    axes[0].set_ylim(bottom=0)
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


def fig_days_by_age(res: dict, path: Path, plt) -> None:
    s, fd = STYLE, res["figures"]["days_by_age"]
    ages = fd["ages"]
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["height_in"]), layout="constrained"
    )
    for sex in SEXES:
        d, color = fd[sex]["calibrated"], s[SEX_COLOR[sex]]
        ax.fill_between(
            ages,
            _days(d["p10"]),
            _days(d["p90"]),
            color=color,
            alpha=s["band_alpha"],
            linewidth=0,
        )
        ax.plot(
            ages,
            _days(d["mean"]),
            color=color,
            lw=s["line_width"],
            label=f"{SEX_LABEL[sex]}, mean and 80% interval",
        )
        ax.annotate(
            SEX_LABEL[sex],
            (ages[-1], _days(d["mean"])[-1]),
            xytext=(4, 0),
            textcoords="offset points",
            va="center",
            color=s["ink_secondary"],
        )
    ax.set_xlim(ages[0], ages[-1])
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Age at which the person starts eating nuts (years)")
    ax.set_ylabel("Life expectancy gained (days)")
    _thousands(ax)
    ax.legend(loc="upper right")
    _save(fig, path)
    plt.close(fig)


def fig_marginal(res: dict, path: Path, plt) -> None:
    s, fd = STYLE, res["figures"]["marginal_by_background"]
    bgs = fd["backgrounds"]
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["height_in"]), layout="constrained"
    )
    for sex in SEXES:
        d, color = fd[sex]["calibrated"], s[SEX_COLOR[sex]]
        ax.fill_between(
            bgs,
            _days(d["p10"]),
            _days(d["p90"]),
            color=color,
            alpha=s["band_alpha"],
            linewidth=0,
        )
        ax.plot(
            bgs,
            _days(d["mean"]),
            color=color,
            lw=s["line_width"],
            label=f"{SEX_LABEL[sex]}, mean and 80% interval",
        )
    ax.set_xlim(bgs[0], bgs[-1])
    ax.set_ylim(bottom=0)
    ax.set_xlabel(f"Nuts already eaten (g/day), before adding {fd['step_g']} g/day")
    ax.set_ylabel("Life expectancy gained (days)")
    _thousands(ax)
    ax.legend(loc="upper right")
    _save(fig, path)
    plt.close(fig)


BRACKET_ROWS = (
    ("face_value", "Face value (c = 1)"),
    ("calibrated", "Calibrated: diet-intake stratum"),
    ("calibrated_overall", "Calibrated: all pairs"),
    ("calibrated_all_cause", "Calibrated: all-cause stratum"),
    ("cvd_only", "CVD deaths only"),
    ("floor_high", "Randomized floor, high"),
    ("floor_low", "Randomized floor, low"),
)


def fig_bracket(res: dict, path: Path, plt) -> None:
    from matplotlib.lines import Line2D

    s = STYLE
    br = res["reference"]["bracket"]
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["tall_height_in"]), layout="constrained"
    )
    n = len(BRACKET_ROWS)
    for i, (mem, _) in enumerate(BRACKET_ROWS):
        y0 = n - 1 - i
        for sex, sign in zip(SEXES, (1, -1)):
            st, color = br[sex][mem], s[SEX_COLOR[sex]]
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
    ax.set_yticklabels([label for _, label in reversed(BRACKET_ROWS)])
    ax.tick_params(axis="y", length=0)
    ax.grid(axis="y", visible=False)
    ax.axvline(0, color=s["axis"], lw=s["hairline"])
    ax.set_xlabel(
        f"Life expectancy gained (days), age {res['reference']['a0']}, "
        f"{res['reference']['background']} to {res['reference']['delta']} g/day"
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


def fig_cost(res: dict, path: Path, plt) -> None:
    from matplotlib.lines import Line2D

    s, c = STYLE, res["cost"]
    member = "calibrated"
    nuts = sorted(c["by_nut"], key=lambda k: c["by_nut"][k]["usd_per_year"])
    fig, ax = plt.subplots(
        figsize=(s["width_in"], s["height_in"]), layout="constrained"
    )
    n = len(nuts)
    for i, nut in enumerate(nuts):
        y0 = n - 1 - i
        for sex, sign in zip(SEXES, (1, -1)):
            v = c["by_nut"][nut][sex][member]["usd_per_life_year"]
            ax.plot(
                [v],
                [y0 + sign * s["row_offset"]],
                "o",
                color=s[SEX_COLOR[sex]],
                markersize=s["marker_size"],
                markeredgecolor=s["surface"],
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
        f"calibrated, {c['delta']} g/day from age {c['a0']}"
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
    ]
    fig.legend(
        handles, [SEX_LABEL[x] for x in SEXES], loc="outside lower center", ncols=2
    )
    _save(fig, path)
    plt.close(fig)


def write_figures(res: dict, figures_dir: Path = FIGURES) -> list[Path]:
    plt = _plt()
    figures_dir.mkdir(parents=True, exist_ok=True)
    makers = (fig_days_by_dose, fig_days_by_age, fig_marginal, fig_bracket, fig_cost)
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
    ref = res["reference"]["bracket"]
    for sex in SEXES:
        row = ", ".join(
            f"{mem} {ref[sex][mem]['mean'] * DAYS:,.0f}"
            for mem in ("floor_low", "floor_high", "calibrated", "face_value")
        )
        print(f"{sex}: days gained, age {REF['a0']}, 0 -> {REF['delta']} g/day: {row}")
    print(
        f"wrote {args.results} and {len(FIGURE_FILES)} figures in "
        f"{time.perf_counter() - t0:.1f} s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
