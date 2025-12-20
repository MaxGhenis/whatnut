# Methodology

## Key Findings Summary

**Dose**: 28g/day (1 oz, about a handful)

**Expected Benefit**: ~2.5 QALYs (95% CI: 1.0-4.5) for any nut type

**Practical Takeaway**: Eat whichever nut you'll actually eat consistently. The difference between nut types (~0.7 QALYs) is small relative to the benefit of eating any nut vs. none.

## Target Population

This analysis applies to:
- **Age**: Adults 30-70 years (primary analysis uses 40-year-old baseline)
- **Health status**: General population, not specifically high-risk
- **Geography**: Estimates derived primarily from US and European cohorts
- **Exclusions**: Those with nut allergies (~1-2% of population)

Results may differ for:
- Secondary prevention (existing CVD): likely larger absolute benefit
- Very elderly (80+): shorter time horizon reduces total QALYs
- Non-Western populations: limited generalizability data

## Overview

This analysis estimates the lifetime QALY impact of regular nut consumption using a Bayesian Monte Carlo framework.

## Evidence Hierarchy

We use the following evidence sources, in order of strength:

1. **Meta-analyses of mortality outcomes** - Aune 2016, Grosso 2015
2. **Large cohort studies** - Bao 2013 (NEJM), Guasch-Ferré 2017
3. **Randomized controlled trials** - PREDIMED, WAHA
4. **Nutrient composition data** - USDA FoodData Central

## Key Parameters

### Base Mortality Effect

From Aune et al. 2016 meta-analysis (n=819,448):
- **Relative Risk**: 0.78 (95% CI: 0.72-0.84)
- **Interpretation**: 22% reduced all-cause mortality per 28g/day

### Nut-Specific Adjustments

Each nut receives an adjustment factor based on:
1. Nut-specific outcome studies (if available)
2. Unique nutrient properties (omega-3, omega-7, etc.)
3. Evidence quality (affects uncertainty, not point estimate)

| Nut | Adjustment | SD | Evidence | Rationale |
|-----|-----------|-----|----------|-----------|
| Walnut | 1.15 | 0.08 | Strong | PREDIMED, WAHA RCTs, unique omega-3 profile |
| Pistachio | 1.08 | 0.10 | Strong | Best lipid improvements in RCTs |
| Almond | 1.00 | 0.06 | Strong | Reference nut, robust RCT base |
| Pecan | 1.00 | 0.12 | Moderate | Hart 2025, Guarneiri 2021 RCTs show significant LDL reductions |
| Macadamia | 1.02 | 0.12 | Moderate | FDA health claim, Neale 2023 and Griel 2008 RCTs |
| Peanut | 0.95 | 0.07 | Strong | Bao 2013 cohort (n=118,962), slight aflatoxin discount |
| Cashew | 0.95 | 0.12 | Limited | Mixed RCT results (Mah 2017, Meneguelli 2024), CIs cross zero |

### Bayesian Principle

**Sparse evidence should widen confidence intervals, not lower point estimates.**

For nuts with less evidence (macadamia, pecan), we:
- Keep the point estimate near the category prior (~2.5 QALYs)
- Increase the uncertainty (higher SD)

This differs from naive approaches that penalize low-evidence options.

## Simulation Steps

For each of 10,000 iterations:

1. Sample base hazard ratio: $HR \sim \text{LogNormal}(\log(0.78), 0.08)$
2. Sample nut-specific adjustment: $a \sim \text{Normal}(\mu_{nut}, \sigma_{nut})$
3. Compute adjusted HR: $HR_{adj} = HR^a$
4. Compute years of life gained: $YLG = YLG_{base} \times \frac{1 - HR_{adj}}{1 - 0.78}$
5. Sample quality weight: $q \sim \text{Beta}(17, 3)$
6. Sample confounding adjustment: $c \sim \text{Beta}(8, 2)$
7. Compute QALYs: $QALY = YLG \times q \times c + LE \times QoL_{effect} \times q \times c$

## Confounding Adjustment

### Why We Apply an Additional Adjustment

Meta-analyses like Aune 2016 already adjust for measured confounders (age, sex, BMI, smoking, etc.). However, residual confounding from unmeasured factors likely remains:

- **Healthy user bias**: Nut consumers tend to be more health-conscious overall
- **Socioeconomic status**: Nuts are more expensive than other snacks
- **Dietary pattern**: Nut consumption correlates with overall diet quality

### Our Approach

We apply a Beta(8, 2) confounding adjustment (mean = 0.80, or 20% discount), representing our prior belief that ~80% of the observed association is causal. This is:

1. **Separate from study adjustments**: Studies already adjust for measured confounders
2. **Conservative**: Assumes significant residual confounding exists
3. **Uncertain**: The Beta distribution allows for values from 0.5 to 1.0

### E-Value Analysis

Per Mathur & VanderWeele (2018), the E-value for HR=0.78 is approximately 1.8. This means an unmeasured confounder would need to be associated with both nut consumption AND mortality by a factor of 1.8 to fully explain the observed association. Given that known confounders (smoking, BMI) have already been adjusted, this level of residual confounding seems unlikely.

## External Validation

Our estimates align with published QALY calculations:

| Source | Intervention | QALY Estimate |
|--------|-------------|---------------|
| This analysis | 28g/day nuts | 2.5 (1.0-4.5) |
| Mediterranean diet CEA | Full diet pattern | 2.0-3.0 |
| NICE threshold | Reference | 1 QALY = ~£20-30k |
| WHO CHOICE | Dietary interventions | 1-5 QALYs typical |

The magnitude of our estimate is plausible given:
- 22% mortality reduction is substantial but not unprecedented for dietary factors
- Similar effect sizes seen for Mediterranean diet, exercise interventions
- Conservative confounding adjustment reduces estimate from raw observational data

## Limitations

1. **Confounding**: Observational studies can't fully separate nut effect from healthy user bias. We apply a 20% discount but true confounding is unknown.
2. **Generalizability**: Most studies are from Western populations (US, Europe, Australia)
3. **Dose-response**: We model 28g/day consumption; actual effects may be non-linear
4. **Nut-specific evidence**: Limited RCT evidence for cashews (mixed results); moderate for macadamia and pecan
5. **Adherence**: Assumes daily consumption; intermittent eating likely reduces benefits
6. **Competing risks**: Other mortality causes may limit achievable gains in older populations
