"""Hierarchical Bayesian model for nut-mortality effects.

This model uses nutrient-level priors from meta-analyses to inform
nut-specific effects, with RCT evidence updating the posteriors.

Key difference from lifecycle_pathways.py:
- Old: Sample independently from fixed distributions (Monte Carlo)
- New: Sample from joint posterior via MCMC (Bayesian inference)

Priors derived from:
- ALA (omega-3): Pan 2012, Naghshi 2021 meta-analyses
- Omega-6: Farvid 2014, Marklund 2019 meta-analyses
- Omega-7: Limited evidence, weak prior
- Vitamin E: Miller 2005 meta-analysis
"""

import numpy as np
from pathlib import Path
import yaml

# PyMC is optional - only needed for MCMC inference
try:
    import pymc as pm
    import arviz as az
    PYMC_AVAILABLE = True
except ImportError:
    PYMC_AVAILABLE = False
    pm = None
    az = None


# =============================================================================
# CALIBRATION CONSTANTS FROM META-ANALYSES
# =============================================================================

# CTT Collaboration (Lancet 2010, 2012) - LDL → CVD relationship
# 170,000 participants in 26 statin RCTs
CTT_CALIBRATION = {
    'rr_per_mmol_vascular': 0.78,     # Major vascular events
    'rr_per_mmol_mortality': 0.90,    # All-cause mortality
    'rr_per_mmol_chd_death': 0.80,    # CHD death specifically
    'mmol_per_mgdl': 1 / 38.67,       # Conversion factor
    'source': 'CTT Collaboration, Lancet 2010'
}

# Del Gobbo 2015 - Nut → LDL relationship (61 controlled trials)
NUT_LDL_EFFECT = {
    'ldl_reduction_mgdl': 4.8,  # Per serving (28g)
    'ldl_se': 1.5,
    'source': 'Del Gobbo 2015 AJCN'
}

# Derived: Expected CVD effect from LDL pathway alone
# 4.8 mg/dL = 0.124 mmol/L → RR = 0.78^0.124 = 0.97 → 3% reduction
LDL_PATHWAY_CVD_EFFECT = 0.03  # Only ~3% CVD reduction mechanistically explained

# Nutrient priors from meta-analyses (effect per unit, log-RR scale)
# These are the key innovation: mechanistic priors from independent literature

NUTRIENT_PRIORS = {
    # ALA omega-3: ~5% mortality reduction per g/day
    # Source: Naghshi 2021 BMJ (RR 0.90, 95% CI 0.83-0.97 for high vs low)
    # High intake median 1.59g vs low 0.73g → 0.86g difference
    # 10% reduction / 0.86g ≈ 12% per gram
    'ala_omega3': {
        'mean': -0.12,  # log-RR per gram (strong effect)
        'sd': 0.04,
        'source': 'Naghshi 2021 BMJ: RR 0.90 for high vs low ALA'
    },

    # Omega-6 (linoleic acid): benefit, not harm
    # Source: 2025 global meta-analysis of 150 cohorts
    # Farvid 2014: 5% CHD reduction per 5% energy from LA
    # ~13g LA per 5% energy (2000 kcal diet) → ~0.4% per gram
    'omega6': {
        'mean': -0.004,  # log-RR per gram (weak benefit)
        'sd': 0.003,
        'source': '2025 global meta (150 cohorts), Farvid 2014'
    },

    # Omega-7 (palmitoleic acid): limited evidence, weak prior
    # No meta-analysis; animal studies show ~45% plaque reduction
    # Human observational: OR 0.47 for hypertension (top vs bottom quartile)
    'omega7': {
        'mean': -0.02,  # log-RR per gram
        'sd': 0.04,     # wide - limited human RCT evidence
        'source': 'Mechanistic + observational only'
    },

    # Vitamin E: null to slight benefit from food sources
    # Source: Dietary (not supplement) vitamin E associated with CVD benefit
    # ~10% reduction per 10mg in some studies
    'vitamin_e': {
        'mean': -0.01,  # log-RR per mg
        'sd': 0.008,
        'source': 'Dietary vitamin E studies (not supplements)'
    },

    # Fiber: consistent CVD benefit
    # Source: Threapleton 2013 BMJ
    # RR 0.91 per 7g/day → log(0.91)/7 = -0.0135 per gram
    'fiber': {
        'mean': -0.0135,  # log-RR per gram
        'sd': 0.004,
        'source': 'Threapleton 2013 BMJ: RR 0.91 per 7g/day'
    },

    # Saturated fat: modest harm
    # Source: Sacks 2017 AHA - replacing SFA with PUFA reduces CHD
    # ~25% reduction when replacing 5% energy SFA with PUFA
    # 5% energy ≈ 11g SFA → ~2% harm per gram
    'saturated_fat': {
        'mean': 0.02,   # log-RR per gram (harmful)
        'sd': 0.01,
        'source': 'Sacks 2017 AHA advisory'
    },
}


# RCT evidence for nut-specific effects (used as likelihood)
# Format: (observed effect size, standard error)
RCT_EVIDENCE = {
    'walnut': {
        'ldl_reduction_mgdl': (4.3, 1.5),  # WAHA trial
        'source': 'Rajaram 2021 WAHA'
    },
    'almond': {
        'ldl_reduction_mgdl': (5.3, 1.2),  # Multiple RCTs pooled
        'source': 'Musa-Veloso 2016 meta'
    },
    'pistachio': {
        'ldl_reduction_mgdl': (6.1, 2.0),  # Del Gobbo 2015
        'source': 'Del Gobbo 2015'
    },
    'peanut': {
        'ldl_reduction_mgdl': (3.8, 1.8),  # Bao cohort implied
        'source': 'Bao 2013 cohort'
    },
    'cashew': {
        'ldl_reduction_mgdl': (3.9, 3.5),  # Mah 2017 (wide CI!)
        'source': 'Mah 2017'
    },
    # Pecan, macadamia: limited RCT data → rely more on priors
}


def load_nut_nutrients() -> dict:
    """Load nutrient data from YAML."""
    data_path = Path(__file__).parent / 'data' / 'nuts.yaml'
    with open(data_path) as f:
        data = yaml.safe_load(f)

    nutrients = {}
    for nut, info in data.items():
        n = info['nutrients']
        nutrients[nut] = {
            'ala_omega3': n.get('omega3_ala_g', 0),
            'omega6': n.get('polyunsaturated_fat_g', 0) - n.get('omega3_ala_g', 0),
            'omega7': n.get('omega7_g', 0),
            'vitamin_e': n.get('vitamin_e_mg', 0),
            'fiber': n.get('fiber_g', 0),
            'saturated_fat': n.get('saturated_fat_g', 0),
        }
    return nutrients


def build_hierarchical_model(nuts: list[str] = None):
    """Build PyMC hierarchical model for nut effects.

    Requires PyMC to be installed: pip install pymc arviz

    Model structure:
    1. Nutrient-level effects (beta_ala, beta_omega6, etc.)
       - Priors from meta-analyses

    2. Nut-specific expected effects (derived from composition)
       - expected_effect[nut] = sum(beta_nutrient * nutrient_amount[nut])

    3. Nut-specific true effects (allow deviation from expected)
       - true_effect[nut] ~ Normal(expected_effect[nut], tau)
       - tau captures nut-specific factors not in nutrients

    4. RCT likelihood (where available)
       - observed_ldl[nut] ~ Normal(true_effect[nut] * ldl_conversion, rct_se)

    5. Confounding adjustment (shared across nuts)
       - causal_fraction ~ Beta(1.5, 4.5)
    """
    if not PYMC_AVAILABLE:
        raise ImportError("PyMC is required for MCMC inference. "
                         "Install with: pip install pymc arviz")

    if nuts is None:
        nuts = ['walnut', 'almond', 'pistachio', 'pecan',
                'macadamia', 'peanut', 'cashew']

    nutrients = load_nut_nutrients()
    n_nuts = len(nuts)

    with pm.Model() as model:
        # --- Nutrient-level priors ---
        beta_ala = pm.Normal('beta_ala',
                            mu=NUTRIENT_PRIORS['ala_omega3']['mean'],
                            sigma=NUTRIENT_PRIORS['ala_omega3']['sd'])

        beta_omega6 = pm.Normal('beta_omega6',
                               mu=NUTRIENT_PRIORS['omega6']['mean'],
                               sigma=NUTRIENT_PRIORS['omega6']['sd'])

        beta_omega7 = pm.Normal('beta_omega7',
                               mu=NUTRIENT_PRIORS['omega7']['mean'],
                               sigma=NUTRIENT_PRIORS['omega7']['sd'])

        beta_vite = pm.Normal('beta_vitamin_e',
                             mu=NUTRIENT_PRIORS['vitamin_e']['mean'],
                             sigma=NUTRIENT_PRIORS['vitamin_e']['sd'])

        beta_fiber = pm.Normal('beta_fiber',
                              mu=NUTRIENT_PRIORS['fiber']['mean'],
                              sigma=NUTRIENT_PRIORS['fiber']['sd'])

        beta_satfat = pm.Normal('beta_saturated_fat',
                               mu=NUTRIENT_PRIORS['saturated_fat']['mean'],
                               sigma=NUTRIENT_PRIORS['saturated_fat']['sd'])

        # --- Compute expected effects from composition ---
        expected_effects = []
        for nut in nuts:
            n = nutrients[nut]
            expected = (
                beta_ala * n['ala_omega3'] +
                beta_omega6 * n['omega6'] +
                beta_omega7 * n['omega7'] +
                beta_vite * n['vitamin_e'] +
                beta_fiber * n['fiber'] +
                beta_satfat * n['saturated_fat']
            )
            expected_effects.append(expected)

        expected_effects = pm.math.stack(expected_effects)

        # --- Hierarchical shrinkage ---
        # Allow nut-specific deviations from nutrient-predicted effects
        tau = pm.HalfNormal('tau', sigma=0.05)  # Shrinkage toward expected

        true_effects = pm.Normal('true_effect',
                                mu=expected_effects,
                                sigma=tau,
                                shape=n_nuts)

        # --- RCT likelihood (LDL as proxy for CVD effect) ---
        # Convert log-RR to expected LDL reduction
        # Rough: 1% CVD reduction ≈ 1 mg/dL LDL reduction (from CTT)
        ldl_conversion = 100  # log-RR of -0.01 → ~1 mg/dL LDL reduction

        for i, nut in enumerate(nuts):
            if nut in RCT_EVIDENCE:
                obs_ldl, obs_se = RCT_EVIDENCE[nut]['ldl_reduction_mgdl']
                expected_ldl = -true_effects[i] * ldl_conversion
                pm.Normal(f'ldl_obs_{nut}',
                         mu=expected_ldl,
                         sigma=obs_se,
                         observed=obs_ldl)

        # --- Confounding adjustment ---
        causal_fraction = pm.Beta('causal_fraction', alpha=1.5, beta=4.5)

        # --- Final causal effects ---
        causal_effects = pm.Deterministic(
            'causal_effect',
            true_effects * causal_fraction
        )

        # --- Convert to relative risk ---
        # RR = exp(log_rr) where log_rr is causal_effect
        relative_risks = pm.Deterministic(
            'relative_risk',
            pm.math.exp(causal_effects)
        )

    return model, nuts


def run_inference(model, draws=2000, tune=1000, chains=4, seed=42):
    """Run MCMC inference using NUTS sampler."""
    with model:
        trace = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=seed,
            return_inferencedata=True,
            target_accept=0.9,
        )
    return trace


def summarize_results(trace, nuts):
    """Summarize posterior estimates for each nut."""
    summary = az.summary(trace, var_names=['relative_risk', 'causal_fraction'])

    print("=== Hierarchical Bayesian Model Results ===\n")

    print("Nutrient effects (log-RR per unit):")
    nutrient_summary = az.summary(trace, var_names=[
        'beta_ala', 'beta_omega6', 'beta_omega7',
        'beta_vitamin_e', 'beta_fiber', 'beta_saturated_fat'
    ])
    print(nutrient_summary[['mean', 'sd', 'hdi_3%', 'hdi_97%']])

    print("\nCausal fraction:")
    cf = trace.posterior['causal_fraction'].values.flatten()
    print(f"  Mean: {np.mean(cf):.2%}")
    print(f"  95% CI: [{np.percentile(cf, 2.5):.2%}, {np.percentile(cf, 97.5):.2%}]")

    print("\nNut-specific relative risks (causal, mortality):")
    rr = trace.posterior['relative_risk'].values
    for i, nut in enumerate(nuts):
        rr_nut = rr[:, :, i].flatten()
        print(f"  {nut:12s}: {np.mean(rr_nut):.3f} "
              f"[{np.percentile(rr_nut, 2.5):.3f}, {np.percentile(rr_nut, 97.5):.3f}]")

    return summary


def run_full_monte_carlo(trace, nuts, n_samples=1000):
    """Run full lifecycle Monte Carlo using MCMC posterior samples.

    This connects the Bayesian posterior to the lifecycle CEA model
    to produce QALY distributions.
    """
    from whatnut.lifecycle_pathways import PathwayLifecycleCEA, PathwayParams, get_nut_cost

    # Extract posterior samples
    rr_samples = trace.posterior['relative_risk'].values  # shape: (chains, draws, nuts)
    n_chains, n_draws, n_nuts = rr_samples.shape

    # Flatten chains
    rr_flat = rr_samples.reshape(-1, n_nuts)  # shape: (chains*draws, nuts)

    # Subsample if needed
    if len(rr_flat) > n_samples:
        indices = np.random.choice(len(rr_flat), n_samples, replace=False)
        rr_flat = rr_flat[indices]

    print(f"=== Full Lifecycle Monte Carlo ({len(rr_flat)} samples) ===\n")

    results = {nut: {'qalys': [], 'icers': [], 'life_years': []} for nut in nuts}

    model = PathwayLifecycleCEA(seed=42)

    for i, rr_sample in enumerate(rr_flat):
        for j, nut in enumerate(nuts):
            # Convert RR to pathway-specific effects
            # The MCMC gives us overall causal RR, need to map to pathways
            # For now, apply uniformly to all pathways
            rr = rr_sample[j]

            # Convert RR to adjustment factor relative to base HR
            # If base CVD RR is 0.75 and we want overall RR of 0.988,
            # we need to find what adjustment makes it work
            # Simplified: just use the RR directly as the mortality effect

            params = PathwayParams(
                start_age=40,
                max_age=110,
                discount_rate=0.03,
                # Apply the sampled RR as a uniform effect
                rr_cvd=rr,
                rr_cancer=rr,  # Simplified - should be pathway-specific
                rr_other=rr,
                confounding_adjustment=1.0,  # Already applied in MCMC
                annual_cost=get_nut_cost(nut),
                # No additional nut adjustments - already in RR
                nut_adj_cvd=1.0,
                nut_adj_cancer=1.0,
                nut_adj_other=1.0,
            )

            result = model.run(params)
            results[nut]['qalys'].append(result.qalys_gained_discounted)
            results[nut]['icers'].append(result.cost_per_qaly)
            results[nut]['life_years'].append(result.life_years_gained)

    # Summarize results
    print("Nut-specific QALY estimates (discounted at 3%):\n")
    print(f"{'Nut':12s} {'Mean QALY':>12s} {'Median':>10s} {'95% CI':>20s} {'ICER':>15s}")
    print("-" * 75)

    summary = {}
    for nut in nuts:
        qalys = np.array(results[nut]['qalys'])
        icers = np.array(results[nut]['icers'])
        icers_finite = icers[np.isfinite(icers)]

        summary[nut] = {
            'qaly_mean': np.mean(qalys),
            'qaly_median': np.median(qalys),
            'qaly_ci': (np.percentile(qalys, 2.5), np.percentile(qalys, 97.5)),
            'icer_median': np.median(icers_finite) if len(icers_finite) > 0 else float('inf'),
            'life_years_mean': np.mean(results[nut]['life_years']),
        }

        s = summary[nut]
        ci_str = f"[{s['qaly_ci'][0]:.3f}, {s['qaly_ci'][1]:.3f}]"
        print(f"{nut:12s} {s['qaly_mean']:12.4f} {s['qaly_median']:10.4f} {ci_str:>20s} ${s['icer_median']:>13,.0f}")

    print("\n" + "=" * 75)
    print("Comparison with current model (from paper):\n")
    print(f"{'Nut':12s} {'Bayesian QALY':>15s} {'Current QALY':>15s} {'Difference':>15s}")
    print("-" * 60)

    current_qalys = {
        'walnut': 0.10, 'almond': 0.09, 'pistachio': 0.10,
        'pecan': 0.09, 'macadamia': 0.09, 'peanut': 0.09, 'cashew': 0.09
    }

    for nut in nuts:
        bayesian = summary[nut]['qaly_mean']
        current = current_qalys.get(nut, 0.09)
        diff = bayesian - current
        pct = (diff / current) * 100 if current > 0 else 0
        print(f"{nut:12s} {bayesian:15.4f} {current:15.2f} {diff:+15.4f} ({pct:+.0f}%)")

    return summary, results


def compute_nutrient_based_effects():
    """Compute expected effects from nutrient composition alone.

    This shows what the model would predict WITHOUT any nut-specific
    RCT evidence - purely from nutrient meta-analyses.
    """
    nutrients = load_nut_nutrients()

    print("=== Nutrient-Based Effect Predictions ===")
    print("(Before incorporating nut-specific RCT evidence)\n")

    print("Nutrient content per 28g serving:")
    print("-" * 80)
    header = f"{'Nut':12s} {'ALA(g)':>8s} {'ω6(g)':>8s} {'ω7(g)':>8s} {'VitE(mg)':>10s} {'Fiber(g)':>10s} {'SatFat(g)':>10s}"
    print(header)
    print("-" * 80)

    for nut in nutrients:
        n = nutrients[nut]
        print(f"{nut:12s} {n['ala_omega3']:8.2f} {n['omega6']:8.2f} {n['omega7']:8.2f} "
              f"{n['vitamin_e']:10.1f} {n['fiber']:10.1f} {n['saturated_fat']:10.1f}")

    print("\n" + "=" * 80)
    print("Expected log-RR from each nutrient pathway:")
    print("-" * 80)

    results = {}
    for nut in nutrients:
        n = nutrients[nut]
        effects = {
            'ala': NUTRIENT_PRIORS['ala_omega3']['mean'] * n['ala_omega3'],
            'omega6': NUTRIENT_PRIORS['omega6']['mean'] * n['omega6'],
            'omega7': NUTRIENT_PRIORS['omega7']['mean'] * n['omega7'],
            'vit_e': NUTRIENT_PRIORS['vitamin_e']['mean'] * n['vitamin_e'],
            'fiber': NUTRIENT_PRIORS['fiber']['mean'] * n['fiber'],
            'sat_fat': NUTRIENT_PRIORS['saturated_fat']['mean'] * n['saturated_fat'],
        }
        effects['total'] = sum(effects.values())
        effects['rr'] = np.exp(effects['total'])
        results[nut] = effects

    header = f"{'Nut':12s} {'ALA':>8s} {'ω6':>8s} {'ω7':>8s} {'VitE':>8s} {'Fiber':>8s} {'SatFat':>8s} {'Total':>8s} {'RR':>8s}"
    print(header)
    print("-" * 80)

    for nut, e in results.items():
        print(f"{nut:12s} {e['ala']:8.3f} {e['omega6']:8.3f} {e['omega7']:8.3f} "
              f"{e['vit_e']:8.3f} {e['fiber']:8.3f} {e['sat_fat']:8.3f} "
              f"{e['total']:8.3f} {e['rr']:8.3f}")

    print("\n" + "=" * 80)
    print("Comparison: Nutrient-predicted vs Current model vs LDL-calibrated")
    print("-" * 80)
    print(f"{'Nut':12s} {'Nutrient RR':>12s} {'Current RR':>12s} {'LDL-only RR':>12s}")
    print("-" * 80)

    # Current model uses fixed adjustment factors
    current_adjustments = {
        'walnut': 0.78 ** 1.25,
        'almond': 0.78 ** 1.00,
        'pistachio': 0.78 ** 1.12,
        'pecan': 0.78 ** 1.08,
        'macadamia': 0.78 ** 1.08,
        'peanut': 0.78 ** 0.98,
        'cashew': 0.78 ** 0.95,
    }

    # LDL-calibrated: only count the mechanistically-explained portion
    ldl_only_rr = 1 - LDL_PATHWAY_CVD_EFFECT  # ~0.97

    for nut in results:
        nutrient_rr = results[nut]['rr']
        current_rr = current_adjustments.get(nut, 0.78)
        print(f"{nut:12s} {nutrient_rr:12.3f} {current_rr:12.3f} {ldl_only_rr:12.3f}")

    print("\n" + "=" * 80)
    print("KEY INSIGHT:")
    print("-" * 80)
    print("The nutrient-based model predicts LARGER effects for walnuts due to ALA,")
    print("but SMALLER effects for most other nuts compared to the current model.")
    print(f"\nWalnuts: {results['walnut']['ala']:.3f} log-RR from ALA alone")
    print(f"         = {np.exp(results['walnut']['ala']):.3f} RR")
    print(f"\nThis is {abs(results['walnut']['ala'] / results['walnut']['total']) * 100:.0f}% of walnut's total predicted effect")
    print("\nThe omega-7 effect (macadamias) is uncertain due to limited evidence.")

    return results


if __name__ == '__main__':
    # First show nutrient-based predictions
    compute_nutrient_based_effects()

    print("\n\n")
    print("=" * 80)
    print("RUNNING HIERARCHICAL BAYESIAN MODEL")
    print("=" * 80)

    try:
        print("\nBuilding hierarchical model...")
        model, nuts = build_hierarchical_model()

        print("Running MCMC inference (this may take a few minutes)...")
        trace = run_inference(model, draws=1000, tune=500, chains=2)

        summarize_results(trace, nuts)
    except ImportError as e:
        print(f"\nPyMC not installed. Install with: pip install pymc arviz")
        print(f"Error: {e}")
