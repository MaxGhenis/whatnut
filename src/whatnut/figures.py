"""Generate figures for the What Nut paper.

This module creates visualizations that explain the model methodology
and present results in an accessible way.
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

# Use a clean style
plt.style.use('seaborn-v0_8-whitegrid')

# Color palette - accessible and professional
COLORS = {
    'cvd': '#E74C3C',      # Red for CVD
    'cancer': '#9B59B6',   # Purple for cancer
    'other': '#3498DB',    # Blue for other
    'primary': '#2C3E50',  # Dark blue-gray
    'secondary': '#7F8C8D', # Gray
    'highlight': '#27AE60', # Green for positive
    'nuts': {
        'walnut': '#8B4513',
        'almond': '#DEB887',
        'peanut': '#CD853F',
        'cashew': '#F5DEB3',
        'pistachio': '#90EE90',
        'macadamia': '#FFDAB9',
        'pecan': '#D2691E',
    }
}

FIGURE_DIR = Path(__file__).parent.parent.parent / 'docs' / '_static' / 'figures'


def ensure_figure_dir():
    """Create figure directory if it doesn't exist."""
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)


def fig1_model_architecture():
    """Create a conceptual diagram of the model architecture.

    Shows: Nutrients → Pathway Priors → Hierarchical Model →
           Confounding Adjustment → Lifecycle Integration → Life Years/QALYs
    """
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')

    # Box style
    box_style = dict(boxstyle='round,pad=0.3', facecolor='white',
                     edgecolor=COLORS['primary'], linewidth=2)
    arrow_style = dict(arrowstyle='->', color=COLORS['primary'],
                       linewidth=2, mutation_scale=15)

    # Title
    ax.text(7, 7.5, 'Hierarchical Bayesian Model Architecture',
            fontsize=16, fontweight='bold', ha='center', va='center')

    # Layer 1: Inputs
    ax.text(2, 6, 'USDA Nutrient\nComposition', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F6F3',
                     edgecolor=COLORS['primary'], linewidth=1.5))
    ax.text(5, 6, 'Meta-Analysis\nPriors', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F6F3',
                     edgecolor=COLORS['primary'], linewidth=1.5))
    ax.text(8, 6, 'Confounding\nEvidence', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F6F3',
                     edgecolor=COLORS['primary'], linewidth=1.5))
    ax.text(11, 6, 'CDC Life\nTables', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#E8F6F3',
                     edgecolor=COLORS['primary'], linewidth=1.5))

    # Arrows down
    for x in [2, 5, 8, 11]:
        ax.annotate('', xy=(x, 5.2), xytext=(x, 5.6),
                   arrowprops=dict(arrowstyle='->', color=COLORS['secondary'], lw=1.5))

    # Layer 2: Processing
    ax.text(3.5, 4.5, 'Nutrient × Pathway\nEffect Priors', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FDF2E9',
                     edgecolor='#E67E22', linewidth=1.5))
    ax.text(8, 4.5, 'Beta(2.5, 2.5)\nCausal Fraction', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FDF2E9',
                     edgecolor='#E67E22', linewidth=1.5))
    ax.text(11, 4.5, 'Age-Varying\nMortality Rates', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FDF2E9',
                     edgecolor='#E67E22', linewidth=1.5))

    # Arrows to central model
    ax.annotate('', xy=(6.5, 3.3), xytext=(3.5, 4.1),
               arrowprops=dict(arrowstyle='->', color=COLORS['secondary'], lw=1.5))
    ax.annotate('', xy=(7, 3.3), xytext=(8, 4.1),
               arrowprops=dict(arrowstyle='->', color=COLORS['secondary'], lw=1.5))

    # Layer 3: Core Model (larger box)
    model_box = mpatches.FancyBboxPatch((4.5, 2.2), 5, 1.2,
                                         boxstyle='round,pad=0.1',
                                         facecolor='#EBF5FB', edgecolor=COLORS['cvd'],
                                         linewidth=2.5)
    ax.add_patch(model_box)
    ax.text(7, 2.8, 'Hierarchical Bayesian Model (PyMC)',
            fontsize=11, fontweight='bold', ha='center', va='center')
    ax.text(7, 2.4, 'Non-centered parameterization • 4 chains × 1000 draws • 0% divergences',
            fontsize=8, ha='center', va='center', color=COLORS['secondary'])

    # Arrow from lifecycle
    ax.annotate('', xy=(9.5, 2.8), xytext=(11, 4.1),
               arrowprops=dict(arrowstyle='->', color=COLORS['secondary'], lw=1.5))

    # Arrow down
    ax.annotate('', xy=(7, 1.8), xytext=(7, 2.2),
               arrowprops=dict(arrowstyle='->', color=COLORS['primary'], lw=2))

    # Layer 4: Outputs
    ax.text(4, 1, 'Pathway-Specific RRs', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#FADBD8',
                     edgecolor=COLORS['cvd'], linewidth=1.5))
    ax.text(7, 1, 'Life Years\n(6-11 months)', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#D5F5E3',
                     edgecolor=COLORS['highlight'], linewidth=2))
    ax.text(10, 1, 'ICERs\n($2,700-$21,600)', fontsize=10, ha='center', va='center',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='#D5F5E3',
                     edgecolor=COLORS['highlight'], linewidth=1.5))

    # Pathway breakdown annotation
    ax.text(1, 1, 'CVD: 0.69-0.80\nCancer: 0.93-0.99\nOther: 0.88-0.94',
            fontsize=8, ha='left', va='center',
            family='monospace', color=COLORS['secondary'])

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'model_architecture.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'model_architecture.png'


def fig2_pathway_rrs():
    """Create a bar chart comparing pathway-specific relative risks."""
    from whatnut.paper_results import r

    nuts = ['Walnut', 'Almond', 'Peanut', 'Cashew', 'Pistachio', 'Macadamia', 'Pecan']
    nut_keys = [n.lower() for n in nuts]

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

    bars1 = ax.bar(x - width, cvd_reduction, width, label='CVD Mortality',
                   color=COLORS['cvd'], alpha=0.85)
    bars2 = ax.bar(x, other_reduction, width, label='Other Mortality',
                   color=COLORS['other'], alpha=0.85)
    bars3 = ax.bar(x + width, cancer_reduction, width, label='Cancer Mortality',
                   color=COLORS['cancer'], alpha=0.85)

    ax.set_ylabel('Mortality Reduction (%)', fontsize=12)
    ax.set_title('Pathway-Specific Mortality Reduction by Nut Type', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(nuts, fontsize=10)
    ax.legend(loc='upper right', fontsize=10)
    ax.set_ylim(0, 35)

    # Add value labels on CVD bars (the largest)
    for bar, val in zip(bars1, cvd_reduction):
        ax.annotate(f'{val:.0f}%', xy=(bar.get_x() + bar.get_width()/2, bar.get_height()),
                   xytext=(0, 3), textcoords='offset points', ha='center', fontsize=8)

    # Add annotation about CVD dominance
    ax.text(0.98, 0.95, 'CVD reductions are\n5-10× larger than\ncancer reductions',
            transform=ax.transAxes, fontsize=9, ha='right', va='top',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'pathway_rrs.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'pathway_rrs.png'


def fig3_forest_plot():
    """Create a forest plot of life years gained by nut type."""
    from whatnut.paper_results import r

    # Sort by life years
    nuts_sorted = sorted(r.nuts.values(), key=lambda x: x.life_years, reverse=True)

    fig, ax = plt.subplots(figsize=(10, 6))

    y_positions = np.arange(len(nuts_sorted))

    for i, nut in enumerate(nuts_sorted):
        # Point estimate
        ax.plot(nut.life_years, i, 'o', color=COLORS['primary'], markersize=10)

        # CI line (approximate from QALY CI scaled)
        ci_scale = nut.life_years / nut.qaly_mean if nut.qaly_mean > 0 else 1
        ci_lower = max(0, nut.qaly_ci_lower * ci_scale)
        ci_upper = nut.qaly_ci_upper * ci_scale
        ax.hlines(i, ci_lower, ci_upper, color=COLORS['primary'], linewidth=2)

        # Caps
        ax.vlines(ci_lower, i-0.1, i+0.1, color=COLORS['primary'], linewidth=2)
        ax.vlines(ci_upper, i-0.1, i+0.1, color=COLORS['primary'], linewidth=2)

        # Value label
        ax.text(ci_upper + 0.05, i, f'{nut.life_years:.2f} yr ({nut.months:.0f} mo)',
                va='center', fontsize=10)

    ax.set_yticks(y_positions)
    ax.set_yticklabels([n.name for n in nuts_sorted], fontsize=11)
    ax.set_xlabel('Life Years Gained', fontsize=12)
    ax.set_title('Life Expectancy Gains from Daily Nut Consumption (28g/day)',
                 fontsize=14, fontweight='bold')
    ax.axvline(0, color='gray', linestyle='--', linewidth=0.5)
    ax.set_xlim(-0.2, 2.0)

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'forest_plot.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'forest_plot.png'


def fig4_cause_fractions():
    """Show how cause-of-death fractions vary with age."""
    ages = np.arange(40, 100, 5)

    # Approximate cause fractions (based on CDC data patterns)
    # CVD increases with age, cancer peaks mid-life, other decreases
    cvd_frac = 0.20 + 0.003 * (ages - 40)  # 20% at 40, ~38% at 100
    cancer_frac = 0.25 - 0.002 * (ages - 40)  # 25% at 40, ~13% at 100
    other_frac = 1 - cvd_frac - cancer_frac

    fig, ax = plt.subplots(figsize=(10, 6))

    ax.stackplot(ages, cvd_frac * 100, cancer_frac * 100, other_frac * 100,
                 labels=['CVD', 'Cancer', 'Other'],
                 colors=[COLORS['cvd'], COLORS['cancer'], COLORS['other']],
                 alpha=0.8)

    ax.set_xlabel('Age', fontsize=12)
    ax.set_ylabel('Mortality Share (%)', fontsize=12)
    ax.set_title('Age-Varying Cause-of-Death Fractions', fontsize=14, fontweight='bold')
    ax.legend(loc='upper right', fontsize=10)
    ax.set_xlim(40, 95)
    ax.set_ylim(0, 100)

    # Annotation
    ax.annotate('CVD fraction increases\nwith age (20% → 40%)',
               xy=(75, 30), xytext=(55, 15),
               fontsize=9, ha='center',
               arrowprops=dict(arrowstyle='->', color='gray'))

    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'cause_fractions.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'cause_fractions.png'


def fig5_confounding_calibration():
    """Visualize the confounding calibration evidence synthesis."""
    from scipy import stats

    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Left panel: Evidence sources
    ax1 = axes[0]

    sources = ['LDL Pathway\n(mechanism floor)', 'Sibling Studies\n(general dietary)',
               'Golestan Cohort\n(Iran, low confounding)']
    values = [0.12, 0.60, 1.0]  # Corrected interpretations
    weights = [0.2, 0.3, 0.5]
    colors = ['#3498DB', '#9B59B6', '#27AE60']

    bars = ax1.barh(sources, values, color=colors, alpha=0.7, edgecolor='black')

    ax1.set_xlabel('Implied Causal Fraction', fontsize=11)
    ax1.set_title('Evidence Sources for Causal Fraction', fontsize=12, fontweight='bold')
    ax1.set_xlim(0, 1.2)
    ax1.axvline(0.5, color='red', linestyle='--', linewidth=2, label='Prior mean (0.50)')

    # Add value labels
    for bar, val in zip(bars, values):
        ax1.text(val + 0.03, bar.get_y() + bar.get_height()/2,
                f'{val:.0%}', va='center', fontsize=10)

    ax1.legend(loc='lower right')
    ax1.spines['top'].set_visible(False)
    ax1.spines['right'].set_visible(False)

    # Right panel: Prior distribution
    ax2 = axes[1]

    x = np.linspace(0, 1, 200)
    prior = stats.beta(2.5, 2.5)

    ax2.fill_between(x, prior.pdf(x), alpha=0.3, color=COLORS['primary'])
    ax2.plot(x, prior.pdf(x), color=COLORS['primary'], linewidth=2, label='Beta(2.5, 2.5)')

    # Mark key values
    ax2.axvline(0.5, color='red', linestyle='--', linewidth=2, label='Mean = 0.50')
    ax2.axvline(0.12, color='gray', linestyle=':', linewidth=1.5)
    ax2.axvline(0.88, color='gray', linestyle=':', linewidth=1.5)

    ax2.fill_between(x[(x >= 0.12) & (x <= 0.88)],
                     prior.pdf(x[(x >= 0.12) & (x <= 0.88)]),
                     alpha=0.2, color='green', label='95% CI: [0.12, 0.88]')

    ax2.set_xlabel('Causal Fraction', fontsize=11)
    ax2.set_ylabel('Density', fontsize=11)
    ax2.set_title('Prior Distribution for Causal Fraction', fontsize=12, fontweight='bold')
    ax2.legend(loc='upper right', fontsize=9)
    ax2.set_xlim(0, 1)
    ax2.spines['top'].set_visible(False)
    ax2.spines['right'].set_visible(False)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'confounding_calibration.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'confounding_calibration.png'


def fig6_nutrient_contributions():
    """Heatmap showing nutrient contributions to each nut's effect."""
    from whatnut.bayesian_model import load_extended_nut_nutrients, PATHWAY_NUTRIENT_PRIORS

    nuts = ['walnut', 'almond', 'peanut', 'cashew', 'pistachio', 'macadamia', 'pecan']
    nutrients_data = load_extended_nut_nutrients()

    # Key nutrients
    key_nutrients = ['ala_omega3', 'fiber', 'magnesium', 'omega7', 'vitamin_e', 'protein']
    nutrient_labels = ['ALA Omega-3', 'Fiber', 'Magnesium', 'Omega-7', 'Vitamin E', 'Protein']

    # Calculate contribution to CVD effect (the dominant pathway)
    contributions = np.zeros((len(nuts), len(key_nutrients)))

    for i, nut in enumerate(nuts):
        for j, nutrient in enumerate(key_nutrients):
            amount = nutrients_data[nut].get(nutrient, 0)
            effect = PATHWAY_NUTRIENT_PRIORS['cvd'][nutrient]['mean']
            contributions[i, j] = -amount * effect * 100  # Convert to % reduction contribution

    fig, ax = plt.subplots(figsize=(10, 6))

    im = ax.imshow(contributions, cmap='RdYlGn', aspect='auto', vmin=-1, vmax=15)

    ax.set_xticks(np.arange(len(key_nutrients)))
    ax.set_yticks(np.arange(len(nuts)))
    ax.set_xticklabels(nutrient_labels, fontsize=10, rotation=45, ha='right')
    ax.set_yticklabels([n.title() for n in nuts], fontsize=10)

    # Add value annotations
    for i in range(len(nuts)):
        for j in range(len(key_nutrients)):
            val = contributions[i, j]
            color = 'white' if val > 7 else 'black'
            ax.text(j, i, f'{val:.1f}', ha='center', va='center', fontsize=9, color=color)

    ax.set_title('Nutrient Contributions to CVD Mortality Reduction (%)',
                 fontsize=14, fontweight='bold')

    cbar = plt.colorbar(im, ax=ax, shrink=0.8)
    cbar.set_label('Contribution to CVD Reduction (%)', fontsize=10)

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'nutrient_contributions.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'nutrient_contributions.png'


def fig7_icer_comparison():
    """Bar chart comparing ICERs to cost-effectiveness thresholds."""
    from whatnut.paper_results import r

    nuts_sorted = sorted(r.nuts.values(), key=lambda x: x.icer)

    fig, ax = plt.subplots(figsize=(10, 6))

    x = np.arange(len(nuts_sorted))
    icers = [n.icer for n in nuts_sorted]

    bars = ax.bar(x, icers, color=[COLORS['nuts'].get(n.name.lower(), '#888')
                                    for n in nuts_sorted], alpha=0.85, edgecolor='black')

    # Threshold lines
    ax.axhline(r.icer_threshold, color='red', linestyle='--', linewidth=2,
               label=f'ICER threshold (${r.icer_threshold:,}/QALY)')
    ax.axhline(r.nice_lower_usd, color='orange', linestyle='--', linewidth=2,
               label=f'NICE threshold (${r.nice_lower_usd:,}/QALY)')

    ax.set_xticks(x)
    ax.set_xticklabels([n.name for n in nuts_sorted], fontsize=10)
    ax.set_ylabel('ICER ($/QALY)', fontsize=12)
    ax.set_title('Cost-Effectiveness by Nut Type', fontsize=14, fontweight='bold')
    ax.legend(loc='upper left', fontsize=9)

    # Value labels
    for bar, val in zip(bars, icers):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 500,
               f'${val:,}', ha='center', fontsize=9)

    ax.set_ylim(0, 60000)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    # Annotation
    ax.text(0.98, 0.15, 'All nuts are\ncost-effective\n(below thresholds)',
            transform=ax.transAxes, fontsize=10, ha='right', va='bottom',
            bbox=dict(boxstyle='round', facecolor='lightgreen', alpha=0.5))

    plt.tight_layout()
    ensure_figure_dir()
    fig.savefig(FIGURE_DIR / 'icer_comparison.png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    return FIGURE_DIR / 'icer_comparison.png'


def generate_all_figures():
    """Generate all figures for the paper."""
    print("Generating figures...")

    figures = {}

    print("  1. Model architecture diagram...")
    figures['architecture'] = fig1_model_architecture()

    print("  2. Pathway-specific RRs...")
    figures['pathway_rrs'] = fig2_pathway_rrs()

    print("  3. Forest plot of life years...")
    figures['forest'] = fig3_forest_plot()

    print("  4. Age-varying cause fractions...")
    figures['cause_fractions'] = fig4_cause_fractions()

    print("  5. Confounding calibration...")
    figures['confounding'] = fig5_confounding_calibration()

    print("  6. Nutrient contributions heatmap...")
    figures['nutrients'] = fig6_nutrient_contributions()

    print("  7. ICER comparison...")
    figures['icer'] = fig7_icer_comparison()

    print(f"\nAll figures saved to {FIGURE_DIR}")
    return figures


if __name__ == '__main__':
    generate_all_figures()
