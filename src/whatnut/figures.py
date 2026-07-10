"""Generate figures for the What Nut paper.

This module creates visualizations that explain the model methodology
and present results in an accessible way.
"""

from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np

# Use a clean style
plt.style.use("seaborn-v0_8-whitegrid")

# Color palette - accessible and professional
COLORS = {
    "cvd": "#E74C3C",  # Red for CVD
    "cancer": "#9B59B6",  # Purple for cancer
    "other": "#3498DB",  # Blue for other
    "primary": "#2C3E50",  # Dark blue-gray
    "secondary": "#7F8C8D",  # Gray
    "highlight": "#27AE60",  # Green for positive
    "nuts": {
        "walnut": "#8B4513",
        "almond": "#DEB887",
        "peanut": "#CD853F",
        "cashew": "#F5DEB3",
        "pistachio": "#90EE90",
        "macadamia": "#FFDAB9",
        "pecan": "#D2691E",
        "hazelnut": "#A66A2C",
    },
}

FIGURE_DIR = Path(__file__).parent.parent.parent / "docs" / "_static" / "figures"


def ensure_figure_dir():
    """Create figure directory if it doesn't exist."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def fig1_model_architecture():
    """Create a decision-first diagram of the model architecture."""
    from whatnut.results import r

    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis("off")

    ax.text(
        7,
        7.55,
        "Decision-First Model Architecture",
        fontsize=16,
        fontweight="bold",
        ha="center",
        va="center",
    )

    input_style = {
        "boxstyle": "round,pad=0.35",
        "facecolor": "#E8F6F3",
        "edgecolor": COLORS["primary"],
        "linewidth": 1.5,
    }
    stage_style = {
        "boxstyle": "round,pad=0.4",
        "facecolor": "#FDF2E9",
        "edgecolor": "#E67E22",
        "linewidth": 1.5,
    }
    output_style = {
        "boxstyle": "round,pad=0.4",
        "facecolor": "#D5F5E3",
        "edgecolor": COLORS["highlight"],
        "linewidth": 1.5,
    }

    input_nodes = [
        (1.3, "USDA Nutrient\nComposition"),
        (3.9, "Evidence Priors\n+ Nut Adjustments"),
        (6.5, "Confounding\nEvidence"),
        (9.1, "Life, Quality +\nCause Tables"),
        (11.9, "Retail Prices +\nQALY Value (λ)"),
    ]
    for x, label in input_nodes:
        ax.text(
            x,
            6.45,
            label,
            fontsize=9.5,
            ha="center",
            va="center",
            bbox=input_style,
        )

    ax.text(
        2.8,
        4.65,
        "Paired Cause-Specific\nEffect Draws",
        fontsize=10,
        ha="center",
        va="center",
        bbox=stage_style,
    )
    ax.text(
        7,
        4.65,
        "Batched Lifecycle Projection\nLife Years • QALYs • Consumer Cost",
        fontsize=10,
        ha="center",
        va="center",
        bbox=stage_style,
    )
    ax.text(
        11.2,
        4.65,
        "Decision Specification\nComparator • WTP • Options",
        fontsize=10,
        ha="center",
        va="center",
        bbox=stage_style,
    )

    arrow = dict(arrowstyle="->", color=COLORS["secondary"], lw=1.5)
    for x in (1.3, 3.9, 6.5):
        ax.annotate("", xy=(2.8, 5.15), xytext=(x, 6.05), arrowprops=arrow)
    ax.annotate("", xy=(7, 5.15), xytext=(9.1, 6.05), arrowprops=arrow)
    ax.annotate("", xy=(11.2, 5.15), xytext=(11.9, 6.05), arrowprops=arrow)
    ax.annotate("", xy=(5.55, 4.65), xytext=(4.25, 4.65), arrowprops=arrow)
    ax.annotate("", xy=(8.45, 4.65), xytext=(9.75, 4.65), arrowprops=arrow)

    decision_box = mpatches.FancyBboxPatch(
        (4.2, 2.45),
        5.6,
        1.15,
        boxstyle="round,pad=0.1",
        facecolor="#EBF5FB",
        edgecolor=COLORS["cvd"],
        linewidth=2.5,
    )
    ax.add_patch(decision_box)
    ax.text(
        7,
        3.13,
        "All-Option Decision Evaluator",
        fontsize=11,
        fontweight="bold",
        ha="center",
        va="center",
    )
    ax.text(
        7,
        2.72,
        (
            f"{r.n_samples:,} paired draws • comparator included • "
            f"E[NMB] at USD {r.willingness_to_pay:,.0f}/QALY • tie-safe P(optimal)"
        ),
        fontsize=8,
        ha="center",
        va="center",
        color=COLORS["secondary"],
    )
    ax.annotate("", xy=(6.35, 3.6), xytext=(6.55, 4.15), arrowprops=arrow)
    ax.annotate("", xy=(8.55, 3.6), xytext=(10.5, 4.15), arrowprops=arrow)

    icer_label = r.icer_range.replace("$", r"\$")
    output_nodes = [
        (1.8, "Pathway-Specific\nRelative Risks"),
        (5.0, f"Life Years + QALYs\n({r.months_range} months)"),
        (
            8.5,
            f"Consumer Cost +\nExpected ICERs\n({icer_label})",
        ),
        (12.0, "Expected NMB + P(optimal)\nRecommendation + Ranking"),
    ]
    for x, label in output_nodes:
        ax.text(
            x,
            1.15,
            label,
            fontsize=9.5,
            ha="center",
            va="center",
            bbox=output_style,
        )

    ax.annotate("", xy=(1.8, 1.65), xytext=(2.8, 4.15), arrowprops=arrow)
    for x in (5.0, 8.5, 12.0):
        ax.annotate("", xy=(x, 1.7), xytext=(7, 2.45), arrowprops=arrow)

    ax.text(
        0.45,
        3.05,
        f"CVD RR: {r.cvd_effect_range}\n"
        f"Cancer RR: {r.cancer_effect_range}\n"
        f"Other RR: {r.other_effect_range}",
        fontsize=8,
        ha="left",
        va="center",
        family="monospace",
        color=COLORS["secondary"],
    )

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "model_architecture.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "model_architecture.png"


def fig2_pathway_rrs():
    """Create a bar chart comparing pathway-specific relative risks."""
    from whatnut.results import r

    nuts = [nut.name for nut in r.nuts.values()]
    nut_keys = [name.lower() for name in nuts]

    cvd_rrs = [r.pathway_rrs[k].cvd for k in nut_keys]
    cancer_rrs = [r.pathway_rrs[k].cancer for k in nut_keys]
    other_rrs = [r.pathway_rrs[k].other for k in nut_keys]

    # Convert to % reduction for easier interpretation
    cvd_reduction = [(1 - rr) * 100 for rr in cvd_rrs]
    cancer_reduction = [(1 - rr) * 100 for rr in cancer_rrs]
    other_reduction = [(1 - rr) * 100 for rr in other_rrs]

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(nuts))
    width = 0.25

    bars1 = ax.bar(
        x - width,
        cvd_reduction,
        width,
        label="CVD Mortality",
        color=COLORS["cvd"],
        alpha=0.85,
    )
    ax.bar(
        x,
        other_reduction,
        width,
        label="Other Mortality",
        color=COLORS["other"],
        alpha=0.85,
    )
    ax.bar(
        x + width,
        cancer_reduction,
        width,
        label="Cancer Mortality",
        color=COLORS["cancer"],
        alpha=0.85,
    )

    ax.set_ylabel("Mortality Reduction (%)", fontsize=12)
    ax.set_title(
        "Pathway-Specific Mortality Reduction by Nut Type",
        fontsize=14,
        fontweight="bold",
    )
    ax.set_xticks(x)
    ax.set_xticklabels(nuts, fontsize=10)
    ax.legend(loc="upper left", fontsize=10)
    # Dynamic y-limit with ~35% headroom so the annotation box fits cleanly
    # above the tallest bar
    ymax = max(cvd_reduction + cancer_reduction + other_reduction + [1e-9])
    ax.set_ylim(0, ymax * 1.45)

    # Add value labels on CVD bars (the largest). Use one decimal because
    # the skeptical model produces small per-cause reductions.
    for bar, val in zip(bars1, cvd_reduction):
        ax.annotate(
            f"{val:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, bar.get_height()),
            xytext=(0, 3),
            textcoords="offset points",
            ha="center",
            fontsize=8,
        )

    # Annotation comparing CVD vs cancer reductions, derived live so it
    # tracks the current prior specification.
    cvd_max = max(cvd_reduction) if cvd_reduction else 0.0
    cancer_max = max(cancer_reduction) if cancer_reduction else 1e-9
    ratio = cvd_max / cancer_max if cancer_max > 0 else float("inf")
    ratio_label = f"{ratio:.0f}×" if ratio < 100 else "much larger"
    ax.text(
        0.98,
        0.95,
        f"CVD reductions are\n{ratio_label} larger than\ncancer reductions",
        transform=ax.transAxes,
        fontsize=9,
        ha="right",
        va="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "pathway_rrs.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "pathway_rrs.png"


def fig3_forest_plot():
    """Create a forest plot of life years gained by nut type."""
    from whatnut.results import r

    # Sort by life years
    nuts_sorted = sorted(r.nuts.values(), key=lambda x: x.life_years, reverse=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    y_positions = np.arange(len(nuts_sorted))

    for i, nut in enumerate(nuts_sorted):
        # Point estimate
        ax.plot(nut.life_years, i, "o", color=COLORS["primary"], markersize=10)

        # Direct 95% Monte Carlo model interval for life years.
        ci_lower = nut.life_years_ci_lower
        ci_upper = nut.life_years_ci_upper
        ax.hlines(i, ci_lower, ci_upper, color=COLORS["primary"], linewidth=2)

        # Caps
        ax.vlines(ci_lower, i - 0.1, i + 0.1, color=COLORS["primary"], linewidth=2)
        ax.vlines(ci_upper, i - 0.1, i + 0.1, color=COLORS["primary"], linewidth=2)

        # Value label (use 1-decimal months so "0 mo" never appears for
        # sub-month gains).
        ax.text(
            ci_upper + 0.02,
            i,
            f"{nut.life_years:.2f} yr ({nut.months:.1f} mo)",
            va="center",
            fontsize=10,
        )

    ax.set_yticks(y_positions)
    ax.set_yticklabels([n.name for n in nuts_sorted], fontsize=11)
    ax.set_xlabel("Life Years Gained", fontsize=12)
    ax.set_title(
        "Life Expectancy Gains from Daily Nut Consumption (28g/day)",
        fontsize=14,
        fontweight="bold",
    )
    ax.axvline(0, color="gray", linestyle="--", linewidth=0.5)
    # Scale to the interval endpoints, not only the point estimates, and leave
    # enough right-hand room for labels placed beyond each upper endpoint.
    interval_lowers = [nut.life_years_ci_lower for nut in nuts_sorted]
    interval_uppers = [nut.life_years_ci_upper for nut in nuts_sorted]
    data_min = min(interval_lowers + [0.0])
    data_max = max(interval_uppers + [0.05])
    data_span = max(data_max - data_min, 0.1)
    xmin = data_min - 0.08 * data_span
    xmax = data_max + 0.38 * data_span
    ax.set_xlim(min(xmin, -0.05), xmax)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "forest_plot.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "forest_plot.png"


def fig4_cause_fractions():
    """Show how cause-of-death fractions vary with age, using the live
    cause_fractions.yaml table rather than a stylized approximation."""
    from whatnut.config import get_cause_fractions

    ages = np.arange(40, 96, 5)
    cvd_frac = np.array([get_cause_fractions(a)[0] for a in ages])
    cancer_frac = np.array([get_cause_fractions(a)[1] for a in ages])
    other_frac = np.array([get_cause_fractions(a)[2] for a in ages])

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.stackplot(
        ages,
        cvd_frac * 100,
        cancer_frac * 100,
        other_frac * 100,
        labels=["CVD", "Cancer", "Other"],
        colors=[COLORS["cvd"], COLORS["cancer"], COLORS["other"]],
        alpha=0.8,
    )

    ax.set_xlabel("Age", fontsize=12)
    ax.set_ylabel("Mortality Share (%)", fontsize=12)
    ax.set_title("Age-Varying Cause-of-Death Fractions", fontsize=14, fontweight="bold")
    ax.legend(loc="upper right", fontsize=10)
    ax.set_xlim(40, 95)
    ax.set_ylim(0, 100)

    # Annotation reads the start/end CVD fraction live
    cvd_start_pct = int(round(cvd_frac[0] * 100))
    cvd_end_pct = int(round(cvd_frac[-1] * 100))
    ax.annotate(
        f"CVD fraction shifts\nwith age ({cvd_start_pct}% → {cvd_end_pct}%)",
        xy=(75, 30),
        xytext=(55, 15),
        fontsize=9,
        ha="center",
        arrowprops=dict(arrowstyle="->", color="gray"),
    )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "cause_fractions.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "cause_fractions.png"


def fig5_confounding_calibration():
    """Visualize the confounding calibration evidence synthesis.

    Prior parameters are sourced from the generated results.json so the
    figure tracks the live Beta(alpha, beta) configuration and never
    contradicts the paper text.
    """
    from scipy import stats

    from whatnut.results import r

    alpha = r.confounding_alpha
    beta = r.confounding_beta
    mean = r.confounding_mean
    ci_lower = r.confounding_ci_lower
    ci_upper = r.confounding_ci_upper

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left panel: Evidence sources — implied causal-fraction bounds from
    # each evidence line (see Methods §"Confounding Calibration").
    ax1 = axes[0]
    sources = [
        "LDL Pathway\n(mechanism floor)",
        "Mendelian\nRandomization",
        "Golestan Cohort\n(Iran, low confounding)",
    ]
    values = [0.12, 0.05, 1.0]
    colors = ["#3498DB", "#9B59B6", "#27AE60"]

    bars = ax1.barh(sources, values, color=colors, alpha=0.7, edgecolor="black")

    ax1.set_xlabel("Implied Causal Fraction", fontsize=11)
    ax1.set_title(
        "Evidence Sources for Causal Fraction", fontsize=12, fontweight="bold"
    )
    ax1.set_xlim(0, 1.2)
    ax1.axvline(
        mean, color="red", linestyle="--", linewidth=2, label=f"Prior mean ({mean:.2f})"
    )

    for bar, val in zip(bars, values):
        ax1.text(
            val + 0.03,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0%}",
            va="center",
            fontsize=10,
        )

    ax1.legend(loc="lower right")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Right panel: Prior distribution (live from config)
    ax2 = axes[1]
    x = np.linspace(0, 1, 200)
    prior = stats.beta(alpha, beta)

    ax2.fill_between(x, prior.pdf(x), alpha=0.3, color=COLORS["primary"])
    ax2.plot(
        x,
        prior.pdf(x),
        color=COLORS["primary"],
        linewidth=2,
        label=f"Beta({alpha:g}, {beta:g})",
    )

    ax2.axvline(
        mean, color="red", linestyle="--", linewidth=2, label=f"Mean = {mean:.2f}"
    )
    ax2.axvline(ci_lower, color="gray", linestyle=":", linewidth=1.5)
    ax2.axvline(ci_upper, color="gray", linestyle=":", linewidth=1.5)

    in_ci = (x >= ci_lower) & (x <= ci_upper)
    ax2.fill_between(
        x[in_ci],
        prior.pdf(x[in_ci]),
        alpha=0.2,
        color="green",
        label=f"95% prior interval: [{ci_lower:.2f}, {ci_upper:.2f}]",
    )

    ax2.set_xlabel("Causal Fraction", fontsize=11)
    ax2.set_ylabel("Density", fontsize=11)
    ax2.set_title(
        "Prior Distribution for Causal Fraction", fontsize=12, fontweight="bold"
    )
    ax2.legend(loc="upper right", fontsize=9)
    ax2.set_xlim(0, 1)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "confounding_calibration.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "confounding_calibration.png"


def fig6_nutrient_contributions():
    """Heatmap showing nutrient contributions to each nut's effect."""
    from whatnut.config import (
        NUT_IDS,
        get_pathway_priors,
    )

    nuts = list(NUT_IDS)
    cvd_priors = get_pathway_priors("cvd")

    # Key nutrients
    key_nutrients = [
        "ala_omega3",
        "fiber",
        "magnesium",
        "omega7",
        "saturated_fat",
        "vitamin_e",
        "protein",
    ]
    nutrient_labels = [
        "ALA Omega-3",
        "Fiber",
        "Magnesium",
        "Omega-7",
        "Saturated fat",
        "Vitamin E",
        "Protein",
    ]

    # Build nutrient matrix for just key nutrients
    from whatnut.config import get_nut as _get_nut

    contributions = np.zeros((len(nuts), len(key_nutrients)))

    for i, nut in enumerate(nuts):
        nut_profile = _get_nut(nut)
        for j, nutrient in enumerate(key_nutrients):
            amount = nut_profile.nutrients.get(nutrient, 0)
            effect = cvd_priors[nutrient].mean
            contributions[i, j] = -amount * effect * 100

    fig, ax = plt.subplots(figsize=(10, 6))

    color_limit = max(float(np.max(np.abs(contributions))), 1.0)
    im = ax.imshow(
        contributions,
        cmap="RdYlGn",
        aspect="auto",
        vmin=-color_limit,
        vmax=color_limit,
    )

    ax.set_xticks(np.arange(len(key_nutrients)))
    ax.set_yticks(np.arange(len(nuts)))
    ax.set_xticklabels(nutrient_labels, fontsize=10, rotation=45, ha="right")
    ax.set_yticklabels([n.title() for n in nuts], fontsize=10)

    # Add value annotations
    for i in range(len(nuts)):
        for j in range(len(key_nutrients)):
            val = contributions[i, j]
            color = "white" if abs(val) > 0.55 * color_limit else "black"
            ax.text(
                j, i, f"{val:.1f}", ha="center", va="center", fontsize=9, color=color
            )

    ax.set_title(
        "Nominal Nutrient Contributions to CVD Log-RR (Pre-Shrinkage)",
        fontsize=14,
        fontweight="bold",
    )

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label("Protective log-RR contribution (percentage points)", fontsize=10)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "nutrient_contributions.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "nutrient_contributions.png"


def fig7_icer_comparison():
    """Compare expected consumer ICERs with an illustrative QALY value."""
    from whatnut.results import r

    # An expected ICER is undefined when the expected incremental QALY is
    # non-positive. Keep those options in the decision analysis, but exclude
    # undefined ratios from this ratio-only chart.
    nuts_sorted = sorted(
        (nut for nut in r.nuts.values() if nut.icer is not None),
        key=lambda nut: nut.icer,
    )

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(nuts_sorted))
    icers = [n.icer for n in nuts_sorted]

    bars = ax.bar(
        x,
        icers,
        color=[COLORS["nuts"].get(n.name.lower(), "#888") for n in nuts_sorted],
        alpha=0.85,
        edgecolor="black",
    )

    # This consumer-perspective numerator is not a health-system cost
    # inventory, so the line is an illustrative QALY valuation rather than a
    # payer cost-effectiveness threshold.
    ax.axhline(
        r.willingness_to_pay,
        color="red",
        linestyle="--",
        linewidth=2,
        label=f"Illustrative QALY value (\\${r.willingness_to_pay:,.0f})",
    )

    ax.set_xticks(x)
    ax.set_xticklabels([n.name for n in nuts_sorted], fontsize=10)
    ax.set_ylabel("Expected ICER ($/QALY)", fontsize=12)
    ax.set_title("Expected Consumer ICER by Nut Type", fontsize=14, fontweight="bold")
    ax.legend(loc="upper left", fontsize=9)

    # Dynamic y-limit so the chart scales with the live ICER distribution
    ymax = max(icers + [r.willingness_to_pay, 1]) * 1.15
    ax.set_ylim(0, ymax)

    # Value labels (offset 1.5% of y-axis so they sit above the bars).
    # Escape $ to keep matplotlib out of math mode.
    offset = ymax * 0.015
    for bar, val in zip(bars, icers):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + offset,
            f"\\${val:,.0f}",
            ha="center",
            fontsize=9,
        )

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Annotation derived live from how many defined ratios fall below the
    # benchmark.
    n_total = len(nuts_sorted)
    n_below_benchmark = sum(1 for n in nuts_sorted if n.icer <= r.willingness_to_pay)
    if n_total:
        annotation = (
            f"{n_below_benchmark}/{n_total} defined expected ICERs below\n"
            f"the ${r.willingness_to_pay:,.0f}/QALY benchmark"
        )
    else:
        annotation = (
            "No expected ICER is defined\n(expected QALY gains are non-positive)"
        )
    # Escape $ so matplotlib doesn't enter math mode
    annotation = annotation.replace("$", r"\$")
    annotation_color = "lightgreen" if n_below_benchmark else "mistyrose"
    ax.text(
        0.98,
        0.15,
        annotation,
        transform=ax.transAxes,
        fontsize=10,
        ha="right",
        va="bottom",
        bbox=dict(boxstyle="round", facecolor=annotation_color, alpha=0.7),
    )

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(
        FIGURE_DIR / "icer_comparison.png",
        dpi=150,
        bbox_inches="tight",
        facecolor="white",
        edgecolor="none",
    )
    plt.close(fig)
    return FIGURE_DIR / "icer_comparison.png"


def generate_all_figures():
    """Generate all figures for the paper."""
    print("Generating figures...")

    figures = {}

    print("  1. Model architecture diagram...")
    figures["architecture"] = fig1_model_architecture()

    print("  2. Pathway-specific RRs...")
    figures["pathway_rrs"] = fig2_pathway_rrs()

    print("  3. Forest plot of life years...")
    figures["forest"] = fig3_forest_plot()

    print("  4. Age-varying cause fractions...")
    figures["cause_fractions"] = fig4_cause_fractions()

    print("  5. Confounding calibration...")
    figures["confounding"] = fig5_confounding_calibration()

    print("  6. Nutrient contributions heatmap...")
    figures["nutrients"] = fig6_nutrient_contributions()

    print("  7. ICER comparison...")
    figures["icer"] = fig7_icer_comparison()

    print(f"\nAll figures saved to {FIGURE_DIR}")
    return figures


if __name__ == "__main__":
    generate_all_figures()
