# Technical Appendix

## Target Population

This analysis applies to:
- **Age**: Adults 30-70 years (primary analysis uses 40-year-old baseline)
- **Health status**: General population, not specifically high-risk
- **Geography**: Estimates derived primarily from US and European cohorts
- **Exclusions**: Those with nut allergies (~1-2% of population)

Not modeled:
- Secondary prevention (existing CVD)
- Very elderly (80+)
- Non-Western populations

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

| Nut | CVD Adj | Cancer Adj | Other Adj | Evidence | Rationale |
|-----|---------|------------|-----------|----------|-----------|
| Walnut | 1.25 (0.08) | 1.05 (0.10) | 1.10 (0.10) | Strong | PREDIMED, WAHA RCTs, highest omega-3 |
| Pistachio | 1.12 (0.08) | 1.02 (0.10) | 1.05 (0.10) | Moderate | Strong lipid improvements in RCTs |
| Almond | 1.00 (0.06) | 1.05 (0.08) | 1.00 (0.06) | Strong | Reference nut, robust RCT base |
| Pecan | 1.08 (0.10) | 0.98 (0.12) | 1.00 (0.12) | Moderate | {cite}`hart2025pecan`, {cite}`guarneiri2021pecan` |
| Macadamia | 1.08 (0.10) | 0.95 (0.15) | 1.05 (0.12) | Moderate | Omega-7, FDA health claim |
| Peanut | 0.98 (0.06) | 0.90 (0.08) | 0.98 (0.08) | Strong | {cite}`bao2013association` (n=118,962), aflatoxin concern |
| Cashew | 0.95 (0.10) | 0.95 (0.12) | 0.95 (0.12) | Limited | {cite}`mah2017cashew`, wider CIs |

Nuts with limited evidence (macadamia, pecan, cashew) receive higher SD values.

## Confounding Prior Derivation

The evidence-optimized prior Beta(1.5, 4.5) was derived by minimizing squared error to calibration targets:

| Source | Target Causal % | Weight |
|--------|-----------------|--------|
| LDL pathway calibration | 12% | 0.4 |
| Sibling comparisons | 20% | 0.4 |
| Golestan cohort (Iran) | 40% | 0.2 |

**Optimization**: Rather than setting the prior mean to a simple weighted average of targets, we calibrated Beta parameters to match the full distribution of evidence—capturing both the central tendency and the wide uncertainty across sources.

**Result**: Beta(1.5, 4.5) with mean 0.25 (95% CI: 2-63%).

## Cost-Effectiveness Model

### Data Sources
- **Life tables**: CDC National Vital Statistics (2021) for age-specific mortality
- **Quality weights**: Age-varying HRQoL from Sullivan et al. (2006)
- **Discounting**: 3% annual rate (standard for NICE, ICER, WHO-CHOICE)
- **Cost data**: USDA ERS retail prices (2024)

### Lifecycle Model

For a 40-year-old beginning daily nut consumption:
- **Undiscounted life years gained**: ~0.43 years (5 months)
- **Undiscounted QALYs**: ~0.27 (life years × age-weighted quality)
- **Discounted QALYs**: ~0.08-0.10 (3% annual discounting over 40+ years)
- **ICERs**: $10,000/QALY (peanuts) to $57,000/QALY (macadamias)

### Sensitivity to Discount Rate

| Discount Rate | Rationale | QALYs (any nut) | Cost/QALY Range |
|---------------|-----------|-----------------|-----------------|
| 0% | Undiscounted | 0.28 | \$7,000–45,000 |
| 1.5% | NICE long-term | 0.16 | \$10,000–62,000 |
| 3% | Base case (ICER) | 0.08 | \$25,000–160,000 |
| 3.5% | NICE standard | 0.07 | \$29,000–180,000 |

## E-Value Analysis

Per {cite}`vanderweele2017sensitivity`, the E-value quantifies the minimum strength of association an unmeasured confounder would need with both exposure and outcome to fully explain an observed association.

For a protective exposure with hazard ratio $HR$, we first convert to relative risk $RR = 1/HR$, then calculate:

$$E\text{-value} = RR + \sqrt{RR \times (RR - 1)}$$

For HR = 0.78:
- $RR = 1/0.78 = 1.28$
- $E\text{-value} = 1.28 + \sqrt{1.28 \times 0.28} = 1.28 + 0.60 \approx 1.8$

An unmeasured confounder would need RR ≥ 1.8 with both nut consumption and mortality to fully explain the observed effect.

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

CVD fraction increases with age; CVD has the lowest RR (0.75).

## Limitations

1. **Confounding**: Our 25% causal estimate is uncertain (95% CI: 2-63%). True value could be higher or lower.
2. **Generalizability**: Most studies from Western populations (US, Europe, Australia)
3. **Dose-response**: We model 28g/day; effects may be non-linear above this threshold
4. **Nut-specific evidence**: Limited RCT evidence for cashews, pecans, macadamias
5. **Adherence**: Assumes daily consumption; intermittent eating reduces benefits
6. **Competing risks**: Other mortality causes limit achievable gains in elderly populations
