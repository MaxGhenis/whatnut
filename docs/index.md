# What Nut? A Bayesian Analysis of Quality-Adjusted Life Years from Nut Consumption

**Max Ghenis**

max@maxghenis.com

## Abstract

Observational studies find nut consumption associated with reduced mortality. I present a Bayesian Monte Carlo framework combining pathway-specific mortality effects with evidence-optimized confounding priors. Drawing on meta-analytic evidence from {cite}`aune2016nut` and calibrating against randomized controlled trial (RCT) evidence on intermediate outcomes (low-density lipoprotein [LDL] cholesterol), cross-country comparisons {cite:p}`hashemian2017nut`, and sibling studies (UK Biobank), I estimate that consuming 28g/day of nuts adds 5 months to life expectancy (95% credible interval [CI]: 1-12 months), equivalent to 0.27 quality-adjusted life years (QALYs; 95% CI: 0.08-0.96 undiscounted, or 0.08 discounted at 3% annually; 95% CI: 0.01-0.24), for a 40-year-old. This is lower than unadjusted observational associations (22% mortality reduction), reflecting that ~25% (95% CI: 2-63%) of observed effects may be causal. 59% of the benefit operates through cardiovascular disease (CVD) prevention. Incremental cost-effectiveness ratios (ICERs) range from \$10,000/QALY (peanuts) to \$57,000/QALY (macadamias); standard thresholds are \$50,000-\$100,000/QALY.

## Introduction

Observational studies find negative associations between nut consumption and all-cause mortality. In a meta-analysis of 15 prospective cohort studies (n=819,448), {cite}`aune2016nut` find that consuming 28 grams of nuts daily is associated with a 22% reduction in all-cause mortality (relative risk [RR] 0.78, 95% confidence interval [CI]: 0.72-0.84). {cite}`bao2013association` (n=118,962) and {cite}`grosso2015nut` (n=354,933) report similar associations.

Three challenges complicate translation of these findings: (1) most studies examine "nuts" as a single category, obscuring differences between nut types; (2) observational studies cannot distinguish causal effects from confounding; (3) relative risk reductions do not directly map to absolute benefits.

Quality-adjusted life years (QALYs) provide a standardized metric combining life expectancy and health-related quality of life. The UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE (World Health Organization CHOosing Interventions that are Cost-Effective) use QALYs in cost-effectiveness analyses.

This paper develops a Bayesian Monte Carlo framework for estimating QALY gains from nut consumption, addressing: (1) expected benefit magnitude; (2) nut type comparisons; (3) sensitivity to confounding assumptions.

### Nut Nutrient Profiles

Nuts vary in macronutrient and micronutrient composition {cite:p}`usda2024fooddata`. All contain 12-22g fat per 28g serving, but differ in fatty acid profiles (monounsaturated vs. polyunsaturated), micronutrient content, and caloric density (157-204 kcal per serving).

**Table 2: Nut Nutrient Profiles.** Macronutrients and key micronutrients per 28g serving. ALA = alpha-linolenic acid (plant-based omega-3 fatty acid); MUFA = monounsaturated fatty acids; PUFA = polyunsaturated fatty acids. Values from USDA FoodData Central SR Legacy database, accessed December 2024.

| Nut | FDC ID | kcal | Fat (g) | MUFA | PUFA | ALA (g) | Fiber (g) | Protein (g) | Notable |
|-----|--------|------|---------|------|------|---------|-----------|-------------|---------|
| Walnut | [170187](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170187/nutrients) | 185 | 18.5 | 2.5 | 13.4 | 2.5 | 1.9 | 4.3 | Highest omega-3 |
| Almond | [170567](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170567/nutrients) | 164 | 14.2 | 9.0 | 3.5 | 0.0 | 3.5 | 6.0 | Highest vitamin E (7.3mg) |
| Pistachio | [170184](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170184/nutrients) | 159 | 12.8 | 6.8 | 3.8 | 0.1 | 2.9 | 5.7 | Lutein (342μg) |
| Pecan | [170182](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170182/nutrients) | 196 | 20.4 | 11.6 | 6.1 | 0.3 | 2.7 | 2.6 | High MUFA |
| Macadamia | [170178](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170178/nutrients) | 204 | 21.5 | 16.7 | 0.4 | 0.1 | 2.4 | 2.2 | Omega-7 (4.7g) |
| Peanut | [172430](https://fdc.nal.usda.gov/fdc-app.html#/food-details/172430/nutrients) | 161 | 14.0 | 6.9 | 4.4 | 0.0 | 2.4 | 7.3 | Highest protein |
| Cashew | [170162](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170162/nutrients) | 157 | 12.4 | 6.7 | 2.2 | 0.0 | 0.9 | 5.2 | Lowest fat/fiber |

**Walnuts** are unique among nuts for their high ALA omega-3 content (2.5g/28g), comprising 73% of total fat as polyunsaturated fatty acids. ALA is a precursor to EPA and DHA, with established anti-inflammatory and cardioprotective effects {cite:p}`ros2008mediterranean`.

**Almonds** provide the highest vitamin E content (7.3mg/28g, 49% DV), a lipid-soluble antioxidant. They also have the highest fiber content among tree nuts, contributing to glycemic control.

**Macadamias** uniquely contain omega-7 fatty acids (palmitoleic acid, 4.7g/28g), which may improve insulin sensitivity. However, they have the highest caloric density (204 kcal) and saturated fat content (3.4g).

**Peanuts** (technically legumes) have the highest protein content (7.3g/28g) and lowest cost, but carry aflatoxin contamination risk that may affect cancer outcomes.

These compositional differences suggest that nut-specific effects may vary by mortality pathway, motivating the pathway-specific modeling approach in this paper.

**Table 1: Pathway-Specific Nut Adjustment Factors.** Adjustment factors applied as exponents to cause-specific relative risks (RRs) for each mortality pathway. Factors derived from RCT evidence on intermediate outcomes (LDL cholesterol, lipid profiles) and nutrient composition. Values >1.0 indicate stronger protective effects than almonds (reference category); values <1.0 indicate weaker effects. Standard deviations (in parentheses) reflect evidence quality: wider SDs for nuts with limited RCT evidence. CVD adjustments primarily reflect omega-3 content and lipid trial results; cancer adjustments reflect antioxidant content and aflatoxin concerns; other-cause adjustments reflect general anti-inflammatory properties.

| Nut | CVD | Cancer | Other | Evidence | Rationale |
|-----|-----|--------|-------|----------|-----------|
| Walnut | 1.25 (0.08) | 1.05 (0.10) | 1.10 (0.10) | Strong | Highest omega-3 (2.5g ALA/28g); PREDIMED, WAHA RCTs show CVD benefit |
| Almond | 1.00 (0.06) | 1.05 (0.08) | 1.00 (0.06) | Strong | Reference category; highest vitamin E (7.3mg/28g) |
| Pistachio | 1.12 (0.08) | 1.02 (0.10) | 1.05 (0.10) | Moderate | Strong lipid improvements; high fiber and lutein content |
| Pecan | 1.08 (0.10) | 0.98 (0.12) | 1.00 (0.12) | Moderate | Moderate omega-3 (0.3g/28g); {cite}`hart2025pecan`, {cite}`guarneiri2021pecan` |
| Macadamia | 1.08 (0.10) | 0.95 (0.15) | 1.05 (0.12) | Moderate | Unique omega-7 content; FDA qualified health claim |
| Peanut | 0.98 (0.06) | 0.90 (0.08) | 0.98 (0.08) | Strong | Aflatoxin contamination risk reduces cancer benefit; large cohort data |
| Cashew | 0.95 (0.10) | 0.95 (0.12) | 0.95 (0.12) | Limited | {cite}`mah2017cashew` shows modest LDL reduction vs control with wider uncertainty than walnut/almond trials |

## Methods

### Evidence Sources

I constructed a hierarchical evidence base drawing on four categories of sources, in order of priority:

1. **Meta-analyses of mortality outcomes**: {cite}`aune2016nut` and {cite}`grosso2015nut` provide pooled estimates for all-cause mortality.

2. **Large prospective cohort studies**: {cite}`bao2013association` and {cite}`guasch2017nut` provide nut-specific associations.

3. **Randomized controlled trials**: {cite}`ros2008mediterranean` (PREDIMED), {cite}`rajaram2021walnuts` (WAHA), {cite}`delgobbo2015effects`, {cite}`hart2025pecan`, {cite}`guarneiri2021pecan`, and {cite}`mah2017cashew` inform nut-specific adjustment factors.

4. **Nutrient composition data**: {cite}`usda2024fooddata` provides standardized nutrient profiles.

### Statistical Model

I employed a Bayesian Monte Carlo simulation with 10,000 iterations using the `lifecycle_pathways` module (random seed 42 for reproducibility). For each iteration:

1. Sampled cause-specific relative risks from log-normal distributions (based on {cite}`aune2016nut` mortality estimates for high vs. low nut consumption):
   - CVD mortality: RR ~ LogNormal(log(0.75), 0.03)
   - Cancer mortality: RR ~ LogNormal(log(0.87), 0.04)
   - Other mortality: RR ~ LogNormal(log(0.90), 0.03)

2. Applied pathway-specific nut adjustment factors (exponents on cause-specific RRs) based on nutrient profiles and RCT evidence. Each nut type has separate adjustments for CVD, cancer, and other mortality pathways. For example, walnuts have a strong CVD adjustment (1.25, SD 0.08) reflecting their high omega-3 content, while peanuts have a cancer penalty (0.90, SD 0.08) reflecting aflatoxin concerns. See Table 1 for complete adjustment factors. Values >1.0 indicate stronger effects than the reference nut (almonds).

3. Applied confounding adjustment sampled from Beta(1.5, 4.5) with mean 0.25.

4. Computed age-weighted mortality reduction using CDC life tables and age-varying cause fractions (CVD fraction increases from 20% at age 40 to 40% at age 80).

5. Applied quality weight sampled from Beta(17, 3) with mean 0.85, based on age-adjusted EQ-5D population norms for US adults {cite:p}`sullivan2005catalogue`.

6. Computed discounted QALYs at 3% annual rate.

### Confounding Calibration

The source meta-analyses adjusted for measured confounders (age, sex, body mass index [BMI], smoking, alcohol, physical activity). I calibrated the confounding prior using three lines of evidence:

**LDL pathway calibration**: {cite}`delgobbo2015effects` find that nuts reduce LDL cholesterol by 4.8 mg/dL (0.12 mmol/L) per serving (61 controlled trials). Using established LDL-CVD relationships, this predicts a ~3% reduction in CVD mortality, compared to 25% observed in cohort studies. This implies ~12% of the observed CVD effect operates through the LDL pathway.

**Sibling comparison evidence**: Within-family studies that control for shared genetic and environmental confounding typically find attenuated associations between dietary factors and mortality, suggesting substantial confounding in observational studies.

**Golestan cohort**: {cite}`hashemian2017nut` find that in Iran, where nut consumption does not correlate with Western healthy lifestyles, the mortality association persists (hazard ratio [HR] 0.71 for ≥3 servings/week).

I calibrated the Beta prior by assigning weights to each evidence source: LDL pathway (weight 0.4, target 12% causal), sibling studies (weight 0.4, target 20% causal), and Golestan cohort (weight 0.2, target 40% causal given persistent associations). Rather than setting the prior mean to a simple weighted average of targets, I calibrated Beta parameters to match the full distribution of evidence—capturing both the central tendency and the wide uncertainty across sources. This yields Beta(1.5, 4.5), a right-skewed distribution with mean 0.25 and 95% CI: 2-63%, reflecting that most evidence points to low causal fractions while allowing for the possibility of larger effects suggested by the Golestan cohort.

For HR=0.78, the E-value is 1.8 {cite:p}`vanderweele2017sensitivity`: an unmeasured confounder would need RR ≥ 1.8 with both nut consumption and mortality to fully explain the observed association.

### Target Population

Primary analyses assumed a 40-year-old from the US or Europe with 40 years remaining life expectancy. I excluded individuals with nut allergies (1-2% of population).

## Results

### Primary Finding

Median life expectancy gain from 28g/day of any nut: 5 months (95% CI: 1-12 months). This translates to 0.27 undiscounted QALYs, or **0.08 discounted QALYs** (95% CI: 0.01-0.24) at the standard 3% annual discount rate used in health economic evaluations. I report both values because undiscounted QALYs (0.27) are more intuitive for clinical interpretation—representing actual expected health gains—while discounted QALYs (0.08) are standard for cost-effectiveness analysis, reflecting that future health benefits are valued less than immediate ones. P(effect > 0) = 85%. Unless otherwise noted, QALY estimates in this paper refer to discounted values.

### Pathway Contributions

**Table 3: Pathway-Specific Contributions to Mortality Benefit.** Decomposition of life expectancy gains by cause of death. Cause-specific relative risks (RRs) from {cite}`aune2016nut` meta-analysis; "Other" category assumed based on weighted average of non-CVD, non-cancer effects.

| Pathway | Contribution | Cause-Specific RR | Source |
|---------|-------------|-------------------|--------|
| CVD mortality | 59% | 0.75 | Aune 2016 |
| Cancer mortality | 17% | 0.87 | Aune 2016 |
| Other causes | 24% | 0.90 | Assumed |

### Nut-Specific Estimates

The spread between highest (walnuts) and lowest (cashews) ranked nuts is 15-20% of the category effect.

**Table 4: Evidence Quality by Nut Type.** Summary of RCT and cohort study support for each nut type. "Strong" = multiple RCTs or large cohorts (n>100,000); "Moderate" = single RCT or smaller cohorts; "Limited" = RCTs with confidence intervals crossing null.

| Nut | Evidence | RCT/Cohort Sources |
|-----|----------|-------------------|
| Walnut | Strong | PREDIMED, WAHA |
| Pistachio | Moderate | Del Gobbo meta-analysis |
| Almond | Strong | Multiple RCTs |
| Pecan | Moderate | Hart 2025, Guarneiri 2021 |
| Macadamia | Moderate | FDA health claim |
| Peanut | Strong | Bao 2013 (n=118,962) |
| Cashew | Limited | Mah 2017 (wider CIs than other nuts) |

### Cost-Effectiveness

Lifecycle model with CDC life tables, age-specific quality weights, and 3% annual discounting. Discounted QALY gains: 0.08 (95% CI: 0.01-0.24). Costs from USDA Economic Research Service {cite:p}`usda2024fooddata`.

**Table 5: Cost-Effectiveness Analysis by Nut Type.** Annual costs based on 28g/day consumption at 2024 retail prices. Discounted QALYs calculated over remaining lifespan for a 40-year-old at 3% annual discount rate. Cost per QALY = (annual cost × expected years) / discounted QALYs.

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

I assign wider credible intervals to nuts with limited RCT evidence (cashews, pecans, macadamias) rather than lower point estimates.

## Discussion

The calibrated estimate of 5 months life expectancy gain (0.27 undiscounted QALYs) is approximately one-eighth of unadjusted observational estimates, reflecting the Beta(1.5, 4.5) confounding prior with mean 0.25.

The difference between nut types (15-20% of the category effect) is smaller than the difference between any nut consumption and none.

ICERs range from \$10,000/QALY (peanuts) to \$57,000/QALY (macadamias). All nuts fall below standard cost-effectiveness thresholds (\$50,000-100,000/QALY).

### Sensitivity Analyses

I examined robustness to key parameter assumptions:

**Discount rate**: At 0% (undiscounted), QALY gains increase to 0.27 (vs 0.08 at 3%); at 5%, gains decrease to 0.05. The ranking of nuts by cost-effectiveness is unchanged across discount rates.

**Confounding prior**: Using Beta(0.5, 4.5) with mean 10% causal (more skeptical) reduces QALYs to 0.03; using Beta(3, 3) with mean 50% causal increases QALYs to 0.16. ICERs scale inversely.

**Adherence**: At 50% real-world adherence (vs 100% assumed), effective QALYs halve to 0.04 and ICERs double. Peanuts remain cost-effective (\$20,000/QALY); macadamias exceed thresholds (\$114,000/QALY).

**Age at initiation**: For a 60-year-old (vs 40), discounted QALYs decrease to 0.05 due to shorter remaining lifespan, but the stronger CVD benefit at older ages partially offsets this.

### Limitations

1. Estimates rely on observational data; residual confounding may remain despite calibration.
2. Source studies predominantly from US and Europe.
3. Fixed 28g/day dose modeled; dose-response may be non-linear ({cite}`aune2016nut` find benefits plateau above ~20g/day).
4. Perfect adherence assumed; real-world adherence likely 50-70%.
5. Substitution effects not modeled (what foods nuts replace affects net benefit).

## Conclusion

I estimate that daily nut consumption (28g) adds 5 months to life expectancy (95% CI: 1-12 months) for a 40-year-old, equivalent to 0.27 QALYs undiscounted or 0.08 QALYs discounted at 3% annually. This is based on a confounding prior Beta(1.5, 4.5) with mean 0.25 calibrated to LDL pathway effects (12% causal), sibling comparisons (20% causal), and the Golestan cohort (40% causal). 59% of the benefit operates through CVD prevention. ICERs: peanuts \$10,000/QALY, walnuts \$22,000/QALY, macadamias \$57,000/QALY. All nuts fall below standard cost-effectiveness thresholds (\$50,000-100,000/QALY). **Caution**: Individuals with nut allergies (1-2% prevalence) should not consume nuts.

## Data and Code Availability

Code: https://github.com/MaxGhenis/whatnut

```{bibliography}
```

```{tableofcontents}
```
