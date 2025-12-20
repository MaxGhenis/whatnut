# Technical Appendix

This appendix provides detailed technical specifications for the methods described in the main paper.

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

## Simulation Algorithm

For each of 10,000 Monte Carlo iterations:

1. Sample base hazard ratio: $HR \sim \text{LogNormal}(\log(0.78), 0.08)$
2. Sample nut-specific adjustment: $a \sim \text{Normal}(\mu_{nut}, \sigma_{nut})$
3. Compute adjusted HR: $HR_{adj} = HR^a$
4. Sample cause-specific relative risks:
   - CVD: $RR_{cvd} \sim \text{LogNormal}(\log(0.75), 0.03)$
   - Cancer: $RR_{cancer} \sim \text{LogNormal}(\log(0.87), 0.04)$
   - Other: $RR_{other} \sim \text{LogNormal}(\log(0.90), 0.03)$
5. Compute age-weighted mortality reduction using CDC life tables
6. Sample quality weight: $q \sim \text{Beta}(17, 3)$, mean = 0.85
7. Sample confounding adjustment: $c \sim \text{Beta}(1.5, 4.5)$, mean = 0.25
8. Compute life years gained and QALYs

## Nut-Specific Adjustment Factors

| Nut | Adjustment | SD | Evidence | Rationale |
|-----|-----------|-----|----------|-----------|
| Walnut | 1.15 | 0.08 | Strong | PREDIMED, WAHA RCTs, unique omega-3 profile |
| Pistachio | 1.08 | 0.10 | Moderate | Best lipid improvements in RCTs |
| Almond | 1.00 | 0.06 | Strong | Reference nut, robust RCT base |
| Pecan | 1.00 | 0.12 | Moderate | {cite}`hart2025pecan`, {cite}`guarneiri2021pecan` RCTs show significant LDL reductions |
| Macadamia | 1.02 | 0.12 | Moderate | FDA health claim, RCT evidence |
| Peanut | 0.95 | 0.07 | Strong | {cite}`bao2013association` cohort (n=118,962), slight aflatoxin discount |
| Cashew | 0.95 | 0.12 | Limited | Mixed RCT results ({cite}`mah2017cashew`), CIs cross zero |

**Bayesian principle**: Sparse evidence widens confidence intervals but does not lower point estimates. Nuts with limited evidence (macadamia, pecan, cashew) receive higher SD values.

## Confounding Prior Derivation

The evidence-optimized prior Beta(1.5, 4.5) was derived by minimizing squared error to calibration targets:

| Source | Implied Causal % | Weight |
|--------|------------------|--------|
| LDL pathway calibration | ~17% | 1.0 |
| UK Biobank sibling comparisons | ~20% | 1.0 |
| Golestan cohort (Iran) | >25% | 0.5 |

**Optimization**: We minimized $\sum_i w_i \cdot (\mu_{prior} - \mu_i)^2 / (\sigma_{prior}^2 + \sigma_i^2)$ subject to concentration $\alpha + \beta \geq 5$.

**Result**: Beta(1.5, 4.5) with mean 0.25 (95% CI: 2-63%).

## Cost-Effectiveness Model

### Data Sources
- **Life tables**: CDC National Vital Statistics (2021) for age-specific mortality
- **Quality weights**: Age-varying HRQoL from Sullivan et al. (2006)
- **Discounting**: 3% annual rate (standard for NICE, ICER, WHO-CHOICE)
- **Cost data**: USDA ERS retail prices (2024)

### Lifecycle Model

For a 40-year-old beginning daily nut consumption:
- **Undiscounted life years gained**: ~0.33 years (4 months)
- **Undiscounted QALYs**: ~0.28 (life years × quality weight)
- **Discounted QALYs**: ~0.08 (3% annual discounting over 40+ years)
- **Discounted lifetime cost**: ~$4,200 (almonds at $248/year)
- **ICER**: ~$60,000/QALY

### Sensitivity to Discount Rate

| Discount Rate | Rationale | QALYs (any nut) | Cost/QALY Range |
|---------------|-----------|-----------------|-----------------|
| 0% | Undiscounted | 0.28 | \$7,000–45,000 |
| 1.5% | NICE long-term | 0.16 | \$10,000–62,000 |
| 3% | Base case (ICER) | 0.08 | \$25,000–160,000 |
| 3.5% | NICE standard | 0.07 | \$29,000–180,000 |

## E-Value Analysis

Per {cite}`mathur2020sensitivity`, the E-value quantifies the minimum strength of association an unmeasured confounder would need with both exposure and outcome to fully explain an observed association.

For HR = 0.78:
- **E-value ≈ 1.8**
- Interpretation: An unmeasured confounder would need RR ≥ 1.8 with both nut consumption AND mortality to explain the observed effect
- Given that major confounders (smoking, obesity, SES) are already adjusted, this level of residual confounding seems unlikely but not impossible

## Pathway-Specific Mortality Effects

From {cite}`aune2016nut`:

| Cause of Death | Relative Risk | 95% CI | Deaths in Meta-Analysis |
|----------------|--------------|--------|------------------------|
| CVD | 0.75 | 0.71-0.79 | 20,381 |
| Cancer | 0.87 | 0.80-0.93 | 21,353 |
| Other | 0.90 | 0.85-0.95 | Assumed |

### Age-Varying Cause Fractions

Cause-of-death proportions vary by age (CDC WONDER 2021):

| Age | CVD | Cancer | Other |
|-----|-----|--------|-------|
| 40 | 20% | 25% | 55% |
| 50 | 25% | 35% | 40% |
| 60 | 30% | 35% | 35% |
| 70 | 35% | 30% | 35% |
| 80 | 40% | 20% | 40% |

Older ages have higher CVD fractions, which amplifies the nut benefit (since CVD has the strongest RR = 0.75).

## Limitations

1. **Confounding**: Our 25% causal estimate is uncertain (95% CI: 2-63%). True value could be higher or lower.
2. **Generalizability**: Most studies from Western populations (US, Europe, Australia)
3. **Dose-response**: We model 28g/day; effects may be non-linear above this threshold
4. **Nut-specific evidence**: Limited RCT evidence for cashews, pecans, macadamias
5. **Adherence**: Assumes daily consumption; intermittent eating reduces benefits
6. **Competing risks**: Other mortality causes limit achievable gains in elderly populations
