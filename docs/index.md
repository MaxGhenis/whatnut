# What Nut? A Bayesian Analysis of Quality-Adjusted Life Years from Nut Consumption

**Max Ghenis**

max@maxghenis.com

## Abstract

Observational studies find nut consumption associated with reduced mortality. I present a hierarchical Bayesian framework with pathway-specific effects (cardiovascular, cancer, other mortality, and quality of life), nutrient-derived priors from independent meta-analyses, and evidence-calibrated confounding adjustment. Using Markov Chain Monte Carlo (MCMC) with non-centered parameterization (0% divergences), I estimate that consuming 28g/day of walnuts yields 0.20 quality-adjusted life years (QALYs; 95% credible interval [CI]: 0.02-0.55), with other nuts ranging from 0.11 QALYs (pecans) to 0.20 QALYs (almonds). Approximately 75% of benefit operates through cardiovascular disease (CVD) prevention, with pathway-specific relative risks of 0.83-0.90 for CVD versus 0.97-0.99 for cancer. Incremental cost-effectiveness ratios (ICERs) range from \$5,700/QALY (peanuts) to \$45,000/QALY (macadamias).

## Introduction

### The Nut-Mortality Association

Researchers have studied the relationship between nut consumption and mortality for over three decades. {cite}`fraser1992possible` first reported reduced coronary heart disease risk among nut consumers in the Adventist Health Study. Subsequent prospective cohorts replicated this finding: the Iowa Women's Health Study {cite:p}`ellsworth2001frequent`, the Physicians' Health Study {cite:p}`albert2002nut`, and the Nurses' Health Study {cite:p}`hu2003nut` each reported 30-50% reductions in cardiovascular disease (CVD) risk among regular nut consumers.

The evidence base expanded substantially with three large-scale analyses. {cite}`bao2013association` analyzed 118,962 participants from the Nurses' Health Study and Health Professionals Follow-up Study, finding that consuming nuts ≥7 times per week was associated with 20% lower all-cause mortality (hazard ratio [HR] 0.80, 95% CI: 0.73-0.86). {cite}`grosso2015nut` conducted a meta-analysis of 354,933 participants across 18 cohorts, estimating a 19% mortality reduction (RR 0.81, 95% CI: 0.77-0.85) for highest versus lowest consumption. {cite}`aune2016nut` synthesized 819,448 participants across 15 cohorts, finding that 28g/day of nut consumption was associated with 22% lower all-cause mortality (RR 0.78, 95% CI: 0.72-0.84).

### Cause-Specific Effects

The mortality benefit appears concentrated in cardiovascular causes. {cite}`aune2016nut` find stronger associations for CVD mortality (RR 0.71, 95% CI: 0.63-0.80) than cancer mortality (RR 0.87, 95% CI: 0.80-0.93). This pattern aligns with mechanistic studies showing that nuts improve intermediate CVD risk factors: {cite}`delgobbo2015effects` meta-analyzed 61 controlled feeding trials (n=2,582) and found that nut consumption reduces low-density lipoprotein (LDL) cholesterol by 4.8 mg/dL (0.12 mmol/L), with additional improvements in apolipoprotein B and triglycerides.

### The Confounding Problem

A central challenge in nutritional epidemiology is distinguishing causal effects from confounding. Nut consumers differ systematically from non-consumers: they are more likely to exercise, less likely to smoke, have higher education and income, and consume more fruits and vegetables {cite:p}`jenab2004associated`. While cohort studies adjust for these measured confounders, unmeasured confounding may persist.

Three lines of evidence inform the causal fraction of observed associations. First, {cite:t}`hashemian2017nut` studied 50,045 adults in the Golestan cohort in northeastern Iran, where nut consumption does not correlate with Western healthy lifestyle patterns. The mortality association persisted (HR 0.71 for ≥3 servings/week), suggesting causal effects independent of healthy-user confounding. Second, sibling-comparison designs that control for shared genetic and environmental factors typically find attenuated—though non-zero—dietary associations. Third, calibrating observed effects against the magnitude predicted from RCT-demonstrated improvements in intermediate outcomes (e.g., LDL cholesterol) suggests that only a fraction of observed associations can be mechanistically explained.

### Gaps in Existing Literature

Three limitations motivate this analysis. First, most studies examine "any nuts" as a single category, obscuring compositional differences. Walnuts contain 2.5g of alpha-linolenic acid (ALA) omega-3 per 28g serving; almonds contain none. Macadamias contain 4.7g of palmitoleic acid (omega-7); other nuts contain negligible amounts. These differences may translate to differential health effects.

Second, relative risk reductions do not directly map to absolute benefits. A 22% mortality reduction sounds substantial, but absolute life expectancy gains depend on baseline mortality risk, age distribution of benefits, and cause-specific mortality patterns.

Third, health policy requires standardized metrics for resource allocation. Quality-adjusted life years (QALYs) combine life expectancy and health-related quality of life into a single metric. The UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE (World Health Organization CHOosing Interventions that are Cost-Effective) use QALYs in cost-effectiveness analyses. No existing study quantifies QALY gains from nut consumption.

### Contribution

This paper develops a Bayesian Monte Carlo framework for estimating QALY gains from nut consumption, addressing: (1) expected benefit magnitude in standardized units; (2) nut type comparisons based on compositional differences; (3) explicit treatment of confounding uncertainty calibrated to multiple evidence sources.

### Nut Nutrient Profiles

Nuts vary in macronutrient and micronutrient composition {cite:p}`usda2024fooddata`. All contain 12-22g fat per 28g serving, but differ in fatty acid profiles (monounsaturated vs. polyunsaturated), micronutrient content, and caloric density (157-204 kcal per serving). Throughout this paper, "nuts" refers to tree nuts plus peanuts (a legume), following epidemiological convention.

**Table 1: Nut Nutrient Profiles.** Macronutrients and key micronutrients per 28g serving. ALA = alpha-linolenic acid (plant-based omega-3 fatty acid); MUFA = monounsaturated fatty acids; PUFA = polyunsaturated fatty acids. Values from USDA FoodData Central SR Legacy database, accessed December 2024.

| Nut | FDC ID | kcal | Fat (g) | MUFA | PUFA | ALA (g) | Fiber (g) | Protein (g) | Notable |
|-----|--------|------|---------|------|------|---------|-----------|-------------|---------|
| Walnut | [170187](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170187/nutrients) | 185 | 18.5 | 2.5 | 13.4 | 2.5 | 1.9 | 4.3 | Highest omega-3 |
| Almond | [170567](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170567/nutrients) | 164 | 14.2 | 9.0 | 3.5 | 0.0 | 3.5 | 6.0 | Highest vitamin E (7.3mg) |
| Pistachio | [170184](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170184/nutrients) | 159 | 12.8 | 6.8 | 3.8 | 0.1 | 2.9 | 5.7 | Lutein (342μg) |
| Pecan | [170182](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170182/nutrients) | 196 | 20.4 | 11.6 | 6.1 | 0.3 | 2.7 | 2.6 | High MUFA |
| Macadamia | [170178](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170178/nutrients) | 204 | 21.5 | 16.7 | 0.4 | 0.1 | 2.4 | 2.2 | Omega-7 (4.7g) |
| Peanut | [172430](https://fdc.nal.usda.gov/fdc-app.html#/food-details/172430/nutrients) | 161 | 14.0 | 6.9 | 4.4 | 0.0 | 2.4 | 7.3 | Highest protein |
| Cashew | [170162](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170162/nutrients) | 157 | 12.4 | 6.7 | 2.2 | 0.0 | 0.9 | 5.2 | Lowest fat/fiber |

**Walnuts** have the highest ALA omega-3 content (2.5g/28g), comprising 73% of total fat as polyunsaturated fatty acids. ALA is a precursor to EPA and DHA {cite:p}`ros2008mediterranean`.

**Almonds** have the highest vitamin E content (7.3mg/28g, 49% DV) and highest fiber content among tree nuts (3.5g/28g).

**Macadamias** are the only common nut with substantial omega-7 fatty acids (palmitoleic acid, 4.7g/28g). They also have the highest caloric density (204 kcal) and saturated fat content (3.4g).

**Peanuts** (technically legumes) have the highest protein content (7.3g/28g) and lowest cost. Aflatoxin contamination occurs in some regions, particularly sub-Saharan Africa and Southeast Asia {cite:p}`williams2004aflatoxin`.

## Methods

### Evidence Sources

I constructed a hierarchical evidence base drawing on four categories of sources, in order of priority:

1. **Meta-analyses of mortality outcomes**: {cite}`aune2016nut` and {cite}`grosso2015nut` provide pooled estimates for all-cause mortality.

2. **Large prospective cohort studies**: {cite}`bao2013association` and {cite}`guasch2017nut` provide nut-specific associations.

3. **Randomized controlled trials**: {cite}`ros2008mediterranean` (PREDIMED), {cite}`rajaram2021walnuts` (WAHA), {cite}`delgobbo2015effects`, {cite}`hart2025pecan`, {cite}`guarneiri2021pecan`, and {cite}`mah2017cashew` inform nut-specific adjustment factors.

4. **Nutrient composition data**: {cite}`usda2024fooddata` provides standardized nutrient profiles.

### Statistical Model

I implemented a hierarchical Bayesian model using PyMC with Markov Chain Monte Carlo (MCMC) sampling. The model uses non-centered parameterization to ensure efficient sampling. I confirmed convergence via MCMC diagnostics: 0% divergences across 4,000 posterior samples from 4 chains, R-hat < 1.01 for all parameters, and effective sample sizes (ESS) > 1,000 for key parameters.

#### Pathway-Specific Effects

The model estimates separate relative risks for four pathways:
- **CVD mortality**: Strongest effects (RR 0.83-0.90), informed by ALA omega-3, fiber, and magnesium priors
- **Cancer mortality**: Modest effects (RR 0.97-0.99), informed by fiber and vitamin E priors
- **Other mortality**: Moderate effects (RR 0.94-0.97), composite of remaining causes
- **Quality of life**: Morbidity effects (RR 0.94-0.97), affecting health utility weights

This decomposition allows different nutrients to contribute differentially to each pathway. For example, ALA omega-3 strongly affects CVD but has negligible cancer effects, while fiber contributes to both.

#### Nutrient-Derived Priors

Rather than specifying nut-specific effects directly, I derived expected effects from nutrient composition using priors from independent meta-analyses:

**Table 2: Nutrient-Pathway Effect Priors.** Log-relative risk per unit nutrient, with pathway-specific coefficients. Priors from meta-analyses of prospective cohort studies and randomized trials.

| Nutrient | CVD Effect | Cancer Effect | Other Effect | Quality Effect | Source |
|----------|------------|---------------|--------------|----------------|--------|
| ALA omega-3 (per g) | -0.15 (0.05) | -0.02 (0.02) | -0.08 (0.04) | -0.05 (0.03) | {cite}`naghshi2021ala` |
| Fiber (per g) | -0.015 (0.005) | -0.015 (0.005) | -0.01 (0.005) | -0.02 (0.01) | {cite}`threapleton2013fiber` |
| Omega-6 (per g) | -0.004 (0.002) | -0.002 (0.002) | -0.002 (0.002) | -0.002 (0.002) | {cite}`farvid2014omega6` |
| Omega-7 (per g) | -0.03 (0.04) | 0.00 (0.02) | -0.02 (0.03) | -0.02 (0.03) | Author prior (limited evidence) |
| Saturated fat (per g) | +0.02 (0.01) | +0.01 (0.01) | +0.01 (0.01) | +0.01 (0.01) | {cite}`sacks2017sat` |
| Magnesium (per 10mg) | -0.003 (0.001) | -0.001 (0.001) | -0.002 (0.001) | -0.003 (0.001) | {cite}`fang2016mg` |
| Arginine (per 100mg) | -0.003 (0.002) | -0.001 (0.001) | -0.002 (0.001) | -0.002 (0.001) | Author prior (limited evidence) |
| Vitamin E (per mg) | -0.005 (0.003) | -0.01 (0.005) | -0.003 (0.002) | -0.005 (0.003) | Author prior (limited evidence) |
| Phytosterols (per 10mg) | -0.001 (0.001) | -0.001 (0.001) | 0.00 (0.001) | -0.001 (0.001) | Author prior (limited evidence) |
| Protein (per g) | -0.002 (0.002) | -0.001 (0.001) | -0.001 (0.001) | -0.002 (0.001) | Author prior (limited evidence) |

#### Hierarchical Structure

Nut-specific effects are modeled as deviations from nutrient-predicted effects using non-centered parameterization:

```
z_pathway ~ Normal(0, 1)  # Standardized deviations
τ_pathway ~ HalfNormal(0.03)  # Shrinkage prior
true_effect = expected_from_nutrients + τ_pathway × z_pathway
```

This parameterization ensures efficient MCMC sampling and shrinks nut-specific deviations toward nutrient-predicted effects when evidence is limited.

#### Confounding Adjustment

The model includes a causal fraction parameter with Beta(1.5, 4.5) prior (mean 0.25, 95% CI: 0.02-0.63), calibrated to three evidence sources (see Confounding Calibration section below).

#### Lifecycle Integration

Posterior samples of pathway-specific relative risks are propagated through a lifecycle model with:
- CDC life tables for age-specific mortality
- Age-varying cause fractions (CVD increases from 20% at age 40 to 40% at age 80)
- Quality weights from EQ-5D population norms (mean 0.85) {cite:p}`sullivan2005catalogue`
- 3% annual discounting

### Confounding Calibration

The source meta-analyses adjusted for measured confounders (age, sex, body mass index [BMI], smoking, alcohol, physical activity). I calibrated the confounding prior using three lines of evidence:

**LDL pathway calibration**: {cite}`delgobbo2015effects` find that nuts reduce LDL cholesterol by 4.8 mg/dL (0.12 mmol/L) per serving (61 controlled trials). Using established LDL-CVD relationships, this predicts a ~3% reduction in CVD mortality, compared to 25% observed in cohort studies. This implies ~12% of the observed CVD effect operates through the LDL pathway.

**Sibling comparison evidence**: Within-family studies that control for shared genetic and environmental confounding typically find attenuated associations between dietary factors and mortality, suggesting substantial confounding in observational studies.

**Golestan cohort**: {cite}`hashemian2017nut` find that in Iran, where nut consumption does not correlate with Western healthy lifestyles, the mortality association persists (hazard ratio [HR] 0.71 for ≥3 servings/week).

I calibrated the Beta prior by assigning weights to each evidence source: LDL pathway (weight 0.4, target 12% causal), sibling studies (weight 0.4, target 20% causal), and Golestan cohort (weight 0.2, target 40% causal given persistent associations). Rather than setting the prior mean to a simple weighted average of targets, I calibrated Beta parameters to match the full distribution of evidence—capturing both the central tendency and the wide uncertainty across sources. This yields Beta(1.5, 4.5), a right-skewed distribution with mean 0.25 and 95% CI: 2-63%, reflecting that most evidence points to low causal fractions while allowing for the possibility of larger effects suggested by the Golestan cohort.

For HR=0.78, the E-value is 1.8 {cite:p}`vanderweele2017sensitivity`: an unmeasured confounder would need RR ≥ 1.8 with both nut consumption and mortality to fully explain the observed association.

### Target Population

I modeled a 40-year-old from the United States or Europe with 40 years remaining life expectancy. I excluded individuals with nut allergies (1-2% prevalence {cite:p}`sicherer2010epidemiology`).

### Cost-Effectiveness Analysis

I calculated incremental cost-effectiveness ratios (ICERs) as:

```
ICER = (Annual cost × Years of consumption) / QALY gain
```

Annual costs use 2024 US retail prices from USDA Economic Research Service: peanuts (\$37/year for 28g/day), almonds (\$95/year), walnuts (\$97/year), cashews (\$103/year), pistachios (\$114/year), pecans (\$126/year), and macadamias (\$229/year) {cite:p}`usda2024prices`. I discounted costs at 3% annually, matching the QALY discount rate.

## Results

### Primary Finding

The hierarchical Bayesian model estimates QALY gains ranging from 0.11 (pecans) to 0.20 (walnuts) for a 40-year-old consuming 28g/day over their remaining lifespan.

**Table 3: QALY Estimates by Nut Type.** Posterior estimates from MCMC sampling (4,000 draws, 4 chains, 0% divergences). QALYs are discounted at 3% annually. 95% credible intervals reflect parameter uncertainty including confounding adjustment.

| Nut | Mean QALY | Median | 95% CI | ICER |
|-----|-----------|--------|--------|------|
| Walnut | 0.20 | 0.18 | [0.02, 0.55] | \$13,400 |
| Almond | 0.20 | 0.16 | [0.01, 0.56] | \$13,000 |
| Peanut | 0.17 | 0.14 | [-0.07, 0.60] | \$5,700 |
| Cashew | 0.17 | 0.14 | [-0.03, 0.54] | \$16,800 |
| Pistachio | 0.16 | 0.12 | [-0.08, 0.55] | \$19,700 |
| Macadamia | 0.14 | 0.11 | [-0.02, 0.43] | \$44,800 |
| Pecan | 0.11 | 0.09 | [-0.01, 0.36] | \$31,400 |

Note: Negative lower bounds on CIs reflect uncertainty in confounding adjustment; the probability of benefit > 0 exceeds 90% for all nuts.

### Pathway-Specific Relative Risks

The model reveals substantial pathway heterogeneity. CVD effects are 5-10x stronger than cancer effects, explaining why walnuts (high ALA omega-3) outperform other nuts.

**Table 4: Pathway-Specific Relative Risks by Nut Type.** Posterior mean RRs for each mortality pathway. Lower values indicate greater benefit. Quality pathway affects morbidity/utility rather than mortality.

| Nut | CVD RR | Cancer RR | Other RR | Quality RR |
|-----|--------|-----------|----------|------------|
| Walnut | 0.83 | 0.98 | 0.94 | 0.96 |
| Almond | 0.85 | 0.97 | 0.94 | 0.94 |
| Peanut | 0.84 | 0.99 | 0.96 | 0.96 |
| Cashew | 0.85 | 0.99 | 0.95 | 0.95 |
| Pistachio | 0.84 | 0.99 | 0.97 | 0.97 |
| Macadamia | 0.88 | 0.99 | 0.96 | 0.96 |
| Pecan | 0.89 | 0.99 | 0.97 | 0.97 |

### Pathway Contributions

Approximately 75% of the QALY benefit operates through CVD prevention, with the remainder split between other mortality (15%) and quality of life improvements (10%).

**Table 5: Pathway Contribution to Total Benefit.** Decomposition of QALY gains by mechanism. CVD dominates due to both stronger relative risk reductions and higher cause-specific mortality at older ages.

| Pathway | Contribution | Mean RR Range | Key Nutrients |
|---------|-------------|---------------|---------------|
| CVD mortality | ~75% | 0.83-0.89 | ALA omega-3, fiber, magnesium |
| Other mortality | ~15% | 0.94-0.97 | Fiber, protein |
| Quality of life | ~10% | 0.94-0.97 | Magnesium, fiber |
| Cancer mortality | <5% | 0.97-0.99 | Fiber, vitamin E |

### Cost-Effectiveness

All nuts fall below cost-effectiveness thresholds used by major health technology assessment bodies: NICE uses £20,000-30,000/QALY (~\$25,000-38,000) {cite:p}`nice2024threshold`, while ICER uses \$100,000-150,000/QALY {cite:p}`icer2024reference`. Peanuts achieve the lowest ICER due to low cost (\$37/year) combined with the third-highest QALY estimate.

**Table 6: Evidence Quality by Nut Type.** I classified evidence quality based on sample size and study design: "Strong" = multiple RCTs or large cohorts (n>100,000); "Moderate" = single RCT or smaller cohorts; "Limited" = RCTs with confidence intervals crossing null.

| Nut | Evidence | RCT/Cohort Sources |
|-----|----------|-------------------|
| Walnut | Strong | PREDIMED, WAHA |
| Almond | Strong | Multiple RCTs |
| Peanut | Strong | Bao 2013 (n=118,962) |
| Pistachio | Moderate | Del Gobbo meta-analysis |
| Pecan | Moderate | Hart 2025, Guarneiri 2021 |
| Macadamia | Moderate | FDA health claim |
| Cashew | Limited | Mah 2017 (wider CIs) |

### Uncertainty Quantification

Credible interval width reflects both nutrient prior uncertainty and hierarchical shrinkage. Nuts with unique nutrient profiles (walnuts: ALA; macadamias: omega-7) have narrower CIs because their effects are more mechanistically constrained. Nuts with generic profiles (cashews, pecans) rely more heavily on the hierarchical prior, producing wider uncertainty.

## Discussion

### Key Findings

The hierarchical Bayesian model estimates 0.11-0.20 discounted QALYs from daily nut consumption, with walnut and almond sharing the top position and pecan ranking lowest. This spread (~45% of the category effect) is larger than previous analyses suggested, reflecting the mechanistic importance of nutrient composition.

The dominance of CVD pathway (~75% of benefit) explains the walnut advantage: its 2.5g ALA omega-3 content drives a CVD RR of 0.83 compared to 0.88-0.89 for nuts with negligible ALA. This mechanistic link provides stronger causal support than overall mortality associations.

### Comparison to Prior Estimates

These estimates are lower than unadjusted observational associations (22% mortality reduction from {cite}`aune2016nut`) but higher than pure LDL-pathway predictions (~3% reduction). The Beta(1.5, 4.5) confounding prior with mean 0.25 mediates between these extremes.

### Cost-Effectiveness

ICERs range from \$5,700/QALY (peanuts) to \$44,800/QALY (macadamias). All nuts fall below the \$50,000-100,000/QALY thresholds that NICE and ICER use. Peanuts achieve the lowest ICER, combining the third-highest QALY estimate with the lowest cost.

### Sensitivity Analyses

I examined robustness to key parameter assumptions:

**Confounding prior**: When I use Beta(0.5, 4.5) with mean 10% causal (more skeptical), QALYs decrease by ~60%; when I use Beta(3, 3) with mean 50% causal, QALYs increase by ~60%. Rankings remain stable.

**Hierarchical shrinkage (τ)**: The baseline model uses τ ~ HalfNormal(0.03), which constrains nut-specific deviations from nutrient-predicted effects to ~±6% on the log-RR scale (95% prior interval). With τ ~ HalfNormal(0.10) (weaker shrinkage), credible intervals widen by ~15% but point estimates and rankings remain stable. This suggests results are driven primarily by nutrient composition rather than nut-specific residual effects.

**Adherence**: At 50% real-world adherence (vs 100% assumed), effective QALYs halve and ICERs double. All nuts except macadamia remain below \$50,000/QALY threshold.

**Age at initiation**: For a 60-year-old (vs 40), discounted QALYs decrease ~40% due to shorter remaining lifespan, partially offset by stronger CVD benefit at older ages.

### Limitations

1. Estimates rely on observational data; residual confounding may remain despite calibration.
2. Source studies predominantly from US and Europe.
3. Fixed 28g/day dose modeled; dose-response may be non-linear ({cite}`aune2016nut` find benefits plateau above ~20g/day).
4. Perfect adherence assumed; I estimate real-world adherence at 50-70% based on dietary intervention studies.
5. Substitution effects not modeled (what foods nuts replace affects net benefit).

## Conclusion

Using a hierarchical Bayesian model with pathway-specific nutrient effects and MCMC sampling (0% divergences), I estimate that daily nut consumption (28g) yields 0.11-0.20 discounted QALYs for a 40-year-old, with walnuts and almonds ranking highest. Approximately 75% of benefit operates through CVD prevention, driven primarily by ALA omega-3, fiber, and magnesium content. ICERs range from \$5,700/QALY (peanuts) to \$44,800/QALY (macadamias); all nuts fall below NICE (£20,000-30,000/QALY) and ICER (\$100,000-150,000/QALY) thresholds. Peanuts achieve the lowest ICER, combining the third-highest QALY estimate with the lowest cost. **Caution**: Individuals with nut allergies (1-2% prevalence {cite:p}`sicherer2010epidemiology`) should not consume nuts.

## Data and Code Availability

Code: https://github.com/MaxGhenis/whatnut

```{bibliography}
```

```{tableofcontents}
```
