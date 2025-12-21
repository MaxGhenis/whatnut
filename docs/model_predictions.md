# Pre-Registered Predictions for Bayesian Model

## Current Model Predictions (for reference)
From `lifecycle_pathways.py` with confounding prior Beta(1.5, 4.5):

| Nut | Observational RR | Causal RR (×0.25) | Current Discounted QALYs |
|-----|------------------|-------------------|--------------------------|
| Walnut | 0.73 | ~0.93 | 0.10 |
| Almond | 0.78 | ~0.95 | 0.09 |
| Pistachio | 0.76 | ~0.94 | 0.10 |
| Macadamia | 0.77 | ~0.94 | 0.09 |
| Peanut | 0.78 | ~0.95 | 0.09 |
| Cashew | 0.79 | ~0.95 | 0.09 |

## Nutrient-Based Predictions (point estimates)
From `bayesian_model.py compute_nutrient_based_effects()`:

| Nut | Nutrient log-RR | Nutrient RR | Primary Driver |
|-----|-----------------|-------------|----------------|
| Walnut | -0.34 | 0.71 | ALA (88%) |
| Almond | -0.11 | 0.89 | Vitamin E (65%) |
| Pistachio | -0.04 | 0.96 | Fiber (100%) |
| Pecan | -0.06 | 0.94 | ALA + Fiber |
| Macadamia | -0.07 | 0.93 | Omega-7 (136%) |
| Peanut | -0.04 | 0.96 | Fiber + VitE |
| Cashew | +0.02 | 1.02 | Sat fat dominates |

## Expected MCMC Posterior Predictions

### Assumptions for prediction:
1. Confounding prior Beta(1.5, 4.5) stays the same (mean 0.25)
2. RCT likelihood shrinks estimates toward LDL-predicted effects
3. Hierarchical shrinkage pulls outliers toward group mean
4. Nutrients inform the prior; RCTs update it

### Predicted causal RRs (after confounding adjustment):

| Nut | Expected RR | 95% CI | Reasoning |
|-----|-------------|--------|-----------|
| **Walnut** | 0.92-0.95 | [0.85, 0.98] | Strong ALA effect, good RCT evidence |
| **Almond** | 0.97-0.98 | [0.94, 1.00] | Vitamin E helps, but less than current model |
| **Pistachio** | 0.98-0.99 | [0.95, 1.01] | Shrinkage toward group; limited unique nutrients |
| **Pecan** | 0.97-0.98 | [0.93, 1.01] | Some ALA, weak RCT evidence → wide CI |
| **Macadamia** | 0.96-0.98 | [0.90, 1.02] | Omega-7 uncertain; wide prior → wide posterior |
| **Peanut** | 0.98-0.99 | [0.95, 1.01] | Nutrition similar to baseline; large cohort evidence |
| **Cashew** | 0.99-1.01 | [0.96, 1.04] | Nutrients predict harm; RCT CIs cross null |

### Key predictions to verify:

1. **Walnut should be best** - large ALA effect survives confounding adjustment
2. **Walnut-cashew gap should INCREASE** - from ~0.05 RR difference (current) to ~0.07-0.08
3. **Most nuts should cluster around RR 0.97-0.99** - modest causal effects
4. **Cashew CI should cross 1.0** - uncertain whether beneficial or harmful
5. **Macadamia CI should be widest** - omega-7 prior has largest SD
6. **Nutrient betas should shrink toward zero** - RCT evidence is limited

### Expected QALY changes:

| Nut | Current QALYs | Expected QALYs | Change |
|-----|---------------|----------------|--------|
| Walnut | 0.10 | 0.06-0.08 | ↓ 20-40% |
| Almond | 0.09 | 0.02-0.04 | ↓ 55-75% |
| Pistachio | 0.10 | 0.02-0.03 | ↓ 70-80% |
| Macadamia | 0.09 | 0.02-0.05 | ↓ 45-75% |
| Peanut | 0.09 | 0.02-0.03 | ↓ 65-75% |
| Cashew | 0.09 | 0.00-0.02 | ↓ 75-100% |

### Overall effect:
- **Mean QALY across nuts**: 0.03-0.05 (vs 0.09 current)
- **Walnut advantage persists** but smaller in absolute terms
- **Cashews may be neutral** - not beneficial, not harmful
- **Cost-effectiveness worsens** - ICERs roughly double

## Why these predictions?

1. **The current model is overconfident** - it applies the observational RR (0.78) with only a 25% causal adjustment, but the nutrient composition can only explain effects for walnuts (via ALA) and partially macadamias (via omega-7).

2. **The hierarchical structure creates shrinkage** - nuts without unique nutrient advantages get pulled toward the group mean, which is near null.

3. **RCT evidence is limited** - most RCTs measure LDL, not mortality. The LDL pathway explains only ~3% CVD reduction.

4. **Uncertainty compounds** - nutrient priors × pathway relationships × confounding → wide posteriors

## Falsification criteria:

The model would be WRONG if:
1. Cashews show RR < 0.95 (strong benefit despite poor nutrient profile)
2. Walnuts show RR > 0.97 (ALA prior has no effect)
3. All nuts cluster tightly (no differentiation by nutrients)
4. Posterior CIs are narrower than priors (learning impossible without mortality RCT data)

Date: 2024-12-20
Author: Pre-registered before running MCMC
