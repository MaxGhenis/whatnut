# Model Approaches: Incorporating Available Evidence

This document compares different approaches for modeling nut-mortality effects, ranked by increasing sophistication.

## Available Evidence Types

| Evidence Type | Example | Strength | Limitation |
|--------------|---------|----------|------------|
| Observational cohorts | Aune 2016 meta | Large N, mortality outcomes | Confounding |
| Feeding RCTs | Del Gobbo 2015 | Causal for biomarkers | No mortality outcomes |
| Nutrient meta-analyses | Naghshi 2021 (ALA) | Independent calibration | Not nut-specific |
| Cross-country comparisons | Golestan cohort | Natural experiment | Different populations |
| Sibling designs | UK Biobank | Controls shared confounders | Limited power |
| Mendelian randomization | Limited for nuts | Genetic instrument | Pleiotropy concerns |

## Approach 1: Current Model (Monte Carlo)

**How it works:**
- I read the literature and pick pathway adjustments (e.g., walnut CVD = 1.25)
- Sample independently from these fixed distributions
- No learning, no updating

**What it incorporates:**
- Observational cohort RRs ✓
- My judgment about RCT evidence ✓ (but subjectively)
- Confounding prior ✓

**What it misses:**
- Nutrient composition (stored but unused)
- Formal evidence synthesis
- Hierarchical structure

## Approach 2: Nutrient-Mechanistic Model

**How it works:**
```
nutrient_effects ~ priors from meta-analyses
expected_effect[nut] = Σ(nutrient_effect × nutrient_amount)
true_effect[nut] ~ Normal(expected_effect, tau)  # hierarchical
```

**What it incorporates:**
- Nutrient meta-analyses (ALA, omega-6, vitamin E, fiber) ✓
- Composition differences between nuts ✓
- Hierarchical shrinkage ✓

**What it misses:**
- Doesn't use nut-specific RCT evidence as likelihood
- Assumes additive nutrient effects (may not hold)
- Ignores nut-specific factors beyond measured nutrients

## Approach 3: Pathway-Calibrated Model

**How it works:**
```
# Calibrate CVD pathway from LDL RCTs
ldl_reduction[nut] ~ observed from RCTs
cvd_effect[nut] = f(ldl_reduction)  # via LDL→CVD relationship

# Calibrate cancer pathway from antioxidant evidence
antioxidant[nut] ~ from composition
cancer_effect[nut] = g(antioxidant, aflatoxin_risk)

# Other pathway: weak prior
other_effect[nut] ~ prior
```

**What it incorporates:**
- Pathway-specific calibration ✓
- RCT evidence on intermediate outcomes ✓
- Established biomarker→disease relationships ✓

**Key calibration data:**
- LDL → CVD: 22% CHD reduction per 1 mmol/L LDL (CTT Collaboration)
- 1 mmol/L ≈ 39 mg/dL
- Del Gobbo 2015: nuts reduce LDL by 4.8 mg/dL → ~3% CVD reduction

## Approach 4: Multi-Level Evidence Synthesis

**How it works:**
```
Level 1: Nutrients → Biomarkers
  ala[nut] → ldl_reduction[nut]
  omega6[nut] → inflammation[nut]

Level 2: Biomarkers → Disease Risk
  ldl_reduction → cvd_risk
  inflammation → cancer_risk

Level 3: Disease Risk → Mortality
  cvd_risk → cvd_mortality
  cancer_risk → cancer_mortality

Combine with pathway-specific cause fractions
```

**What it incorporates:**
- Full mechanistic chain ✓
- Uncertainty at each level ✓
- Can identify where uncertainty is largest ✓

**Challenge:**
- Many parameters to estimate
- Need data at each level
- Risk of compounding errors

## Approach 5: Evidence Triangulation

**How it works:**
- Treat each evidence source as independent estimate of causal effect
- Weight by inverse variance and bias risk
- Look for convergence across methods

```
Sources for "any nut" effect:
1. Observational (Aune 2016): RR 0.78 [confounded]
2. LDL-calibrated: RR 0.97 [pathway limited]
3. Sibling comparison: RR ~0.90 [underpowered]
4. Golestan (low confounding): RR 0.71 [single study]

Triangulated estimate: RR 0.90-0.95
```

## Recommended Hybrid Approach

Combine the best elements:

```python
with pm.Model():
    # 1. Nutrient priors from meta-analyses
    beta_ala = pm.Normal('beta_ala', mu=-0.05, sigma=0.02)
    # ... other nutrients

    # 2. Pathway-specific calibration
    # CVD: Use LDL pathway
    ldl_effect = pm.Normal('ldl_effect_per_unit',
                           mu=-0.22/39,  # CTT: 22% per mmol/L
                           sigma=0.03)

    for nut in nuts:
        # Expected LDL reduction from composition
        expected_ldl = f(nutrients[nut])

        # Observed LDL from RCTs (where available)
        if nut in rct_data:
            pm.Normal(f'ldl_obs_{nut}',
                     mu=expected_ldl,
                     sigma=rct_se[nut],
                     observed=rct_ldl[nut])

        # CVD effect via calibrated pathway
        cvd_effect[nut] = expected_ldl * ldl_effect

    # 3. Cancer pathway: antioxidant + aflatoxin
    # ... similar structure

    # 4. Confounding adjustment
    causal_frac = pm.Beta('causal_frac', 1.5, 4.5)

    # 5. Total mortality effect
    for nut in nuts:
        total_effect[nut] = (
            cvd_frac * cvd_effect[nut] +
            cancer_frac * cancer_effect[nut] +
            other_frac * other_effect[nut]
        ) * causal_frac
```

## What Changes in Results?

| Approach | Walnut RR | Macadamia RR | Key Driver |
|----------|-----------|--------------|------------|
| Current (MC) | 0.78^1.25 = 0.73 | 0.78^1.08 = 0.77 | My judgment |
| Nutrient-based | ~0.75 | ~0.78 | Omega-3 content |
| LDL-calibrated | ~0.96 | ~0.97 | LDL reduction only |
| Hybrid | ~0.92 | ~0.95 | Multiple pathways |

The LDL-calibrated approach gives much more modest estimates because it only counts the mechanistically-explained effect. The hybrid allows for effects beyond LDL while still being calibrated.

## Next Steps

1. Implement the hybrid model in PyMC
2. Extract specific effect sizes from meta-analyses:
   - ALA → mortality: Naghshi 2021
   - LDL → CVD: CTT Collaboration
   - Omega-6: Farvid 2014
3. Add RCT likelihood for nuts with data
4. Run MCMC and compare posteriors
5. Sensitivity analysis: which evidence sources drive results?
