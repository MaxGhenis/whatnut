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

With the scope defined, we now turn to the evidence base and analytical methodology.

## Overview

This analysis estimates the lifetime QALY impact of regular nut consumption using a Bayesian Monte Carlo framework.

## Evidence Hierarchy

We use the following evidence sources, in order of strength:

1. **Meta-analyses of mortality outcomes** - {cite}`aune2016nut`, {cite}`grosso2015nut`
2. **Large cohort studies** - {cite}`bao2013association`, {cite}`guasch2017nut`
3. **Randomized controlled trials** - PREDIMED {cite}`ros2008mediterranean`, WAHA {cite}`rajaram2021walnuts`
4. **Nutrient composition data** - USDA FoodData Central

## Key Parameters

### Base Mortality Effect

From the {cite}`aune2016nut` meta-analysis (n=819,448):
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
| Pecan | 1.00 | 0.12 | Moderate | {cite}`hart2025pecan`, {cite}`guarneiri2021pecan` RCTs show significant LDL reductions |
| Macadamia | 1.02 | 0.12 | Moderate | FDA health claim, {cite}`neale2023macadamia` and {cite}`griel2008macadamia` RCTs |
| Peanut | 0.95 | 0.07 | Strong | {cite}`bao2013association` cohort (n=118,962), slight aflatoxin discount |
| Cashew | 0.95 | 0.12 | Limited | Mixed RCT results ({cite}`mah2017cashew`), CIs cross zero |

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

Meta-analyses like {cite}`aune2016nut` already adjust for measured confounders (age, sex, BMI, smoking, etc.). However, residual confounding from unmeasured factors likely remains:

- **Healthy user bias**: Nut consumers tend to be more health-conscious overall
- **Socioeconomic status**: Nuts are more expensive than other snacks
- **Dietary pattern**: Nut consumption correlates with overall diet quality

### Our Approach

We apply a Beta(8, 2) confounding adjustment (mean = 0.80, or 20% discount), representing our prior belief that ~80% of the observed association is causal. This is:

1. **Separate from study adjustments**: Studies already adjust for measured confounders
2. **Conservative**: Assumes significant residual confounding exists
3. **Uncertain**: The Beta distribution allows for values from 0.5 to 1.0

### E-Value Analysis

Per {cite}`mathur2020sensitivity`, the E-value for HR=0.78 is approximately 1.8. This means an unmeasured confounder would need to be associated with both nut consumption AND mortality by a factor of 1.8 to fully explain the observed association. For context, this exceeds the typical association strength of moderate confounders like education or income with mortality. Given that known strong confounders (smoking HR~2-3, obesity HR~1.5-2) have already been adjusted in the source studies, this level of residual confounding from unmeasured factors seems unlikely.

## External Validation

Our estimates align with published QALY calculations:

| Source | Intervention | QALY Estimate |
|--------|-------------|---------------|
| This analysis | 28g/day nuts | 2.5 (1.0-4.5) |
| Mediterranean diet CEA | Full diet pattern | 2.0-3.0 |
| NICE threshold | Reference | 1 QALY = ~£20-30k |
| WHO-CHOICE | Dietary interventions | 1-5 QALYs typical |

*Note: WHO-CHOICE refers to the WHO's CHOosing Interventions that are Cost-Effective program.*

The magnitude of our estimate is plausible given:
- 22% mortality reduction is substantial but not unprecedented for dietary factors
- Similar effect sizes seen for Mediterranean diet, exercise interventions
- Conservative confounding adjustment reduces estimate from raw observational data

### Cost-Effectiveness

At typical US retail prices (2025), all nuts are highly cost-effective:

| Nut | Annual Cost | Cost per QALY |
|-----|-------------|---------------|
| Peanuts | ~\$100 | ~\$40 |
| Almonds | ~\$250 | ~\$100 |
| Walnuts | ~\$375 | ~\$150 |
| Cashews | ~\$300 | ~\$120 |
| Pecans | ~\$400 | ~\$160 |
| Macadamias | ~\$650 | ~\$260 |
| Pistachios | ~\$350 | ~\$140 |

All values fall well below standard cost-effectiveness thresholds (\$50,000/QALY in US, £20-30k/QALY in UK). Even the most expensive nuts (macadamias) remain highly cost-effective at ~\$260/QALY.

## Limitations

1. **Confounding**: Observational studies can't fully separate nut effect from healthy user bias. We apply a 20% discount but true confounding is unknown.
2. **Generalizability**: Most studies are from Western populations (US, Europe, Australia)
3. **Dose-response**: We model 28g/day consumption; actual effects may be non-linear
4. **Nut-specific evidence**: Limited RCT evidence for cashews (mixed results); moderate for macadamia and pecan
5. **Adherence**: Assumes daily consumption; intermittent eating likely reduces benefits
6. **Competing risks**: Other mortality causes may limit achievable gains in older populations
