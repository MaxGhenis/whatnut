# Methodology

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

| Nut | Adjustment | SD | Rationale |
|-----|-----------|-----|-----------|
| Walnut | 1.15 | 0.08 | Strongest CVD data, unique omega-3 |
| Pistachio | 1.08 | 0.10 | Best lipid improvements |
| Almond | 1.00 | 0.06 | Reference, robust RCT base |
| Macadamia | 1.02 | 0.15 | Limited evidence, FDA health claim |
| Peanut | 0.95 | 0.07 | Large cohort data, slight aflatoxin discount |
| Pecan | 0.98 | 0.18 | Minimal nut-specific evidence |
| Cashew | 0.92 | 0.14 | Lower fiber, limited RCT data |

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

## Limitations

1. **Confounding**: Observational studies can't fully separate nut effect from healthy user bias
2. **Generalizability**: Most studies are from Western populations
3. **Dose-response**: We model daily consumption; actual effects may vary
4. **Nut-specific evidence**: Very limited for some nuts (pecan, cashew)
