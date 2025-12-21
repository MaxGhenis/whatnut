"""Hierarchical Bayesian model v2: Pathway-specific effects.

Key improvements over v1:
1. Pathway-specific nutrient effects (CVD, cancer, other)
2. More nutrients (magnesium, arginine, phytosterols, protein)
3. Non-centered parameterization (fixes divergences)
4. Quality/morbidity effects (not just mortality)

Model structure:
    For each pathway p ∈ {CVD, cancer, other}:
        β_nutrient[p] ~ Normal(μ_nutrient[p], σ_nutrient[p])  # pathway-specific

    For each nut n:
        expected_effect[n, p] = Σ(β_nutrient[p] × nutrient[n])

        # Non-centered parameterization for hierarchical shrinkage
        z[n, p] ~ Normal(0, 1)
        true_effect[n, p] = expected_effect[n, p] + τ[p] × z[n, p]

    Quality adjustment:
        quality_effect[n] = f(fiber, magnesium, protein)  # morbidity pathway

    Total QALY effect combines mortality and quality pathways.
"""

import numpy as np
from pathlib import Path
import yaml
from dataclasses import dataclass

try:
    import pymc as pm
    import arviz as az
    PYMC_AVAILABLE = True
except ImportError:
    PYMC_AVAILABLE = False
    pm = None
    az = None


# =============================================================================
# PATHWAY-SPECIFIC NUTRIENT PRIORS
# =============================================================================

# Priors are specified as (mean, sd) for log-RR per unit
# Organized by pathway for clarity

PATHWAY_NUTRIENT_PRIORS = {
    'cvd': {
        # Strong effects on CVD
        'ala_omega3': {'mean': -0.15, 'sd': 0.05, 'unit': 'g',
                       'source': 'Naghshi 2021: strong CVD effect'},
        'omega6': {'mean': -0.005, 'sd': 0.003, 'unit': 'g',
                   'source': 'Farvid 2014: CHD benefit'},
        'omega7': {'mean': -0.03, 'sd': 0.04, 'unit': 'g',
                   'source': 'Palmitoleic acid, insulin sensitivity'},
        'fiber': {'mean': -0.015, 'sd': 0.005, 'unit': 'g',
                  'source': 'Threapleton 2013: RR 0.91/7g for CVD'},
        'saturated_fat': {'mean': 0.025, 'sd': 0.01, 'unit': 'g',
                          'source': 'Sacks 2017: LDL/CHD pathway'},
        'magnesium': {'mean': -0.003, 'sd': 0.001, 'unit': 'mg',
                      'source': 'Fang 2016: RR 0.90 per 100mg for CHD'},
        'arginine': {'mean': -0.02, 'sd': 0.02, 'unit': 'g',
                     'source': 'Vasodilation, limited RCT evidence'},
        'vitamin_e': {'mean': -0.005, 'sd': 0.008, 'unit': 'mg',
                      'source': 'Food-based, not supplement'},
        'phytosterols': {'mean': -0.01, 'sd': 0.01, 'unit': 'mg',
                         'source': 'LDL lowering mechanism'},
        'protein': {'mean': 0.0, 'sd': 0.005, 'unit': 'g',
                    'source': 'Neutral for CVD'},
    },
    'cancer': {
        # Different profile for cancer
        'ala_omega3': {'mean': -0.02, 'sd': 0.03, 'unit': 'g',
                       'source': 'Naghshi 2021: weaker for cancer'},
        'omega6': {'mean': 0.002, 'sd': 0.005, 'unit': 'g',
                   'source': 'Mixed evidence, possible inflammation'},
        'omega7': {'mean': 0.0, 'sd': 0.02, 'unit': 'g',
                   'source': 'No known cancer mechanism'},
        'fiber': {'mean': -0.01, 'sd': 0.004, 'unit': 'g',
                  'source': 'Colorectal cancer protection'},
        'saturated_fat': {'mean': 0.005, 'sd': 0.008, 'unit': 'g',
                          'source': 'Weak cancer association'},
        'magnesium': {'mean': -0.001, 'sd': 0.002, 'unit': 'mg',
                      'source': 'Limited cancer evidence'},
        'arginine': {'mean': 0.0, 'sd': 0.01, 'unit': 'g',
                     'source': 'Neutral'},
        'vitamin_e': {'mean': -0.008, 'sd': 0.01, 'unit': 'mg',
                      'source': 'Antioxidant, mixed evidence'},
        'phytosterols': {'mean': 0.0, 'sd': 0.005, 'unit': 'mg',
                         'source': 'No cancer mechanism'},
        'protein': {'mean': 0.0, 'sd': 0.003, 'unit': 'g',
                    'source': 'Neutral'},
    },
    'other': {
        # Respiratory, diabetes, other causes
        'ala_omega3': {'mean': -0.05, 'sd': 0.04, 'unit': 'g',
                       'source': 'Anti-inflammatory'},
        'omega6': {'mean': -0.002, 'sd': 0.003, 'unit': 'g',
                   'source': 'Weak effect'},
        'omega7': {'mean': -0.02, 'sd': 0.03, 'unit': 'g',
                   'source': 'Insulin sensitivity → diabetes'},
        'fiber': {'mean': -0.012, 'sd': 0.005, 'unit': 'g',
                  'source': 'Glycemic control'},
        'saturated_fat': {'mean': 0.01, 'sd': 0.01, 'unit': 'g',
                          'source': 'Metabolic effects'},
        'magnesium': {'mean': -0.002, 'sd': 0.001, 'unit': 'mg',
                      'source': 'Diabetes prevention'},
        'arginine': {'mean': -0.01, 'sd': 0.02, 'unit': 'g',
                     'source': 'Immune function'},
        'vitamin_e': {'mean': -0.003, 'sd': 0.005, 'unit': 'mg',
                      'source': 'Antioxidant'},
        'phytosterols': {'mean': 0.0, 'sd': 0.003, 'unit': 'mg',
                         'source': 'No mechanism'},
        'protein': {'mean': -0.005, 'sd': 0.005, 'unit': 'g',
                    'source': 'Muscle maintenance in elderly'},
    },
    'quality': {
        # Effects on quality of life (morbidity, not mortality)
        'ala_omega3': {'mean': -0.02, 'sd': 0.02, 'unit': 'g',
                       'source': 'Anti-inflammatory, mood'},
        'omega6': {'mean': 0.0, 'sd': 0.002, 'unit': 'g',
                   'source': 'Neutral'},
        'omega7': {'mean': -0.01, 'sd': 0.02, 'unit': 'g',
                   'source': 'Skin health, metabolism'},
        'fiber': {'mean': -0.008, 'sd': 0.004, 'unit': 'g',
                  'source': 'Gut health, satiety'},
        'saturated_fat': {'mean': 0.005, 'sd': 0.005, 'unit': 'g',
                          'source': 'Slight negative'},
        'magnesium': {'mean': -0.002, 'sd': 0.001, 'unit': 'mg',
                      'source': 'Muscle/nerve function'},
        'arginine': {'mean': -0.01, 'sd': 0.01, 'unit': 'g',
                     'source': 'Exercise performance'},
        'vitamin_e': {'mean': -0.002, 'sd': 0.003, 'unit': 'mg',
                      'source': 'Skin, immune'},
        'phytosterols': {'mean': 0.0, 'sd': 0.002, 'unit': 'mg',
                         'source': 'No quality mechanism'},
        'protein': {'mean': -0.008, 'sd': 0.005, 'unit': 'g',
                    'source': 'Satiety, muscle maintenance'},
    },
}

NUTRIENTS = ['ala_omega3', 'omega6', 'omega7', 'fiber', 'saturated_fat',
             'magnesium', 'arginine', 'vitamin_e', 'phytosterols', 'protein']

PATHWAYS = ['cvd', 'cancer', 'other', 'quality']


# =============================================================================
# NUTRIENT DATA
# =============================================================================

def load_extended_nut_nutrients() -> dict:
    """Load nutrient data including new nutrients.

    Adds: magnesium, arginine, phytosterols, protein
    Source: USDA FoodData Central
    """
    # Base nutrients from YAML
    data_path = Path(__file__).parent / 'data' / 'nuts.yaml'
    with open(data_path) as f:
        data = yaml.safe_load(f)

    # Extended nutrient data per 28g serving
    # Source: USDA FoodData Central (FDC IDs in nuts.yaml)
    extended = {
        'walnut': {
            'magnesium': 44.2,      # mg
            'arginine': 0.64,       # g
            'phytosterols': 20,     # mg (approximate)
            'protein': 4.3,         # g (from YAML)
        },
        'almond': {
            'magnesium': 76.5,      # Highest magnesium
            'arginine': 0.74,
            'phytosterols': 35,     # Highest phytosterols
            'protein': 6.0,
        },
        'pistachio': {
            'magnesium': 33.6,
            'arginine': 0.60,
            'phytosterols': 61,
            'protein': 5.7,
        },
        'pecan': {
            'magnesium': 33.9,
            'arginine': 0.34,
            'phytosterols': 29,
            'protein': 2.6,
        },
        'macadamia': {
            'magnesium': 36.4,
            'arginine': 0.43,
            'phytosterols': 33,
            'protein': 2.2,
        },
        'peanut': {
            'magnesium': 47.6,
            'arginine': 0.93,       # Highest arginine
            'phytosterols': 62,
            'protein': 7.3,         # Highest protein
        },
        'cashew': {
            'magnesium': 82.8,      # Very high magnesium
            'arginine': 0.62,
            'phytosterols': 45,
            'protein': 5.2,
        },
    }

    nutrients = {}
    for nut, info in data.items():
        n = info['nutrients']
        nutrients[nut] = {
            'ala_omega3': n.get('omega3_ala_g', 0),
            'omega6': n.get('polyunsaturated_fat_g', 0) - n.get('omega3_ala_g', 0),
            'omega7': n.get('omega7_g', 0),
            'fiber': n.get('fiber_g', 0),
            'saturated_fat': n.get('saturated_fat_g', 0),
            'vitamin_e': n.get('vitamin_e_mg', 0),
            'magnesium': extended.get(nut, {}).get('magnesium', 40),
            'arginine': extended.get(nut, {}).get('arginine', 0.5),
            'phytosterols': extended.get(nut, {}).get('phytosterols', 30),
            'protein': extended.get(nut, {}).get('protein', 5),
        }
    return nutrients


# =============================================================================
# BAYESIAN MODEL
# =============================================================================

def build_pathway_model(nuts: list[str] = None):
    """Build hierarchical Bayesian model with pathway-specific effects.

    Uses non-centered parameterization to avoid divergences.
    """
    if not PYMC_AVAILABLE:
        raise ImportError("PyMC required: pip install pymc arviz")

    if nuts is None:
        nuts = ['walnut', 'almond', 'pistachio', 'pecan',
                'macadamia', 'peanut', 'cashew']

    nutrients_data = load_extended_nut_nutrients()
    n_nuts = len(nuts)
    n_pathways = len(PATHWAYS)
    n_nutrients = len(NUTRIENTS)

    # Build nutrient matrix: (nuts × nutrients)
    X = np.zeros((n_nuts, n_nutrients))
    for i, nut in enumerate(nuts):
        for j, nutrient in enumerate(NUTRIENTS):
            X[i, j] = nutrients_data[nut].get(nutrient, 0)

    with pm.Model() as model:
        # --- Pathway-specific nutrient effects ---
        # Shape: (pathways × nutrients)
        beta = {}
        for p, pathway in enumerate(PATHWAYS):
            pathway_betas = []
            for nutrient in NUTRIENTS:
                prior = PATHWAY_NUTRIENT_PRIORS[pathway][nutrient]
                beta_pn = pm.Normal(
                    f'beta_{pathway}_{nutrient}',
                    mu=prior['mean'],
                    sigma=prior['sd']
                )
                pathway_betas.append(beta_pn)
            beta[pathway] = pm.math.stack(pathway_betas)

        # --- Expected effects from nutrients ---
        # Shape: (nuts × pathways)
        expected = {}
        for pathway in PATHWAYS:
            # Matrix multiply: (nuts × nutrients) @ (nutrients,) → (nuts,)
            expected[pathway] = pm.math.dot(X, beta[pathway])

        # --- Hierarchical shrinkage (non-centered) ---
        # Each pathway has its own shrinkage parameter
        tau = {}
        z = {}
        true_effect = {}

        for pathway in PATHWAYS:
            tau[pathway] = pm.HalfNormal(f'tau_{pathway}', sigma=0.03)

            # Non-centered: z ~ N(0,1), then transform
            z[pathway] = pm.Normal(f'z_{pathway}', mu=0, sigma=1, shape=n_nuts)

            # True effect = expected + tau * z
            true_effect[pathway] = pm.Deterministic(
                f'effect_{pathway}',
                expected[pathway] + tau[pathway] * z[pathway]
            )

        # --- Confounding adjustment ---
        causal_frac = pm.Beta('causal_fraction', alpha=1.5, beta=4.5)

        # --- Causal effects by pathway ---
        causal_effect = {}
        for pathway in PATHWAYS:
            causal_effect[pathway] = pm.Deterministic(
                f'causal_{pathway}',
                true_effect[pathway] * causal_frac
            )

        # --- Convert to relative risks ---
        rr = {}
        for pathway in PATHWAYS:
            rr[pathway] = pm.Deterministic(
                f'rr_{pathway}',
                pm.math.exp(causal_effect[pathway])
            )

    return model, nuts, PATHWAYS


def run_pathway_inference(model, draws=2000, tune=1000, chains=4, seed=42):
    """Run MCMC with settings optimized for this model."""
    with model:
        trace = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            return_inferencedata=True,
            target_accept=0.95,  # Higher for complex model
            max_treedepth=12,
        )
    return trace


def get_mcmc_diagnostics(trace):
    """Extract MCMC convergence diagnostics.

    Returns dict with R-hat and ESS for key parameters.
    """
    summary = az.summary(trace, var_names=['causal_fraction', 'tau_cvd', 'tau_cancer',
                                            'tau_other', 'tau_quality'])

    diagnostics = {
        'divergences': int(trace.sample_stats['diverging'].values.sum()),
        'n_samples': int(trace.posterior.dims['chain'] * trace.posterior.dims['draw']),
        'n_chains': int(trace.posterior.dims['chain']),
        'rhat_max': float(summary['r_hat'].max()),
        'ess_bulk_min': float(summary['ess_bulk'].min()),
        'ess_tail_min': float(summary['ess_tail'].min()),
    }
    diagnostics['divergence_rate'] = diagnostics['divergences'] / diagnostics['n_samples']
    return diagnostics


def summarize_pathway_results(trace, nuts, pathways):
    """Summarize posterior for pathway-specific model."""
    print("=" * 80)
    print("PATHWAY-SPECIFIC BAYESIAN MODEL RESULTS")
    print("=" * 80)

    # MCMC Diagnostics
    diag = get_mcmc_diagnostics(trace)
    print("\n--- MCMC Diagnostics ---")
    print(f"Chains: {diag['n_chains']}, Samples per chain: {diag['n_samples'] // diag['n_chains']}")
    print(f"Divergences: {diag['divergences']}/{diag['n_samples']} ({diag['divergence_rate']:.1%})")
    print(f"R-hat (max): {diag['rhat_max']:.4f} {'✓' if diag['rhat_max'] < 1.01 else '⚠️ > 1.01'}")
    print(f"ESS bulk (min): {diag['ess_bulk_min']:.0f} {'✓' if diag['ess_bulk_min'] > 400 else '⚠️ < 400'}")
    print(f"ESS tail (min): {diag['ess_tail_min']:.0f} {'✓' if diag['ess_tail_min'] > 400 else '⚠️ < 400'}")

    # Causal fraction
    cf = trace.posterior['causal_fraction'].values.flatten()
    print(f"\nCausal fraction: {np.mean(cf):.1%} "
          f"[{np.percentile(cf, 2.5):.1%}, {np.percentile(cf, 97.5):.1%}]")

    # Relative risks by pathway
    print("\n" + "-" * 80)
    print("Relative Risks by Pathway (causal, after confounding adjustment)")
    print("-" * 80)

    for pathway in pathways:
        print(f"\n{pathway.upper()} pathway:")
        rr = trace.posterior[f'rr_{pathway}'].values
        for i, nut in enumerate(nuts):
            rr_nut = rr[:, :, i].flatten()
            print(f"  {nut:12s}: {np.mean(rr_nut):.4f} "
                  f"[{np.percentile(rr_nut, 2.5):.4f}, "
                  f"{np.percentile(rr_nut, 97.5):.4f}]")

    # Key nutrient effects
    print("\n" + "-" * 80)
    print("Key Nutrient Effects (posterior means)")
    print("-" * 80)

    key_nutrients = ['ala_omega3', 'fiber', 'omega7', 'magnesium', 'saturated_fat']
    print(f"\n{'Nutrient':15s} {'CVD':>10s} {'Cancer':>10s} {'Other':>10s} {'Quality':>10s}")
    print("-" * 55)

    for nutrient in key_nutrients:
        row = f"{nutrient:15s}"
        for pathway in pathways:
            beta_name = f'beta_{pathway}_{nutrient}'
            if beta_name in trace.posterior:
                val = trace.posterior[beta_name].values.flatten().mean()
                row += f" {val:10.4f}"
            else:
                row += f" {'N/A':>10s}"
        print(row)

    return trace


def run_full_lifecycle_mc(trace, nuts, pathways, n_samples=500, seed=42):
    """Run lifecycle Monte Carlo with pathway-specific effects.

    Args:
        trace: ArviZ InferenceData from MCMC
        nuts: List of nut names
        pathways: List of pathway names
        n_samples: Number of posterior samples to use
        seed: Random seed for reproducibility
    """
    from whatnut.lifecycle_pathways import PathwayLifecycleCEA, PathwayParams, get_nut_cost

    rng = np.random.default_rng(seed)

    # Extract posterior samples
    rr_cvd = trace.posterior['rr_cvd'].values.reshape(-1, len(nuts))
    rr_cancer = trace.posterior['rr_cancer'].values.reshape(-1, len(nuts))
    rr_other = trace.posterior['rr_other'].values.reshape(-1, len(nuts))
    rr_quality = trace.posterior['rr_quality'].values.reshape(-1, len(nuts))

    # Subsample with fixed seed
    n_total = len(rr_cvd)
    if n_total > n_samples:
        idx = rng.choice(n_total, n_samples, replace=False)
        rr_cvd = rr_cvd[idx]
        rr_cancer = rr_cancer[idx]
        rr_other = rr_other[idx]
        rr_quality = rr_quality[idx]

    print(f"\n{'=' * 80}")
    print(f"LIFECYCLE MONTE CARLO ({len(rr_cvd)} samples)")
    print("=" * 80)

    results = {nut: {'qalys': [], 'icers': [], 'life_years': []} for nut in nuts}
    model = PathwayLifecycleCEA(seed=42)

    for i in range(len(rr_cvd)):
        for j, nut in enumerate(nuts):
            # Use pathway-specific RRs
            params = PathwayParams(
                start_age=40,
                max_age=110,
                discount_rate=0.03,
                rr_cvd=rr_cvd[i, j],
                rr_cancer=rr_cancer[i, j],
                rr_other=rr_other[i, j],
                confounding_adjustment=1.0,  # Already in RRs
                annual_cost=get_nut_cost(nut),
                nut_adj_cvd=1.0,
                nut_adj_cancer=1.0,
                nut_adj_other=1.0,
            )

            result = model.run(params)

            # Apply quality adjustment
            # Quality pathway captures morbidity effects (fatigue, mood, etc.)
            # that improve quality weights but don't affect mortality.
            # The 0.5 scaling reflects that quality improvements are partial:
            # - Quality RR 0.95 → multiplier 1.025 (2.5% QALY boost)
            # - This is conservative; full utility gains would require
            #   integrating quality RR into the lifecycle quality weights
            quality_adj = rr_quality[i, j]
            quality_multiplier = 1 + (1 - quality_adj) * 0.5

            adjusted_qaly = result.qalys_gained_discounted * quality_multiplier

            results[nut]['qalys'].append(adjusted_qaly)
            results[nut]['icers'].append(result.cost_per_qaly)
            results[nut]['life_years'].append(result.life_years_gained)

    # Summary
    print(f"\n{'Nut':12s} {'Mean QALY':>10s} {'Median':>10s} {'95% CI':>22s} {'ICER':>12s}")
    print("-" * 70)

    summary = {}
    for nut in nuts:
        q = np.array(results[nut]['qalys'])
        icer = np.array(results[nut]['icers'])
        icer_finite = icer[np.isfinite(icer)]

        summary[nut] = {
            'qaly_mean': np.mean(q),
            'qaly_median': np.median(q),
            'qaly_ci': (np.percentile(q, 2.5), np.percentile(q, 97.5)),
            'icer_median': np.median(icer_finite) if len(icer_finite) > 0 else np.inf,
        }
        s = summary[nut]
        ci = f"[{s['qaly_ci'][0]:.4f}, {s['qaly_ci'][1]:.4f}]"
        print(f"{nut:12s} {s['qaly_mean']:10.4f} {s['qaly_median']:10.4f} {ci:>22s} ${s['icer_median']:>10,.0f}")

    return summary, results


if __name__ == '__main__':
    print("Building pathway-specific Bayesian model...")
    model, nuts, pathways = build_pathway_model()

    print("Running MCMC (this may take several minutes)...")
    trace = run_pathway_inference(model, draws=1500, tune=1000, chains=4)

    summarize_pathway_results(trace, nuts, pathways)
    run_full_lifecycle_mc(trace, nuts, pathways, n_samples=500)
