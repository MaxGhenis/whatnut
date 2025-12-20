# What Nut? A Bayesian Analysis of Quality-Adjusted Life Years from Nut Consumption

**Max Ghenis**

max@maxghenis.com

## Abstract

Nut consumption is associated with reduced mortality in observational studies. I present a Bayesian Monte Carlo framework combining pathway-specific mortality effects with evidence-optimized confounding priors. Drawing on meta-analytic evidence from {cite}`aune2016nut` and calibrating against randomized controlled trial (RCT) evidence on intermediate outcomes (low-density lipoprotein [LDL] cholesterol), cross-country comparisons (Golestan cohort), and sibling studies (UK Biobank), I estimate that consuming 28g/day of nuts adds 5 months to life expectancy (95% CI: 1-12 months), equivalent to 0.08 discounted QALYs (95% CI: 0.01-0.24), for a 40-year-old. This is lower than unadjusted observational associations (22% mortality reduction), reflecting that ~25% (95% CI: 2-63%) of observed effects may be causal. 59% of the benefit operates through cardiovascular disease (CVD) prevention. Incremental cost-effectiveness ratios (ICERs) range from \$10,000/QALY (peanuts) to \$57,000/QALY (macadamias); standard thresholds are \$50,000-100,000/QALY.

## Introduction

Nut consumption is associated with reduced all-cause mortality in observational studies. The meta-analysis by {cite}`aune2016nut`, synthesizing 20 prospective cohort studies (n=819,448), found that consuming 28g of nuts daily was associated with a 22% reduction in all-cause mortality (relative risk [RR] 0.78, 95% confidence interval [CI]: 0.72-0.84). Similar associations were reported by {cite}`bao2013association` (n=118,962) and {cite}`grosso2015nut` (n=354,933).

Three challenges complicate translation of these findings: (1) most studies examine "nuts" as a single category, obscuring differences between nut types; (2) observational studies cannot distinguish causal effects from confounding; (3) relative risk reductions do not directly map to absolute benefits.

Quality-adjusted life years (QALYs) provide a standardized metric combining life expectancy and health-related quality of life. QALYs are used in cost-effectiveness analyses by the UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE.

This paper develops a Bayesian Monte Carlo framework for estimating QALY gains from nut consumption, addressing: (1) expected benefit magnitude; (2) nut type comparisons; (3) sensitivity to confounding assumptions.

### Nut Nutrient Profiles

Different nuts have distinct nutrient profiles that suggest pathway-specific mechanisms {cite:p}`usda2024fooddata`:

| Nut | Key Nutrients (per 28g) | Primary Mechanism |
|-----|------------------------|-------------------|
| Walnut | 2.5g ALA omega-3 | CVD (anti-inflammatory, lipids) |
| Almond | 7.3mg vitamin E, 3.5g fiber | Antioxidant, glycemic control |
| Pistachio | 3g fiber, 6g protein, lutein | Lipids, satiety |
| Pecan | 0.5g ALA omega-3, 2.7g fiber | CVD (weaker than walnut) |
| Macadamia | Omega-7 (palmitoleic acid) | Lipids, insulin sensitivity |
| Peanut | 7g protein, 2.4g fiber | Satiety, glycemic control |
| Cashew | 5g protein, low fiber | Mixed (limited evidence) |

Walnuts contain 10x more ALA omega-3 than other tree nuts. Macadamias uniquely contain omega-7 fatty acids. Almonds have the highest vitamin E content. These differences suggest that nut-specific effects may vary by mortality pathway.

**Table 1: Pathway-Specific Nut Adjustment Factors**

| Nut | CVD | Cancer | Other | Evidence | Rationale |
|-----|-----|--------|-------|----------|-----------|
| Walnut | 1.25 (0.08) | 1.05 (0.10) | 1.10 (0.10) | Strong | Highest omega-3; PREDIMED, WAHA RCTs |
| Almond | 1.00 (0.06) | 1.05 (0.08) | 1.00 (0.06) | Strong | Reference; vitamin E antioxidant |
| Pistachio | 1.12 (0.08) | 1.02 (0.10) | 1.05 (0.10) | Moderate | Best lipid improvements in Del Gobbo |
| Pecan | 1.08 (0.10) | 0.98 (0.12) | 1.00 (0.12) | Moderate | Some omega-3; Hart 2025, Guarneiri 2021 |
| Macadamia | 1.08 (0.10) | 0.95 (0.15) | 1.05 (0.12) | Moderate | Omega-7; FDA qualified health claim |
| Peanut | 0.98 (0.06) | 0.90 (0.08) | 0.98 (0.08) | Strong | Aflatoxin concern; large cohort data |
| Cashew | 0.95 (0.10) | 0.95 (0.12) | 0.95 (0.12) | Limited | Mixed RCT results; CIs cross zero |

*Note: Values are mean (SD) adjustment factors. Values >1.0 indicate stronger effects than almonds (reference). Adjustments are applied as exponents on cause-specific RRs.*

## Methods

### Evidence Sources

I constructed a hierarchical evidence base drawing on four categories of sources, in order of priority:

1. **Meta-analyses of mortality outcomes**: {cite}`aune2016nut` and {cite}`grosso2015nut` provided pooled estimates for all-cause mortality.

2. **Large prospective cohort studies**: {cite}`bao2013association` and {cite}`guasch2017nut` provided nut-specific associations.

3. **Randomized controlled trials**: PREDIMED {cite:p}`ros2008mediterranean`, WAHA {cite:p}`rajaram2021walnuts`, and nut-specific lipid trials {cite:p}`delgobbo2015effects,hart2025pecan,guarneiri2021pecan,mah2017cashew` informed nut-specific adjustment factors.

4. **Nutrient composition data**: {cite}`usda2024fooddata` provided standardized nutrient profiles.

### Statistical Model

I employed a Bayesian Monte Carlo simulation with 10,000 iterations. For each iteration:

1. Sampled cause-specific relative risks from log-normal distributions:
   - CVD: RR ~ LogNormal(log(0.75), 0.03)
   - Cancer: RR ~ LogNormal(log(0.87), 0.04)
   - Other: RR ~ LogNormal(log(0.90), 0.03)

2. Applied pathway-specific nut adjustment factors (exponents on cause-specific RRs) based on nutrient profiles and RCT evidence. Each nut type has separate adjustments for CVD, cancer, and other mortality pathways. For example, walnuts have a strong CVD adjustment (1.25, SD 0.08) reflecting their high omega-3 content, while peanuts have a cancer penalty (0.90, SD 0.08) reflecting aflatoxin concerns. See Table 1 for complete adjustment factors. Values >1.0 indicate stronger effects than the reference nut (almonds).

3. Applied confounding adjustment sampled from Beta(1.5, 4.5) with mean 0.25.

4. Computed age-weighted mortality reduction using CDC life tables and age-varying cause fractions (CVD fraction increases from 20% at age 40 to 40% at age 80).

5. Applied quality weight sampled from Beta(17, 3) with mean 0.85.

6. Computed discounted QALYs at 3% annual rate.

### Confounding Calibration

The source meta-analyses adjusted for measured confounders (age, sex, BMI, smoking, alcohol, physical activity). I calibrated the confounding prior using three lines of evidence:

**LDL pathway calibration**: Nuts reduce LDL cholesterol by 0.18 mmol/L {cite:p}`delgobbo2015effects` (61 RCTs). Using established LDL-CVD relationships, this predicts a 4.4% reduction in CVD mortality, compared to 25% observed in cohort studies. This implies ~17% of the observed CVD effect is explained by the LDL pathway.

**UK Biobank evidence**: Sibling-comparison studies of vegetable consumption and CVD mortality found ~80% of observed associations attributable to confounding {cite:p}`mathur2020sensitivity`.

**Golestan cohort**: In Iran, where nut consumption does not correlate with Western healthy lifestyles, the mortality association persisted (HR 0.71 for ≥3 servings/week).

Minimizing squared error to these targets yields Beta(1.5, 4.5) with mean 0.25 (95% CI: 2-63%).

For HR=0.78, the E-value is 1.8: an unmeasured confounder would need RR ≥ 1.8 with both nut consumption and mortality to fully explain the observed association.

### Target Population

Primary analyses assumed a 40-year-old from the US or Europe with 40 years remaining life expectancy. Those with nut allergies (1-2% of population) were excluded.

## Results

### Primary Finding

Median life expectancy gain from 28g/day of any nut: 5 months (95% CI: 1-12 months), equivalent to 0.27 undiscounted QALYs. P(effect > 0) = 85%.

### Pathway Contributions

| Pathway | Contribution | Cause-Specific RR | Source |
|---------|-------------|-------------------|--------|
| CVD mortality | 59% | 0.75 | Aune 2016 |
| Cancer mortality | 17% | 0.87 | Aune 2016 |
| Other causes | 24% | 0.90 | Assumed |

### Nut-Specific Estimates

The spread between highest (walnuts) and lowest (cashews) ranked nuts is 15-20% of the category effect.

| Nut | Evidence | RCT/Cohort Sources |
|-----|----------|-------------------|
| Walnut | Strong | PREDIMED, WAHA |
| Pistachio | Moderate | Del Gobbo meta-analysis |
| Almond | Strong | Multiple RCTs |
| Pecan | Moderate | Hart 2025, Guarneiri 2021 |
| Macadamia | Moderate | FDA health claim |
| Peanut | Strong | Bao 2013 (n=118,962) |
| Cashew | Limited | Mah 2017 (CIs cross zero) |

### Cost-Effectiveness

Lifecycle model with CDC life tables, age-specific quality weights, and 3% annual discounting. Discounted QALY gains: 0.08 (95% CI: 0.01-0.24). Costs from USDA Economic Research Service {cite:p}`usda2024fooddata`.

| Nut | Annual Cost | Discounted QALYs | Cost per QALY |
|-----|-------------|-----------------|---------------|
| Peanut | \$37 | 0.09 | \$10,000 |
| Almond | \$91 | 0.09 | \$23,000 |
| Walnut | \$99 | 0.10 | \$22,000 |
| Pistachio | \$115 | 0.10 | \$28,000 |
| Pecan | \$131 | 0.09 | \$33,000 |
| Cashew | \$102 | 0.09 | \$28,000 |
| Macadamia | \$230 | 0.09 | \$57,000 |

Standard cost-effectiveness thresholds: \$50,000-100,000/QALY (ICER), £20,000-30,000/QALY (NICE). All nuts fall below standard thresholds.

### Uncertainty Quantification

Nuts with limited RCT evidence (cashews, pecans, macadamias) received wider credible intervals rather than lower point estimates.

## Discussion

The calibrated estimate of 5 months life expectancy gain (0.27 undiscounted QALYs) is approximately one-eighth of unadjusted observational estimates, reflecting the Beta(1.5, 4.5) confounding prior with mean 0.25.

The difference between nut types (15-20% of the category effect) is smaller than the difference between any nut consumption and none.

ICERs range from \$10,000/QALY (peanuts) to \$57,000/QALY (macadamias). All nuts fall below standard cost-effectiveness thresholds (\$50,000-100,000/QALY).

### Limitations

1. Estimates rely on observational data; residual confounding may remain despite calibration.
2. Source studies predominantly from US and Europe.
3. Fixed 28g/day dose modeled; dose-response may be non-linear.
4. Perfect adherence assumed.

## Conclusion

Daily nut consumption (28g) is estimated to add 5 months to life expectancy (95% CI: 1-12 months) for a 40-year-old, based on a confounding prior Beta(1.5, 4.5) with mean 0.25 calibrated to LDL pathway effects, UK Biobank sibling comparisons, and the Golestan cohort. 59% of the estimated benefit operates through CVD prevention. ICERs: peanuts \$10,000/QALY, walnuts \$22,000/QALY, macadamias \$57,000/QALY. All nuts fall below standard cost-effectiveness thresholds.

## Data and Code Availability

Code: https://github.com/MaxGhenis/whatnut

```{bibliography}
```

```{tableofcontents}
```
