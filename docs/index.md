---
kernelspec:
  name: python3
  display_name: Python 3
---

# What Nut? A Monte Carlo analysis of life expectancy from nut consumption

**Max Ghenis**

max@maxghenis.com

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
from whatnut.results import r
```

## Abstract

Observational studies find nut consumption associated with reduced mortality. I present a Monte Carlo uncertainty propagation framework with pathway-specific effects (cardiovascular, cancer, and other mortality), nutrient-derived priors from independent meta-analyses, and evidence-calibrated confounding adjustment. I estimate that for a {eval}`r.target_age`-year-old with {eval}`f"{r.baseline_life_years:.0f}"` baseline remaining life years, consuming 28g/day of nuts over their remaining lifespan yields {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months), with walnuts ({eval}`r.walnut.life_years_fmt` years) ranking highest and cashews ({eval}`r.cashew.life_years_fmt` years) lowest. Approximately {eval}`r.cvd_contribution`% of benefit operates through cardiovascular disease (CVD) prevention, with pathway-specific relative risks of {eval}`r.cvd_effect_range` for CVD versus {eval}`r.cancer_effect_range` for cancer. Incremental cost-effectiveness ratios (ICERs), calculated using standard 3% discounted QALYs, range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.cashew.icer_fmt`/QALY (cashews).

## Introduction

### The nut-mortality association

{cite:t}`fraser1992possible` first linked nut consumption to reduced coronary heart disease risk in the Adventist Health Study over three decades ago. Subsequent prospective cohorts replicated this finding: {cite:t}`ellsworth2001frequent` in the Iowa Women's Health Study, {cite:t}`albert2002nut` in the Physicians' Health Study, and {cite:t}`hu1999nut` in the Nurses' Health Study each found 30-50% reductions in cardiovascular disease (CVD) risk among regular nut consumers.

Three large-scale analyses expanded the evidence base from 3 cohorts to 18 cohorts. {cite:t}`bao2013association` analyzed 118,962 participants from the Nurses' Health Study and Health Professionals Follow-up Study, finding that consuming nuts ≥7 times per week reduced all-cause mortality by 20% (hazard ratio [HR] 0.80, 95% CI: 0.73-0.86). {cite:t}`grosso2015nut` meta-analyzed 354,933 participants across 18 cohorts, estimating a 19% mortality reduction (relative risk [RR] 0.81, 95% CI: 0.77-0.85) for highest versus lowest consumption. {cite:t}`aune2016nut` synthesized 819,448 participants across 15 cohorts, finding that 28g/day of nut consumption reduced all-cause mortality by 22% (RR 0.78, 95% CI: 0.72-0.84). A 2025 update by {cite:t}`liu2025nut`, encompassing 63 prospective cohort studies, confirmed these findings with an all-cause mortality RR of 0.77 (95% CI: 0.73-0.81) and CVD mortality RR of 0.74 (0.70-0.78), while identifying a nonlinear dose-response with benefits plateauing around 15-20 g/day. {cite:t}`liu2021walnut` estimated walnut-specific life expectancy gains of approximately 1.3 years at age 60 in the Nurses' Health Study and Health Professionals Follow-up Study.

### Cause-specific effects

The mortality benefit appears concentrated in cardiovascular causes. {cite}`aune2016nut` find stronger associations for coronary heart disease mortality (RR 0.71, 95% CI: 0.63-0.80) than cancer mortality (RR 0.87, 95% CI: 0.80-0.93). CVD mortality more broadly showed RR 0.79 (0.70-0.88). This pattern aligns with mechanistic studies showing that nuts improve intermediate CVD risk factors: {cite}`delgobbo2015effects` meta-analyzed 61 controlled feeding trials (n=2,582) and found that nut consumption reduces low-density lipoprotein (LDL) cholesterol by 4.8 mg/dL (0.12 mmol/L), with additional improvements in apolipoprotein B and triglycerides. An updated meta-analysis of 113 RCTs by {cite:t}`nishi2025lipid` confirmed nut consumption lowers LDL cholesterol by 0.12 mmol/L (4.6 mg/dL), consistent with the earlier findings.

### The confounding problem

Distinguishing causal effects from confounding remains the primary challenge in nutritional epidemiology. Nut consumers differ from non-consumers across multiple dimensions: {cite:t}`jenab2004associated` find that nut consumers exercise more frequently, smoke less, have higher education and income, and consume more fruits and vegetables. While cohort studies adjust for these measured confounders, unmeasured confounding may persist.

Three lines of evidence inform the causal fraction of observed associations. First, {cite:t}`hashemian2017nut` studied 50,045 adults in the Golestan cohort in northeastern Iran, where nut consumption does not correlate with Western healthy lifestyle patterns. The mortality association persisted (HR 0.71 for ≥3 servings/week), suggesting causal effects independent of healthy-user confounding. Second, sibling-comparison designs that control for shared genetic and environmental factors typically find attenuated—though non-zero—dietary associations. Third, calibrating observed effects against the magnitude predicted from RCT-demonstrated improvements in intermediate outcomes (e.g., LDL cholesterol) suggests that only a fraction of observed associations can be mechanistically explained. A Mendelian randomization study by {cite:t}`wang2025mr` found mostly null associations between genetically predicted nut consumption and CVD outcomes, though Mendelian randomization has well-known power limitations for dietary exposures due to weak genetic instruments.

### Gaps in existing literature

Three limitations motivate this analysis. First, most studies examine "any nuts" as a single category, obscuring compositional differences. Walnuts contain 2.5g of alpha-linolenic acid (ALA) omega-3 per 28g serving; almonds contain none. Macadamias contain 4.7g of palmitoleic acid (omega-7); other nuts contain negligible amounts. These differences may translate to differential health effects.

Second, relative risk reductions do not directly map to absolute benefits. A 22% mortality reduction translates to different absolute life expectancy gains depending on baseline mortality risk, age distribution of benefits, and cause-specific mortality patterns.

Third, no existing study quantifies absolute life expectancy gains from nut consumption. While {cite:t}`fadnes2022estimating` modeled life expectancy gains from dietary changes broadly, no study has provided nut-specific estimates with uncertainty quantification. Health policy requires standardized metrics for resource allocation; quality-adjusted life years (QALYs) enable comparison across interventions. The UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE (World Health Organization CHOosing Interventions that are Cost-Effective) use QALYs in cost-effectiveness analyses.

### Contribution

This paper develops a Monte Carlo uncertainty propagation framework for estimating life expectancy gains from nut consumption, addressing: (1) expected benefit magnitude in absolute terms (life years); (2) nut type comparisons based on compositional differences; (3) explicit treatment of confounding uncertainty calibrated to multiple evidence sources. QALYs are computed for cost-effectiveness comparison with other health interventions. Throughout this paper, "nuts" refers to tree nuts plus peanuts (a legume), following epidemiological convention.

### A note on metrics

This paper reports **life years gained** ({eval}`r.life_years_range` years, or {eval}`r.months_range` months) as the primary metric—representing the actual expected increase in lifespan from daily nut consumption. This is more intuitive for individual decision-making ("how much longer will I live?").

For cost-effectiveness comparison with other health interventions, I also report **QALYs** (quality-adjusted life years), which weight life years by age-specific quality of life using population EuroQol 5-Dimension (EQ-5D) norms. I present both undiscounted QALYs and discounted QALYs (3% annually, following NICE/ICER/WHO-CHOICE guidelines). Note that this analysis models only **mortality effects**—potential morbidity benefits (e.g., fewer non-fatal CVD events, improved cognitive function) are not included, making these QALY estimates conservative.

## Methods

### Evidence sources

I constructed a hierarchical evidence base drawing on four categories of sources, in order of priority. Meta-analyses of mortality outcomes from {cite:t}`aune2016nut` and {cite:t}`grosso2015nut` provide pooled estimates for all-cause mortality. Large prospective cohort studies, including {cite:t}`bao2013association` and {cite:t}`guasch2017nut`, provide nut-specific associations. Randomized controlled trials—{cite:t}`ros2008mediterranean` (Prevención con Dieta Mediterránea [PREDIMED]), {cite:t}`rajaram2021walnuts` (Walnuts and Healthy Aging [WAHA]), {cite:t}`delgobbo2015effects`, {cite:t}`hart2025pecan`, {cite:t}`guarneiri2021pecan`, and {cite:t}`mah2017cashew`—inform nut-specific adjustment factors. Nutrient composition data from {cite:t}`usda2024fooddata` provides standardized nutrient profiles.

### Nut nutrient profiles

Nuts vary in macronutrient and micronutrient composition {cite:p}`usda2024fooddata`. All contain 12-22g fat per 28g serving, but differ in fatty acid profiles (monounsaturated vs. polyunsaturated), micronutrient content, and caloric density (157-204 kcal per serving).

**Table 1: Nut nutrient profiles.** Macronutrients and key micronutrients per 28g serving. ALA = alpha-linolenic acid (plant-based omega-3 fatty acid); MUFA = monounsaturated fatty acids; PUFA = polyunsaturated fatty acids. Values from USDA FoodData Central SR Legacy database, accessed December 2024.

| Nut | FDC ID | kcal | Fat (g) | MUFA | PUFA | ALA (g) | Fiber (g) | Protein (g) | Notable |
|-----|--------|------|---------|------|------|---------|-----------|-------------|---------|
| Walnut | [170187](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170187/nutrients) | 185 | 18.5 | 2.5 | 13.4 | 2.5 | 1.9 | 4.3 | Highest omega-3 |
| Almond | [170567](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170567/nutrients) | 164 | 14.2 | 9.0 | 3.5 | 0.0 | 3.5 | 6.0 | Highest vitamin E (7.3mg) |
| Pistachio | [170184](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170184/nutrients) | 159 | 12.8 | 6.8 | 3.8 | 0.1 | 2.9 | 5.7 | Lutein (342μg) |
| Pecan | [170182](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170182/nutrients) | 196 | 20.4 | 11.6 | 6.1 | 0.3 | 2.7 | 2.6 | High MUFA |
| Macadamia | [170178](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170178/nutrients) | 204 | 21.5 | 16.7 | 0.4 | 0.1 | 2.4 | 2.2 | Omega-7 (4.7g) |
| Peanut | [172430](https://fdc.nal.usda.gov/fdc-app.html#/food-details/172430/nutrients) | 161 | 14.0 | 6.9 | 4.4 | 0.0 | 2.4 | 7.3 | Highest protein |
| Cashew | [170162](https://fdc.nal.usda.gov/fdc-app.html#/food-details/170162/nutrients) | 157 | 12.4 | 6.7 | 2.2 | 0.0 | 0.9 | 5.2 | Lowest fat/fiber |

Walnuts have the highest ALA omega-3 content (2.5g/28g), comprising 73% of total fat as polyunsaturated fatty acids. ALA is a precursor to eicosapentaenoic acid (EPA) and docosahexaenoic acid (DHA) {cite:p}`ros2008mediterranean`. Almonds have the highest vitamin E content (7.3mg/28g, 49% DV) and highest fiber content among tree nuts (3.5g/28g). Macadamias are the only common nut with substantial omega-7 fatty acids (palmitoleic acid, 4.7g/28g); they also have the highest caloric density (204 kcal) and saturated fat content (3.4g). Peanuts (technically legumes) have the highest protein content (7.3g/28g) and lowest cost; aflatoxin contamination occurs in some regions, particularly sub-Saharan Africa and Southeast Asia {cite:p}`williams2004aflatoxin`.

**Note on Brazil nuts**: Brazil nuts are excluded from this analysis. Daily consumption of a standard 28g serving would provide approximately 544 ug of selenium, exceeding the tolerable upper intake level for selenium (400 ug/day) established by the Institute of Medicine, precluding inclusion in a daily-consumption model.

### Statistical model

I implemented a Monte Carlo uncertainty propagation model with hierarchical structure and non-centered parameterization. The model samples from nutrient-derived priors (no likelihood function or outcome data) and propagates uncertainty through a lifecycle model to estimate life expectancy gains.

```{figure} _static/figures/model_architecture.png
:name: fig-architecture
:width: 100%

**Figure 1: Model architecture.** The model transforms nut composition into life expectancy estimates through four stages: (1) **Nutrients** from USDA data define each nut's profile; (2) **Pathway effects** translate nutrients into CVD, cancer, and other mortality reductions using meta-analysis priors; (3) **Confounding adjustment** accounts for observational study limitations; (4) **Lifecycle integration** converts relative risks to absolute life years using CDC mortality tables. Technical details (non-centered parameterization, Monte Carlo uncertainty propagation) are described in the Methods text.
```

**Note on model structure**: This is an **evidence synthesis model** that propagates uncertainty from multiple prior sources (nutrient effect estimates, nut-specific RCT residuals, confounding calibration) through to life expectancy estimates. Unlike traditional Bayesian analyses that update beliefs from outcome data via a likelihood function, this model synthesizes prior information without a likelihood linking to mortality observations. The output distributions represent **propagated prior uncertainty** — the range of plausible life expectancy gains given current evidence — not posterior distributions from data-driven updating. This approach is appropriate because the goal is uncertainty quantification from existing evidence synthesis, not parameter estimation from a novel dataset. Throughout this paper, I use "uncertainty interval" rather than "posterior" to avoid implying data-driven updating where none occurs.

#### Pathway-specific effects

The model estimates separate relative risks for three mortality pathways. CVD mortality shows the largest effects (RR {eval}`r.cvd_effect_range`), informed by ALA omega-3, fiber, and magnesium priors. Cancer mortality shows smaller effects (RR {eval}`r.cancer_effect_range`), informed by fiber and vitamin E priors. Other mortality shows intermediate effects, representing a composite of remaining causes. This decomposition allows different nutrients to contribute differentially to each pathway—for example, ALA omega-3 strongly affects CVD but has negligible cancer effects, while fiber contributes to both.

I do not model a separate morbidity pathway. While nuts may improve quality of life through reduced non-fatal CVD events, improved cognitive function, and other morbidity effects, this analysis focuses solely on mortality. QALYs are computed by weighting mortality-based life expectancy gains by population EQ-5D norms (age-specific quality weights), not by modeling nut-specific quality improvements. This makes the estimates conservative—actual benefits may be larger if nuts reduce morbidity beyond their mortality effects.

#### Nutrient-derived priors

Rather than specifying nut-specific effects directly, I derived expected effects from nutrient composition using priors from independent meta-analyses:

**Table 2: Nutrient-pathway effect priors.** Log-relative risk per unit nutrient, with pathway-specific coefficients. Priors from meta-analyses of prospective cohort studies and randomized trials. For nutrients with limited direct evidence, I use wide priors (SD ≥50% of mean) reflecting mechanistic plausibility with high uncertainty.

| Nutrient | CVD Effect | Cancer Effect | Other Effect | Source |
|----------|------------|---------------|--------------|--------|
| ALA omega-3 (per g) | -0.05 (0.03) | 0.00 (0.03) | -0.05 (0.04) | {cite}`naghshi2021ala` |
| Fiber (per g) | -0.015 (0.005) | -0.01 (0.004) | -0.012 (0.005) | {cite}`threapleton2013fiber` |
| Omega-6 (per g) | -0.005 (0.003) | +0.002 (0.005) | -0.002 (0.003) | {cite}`farvid2014omega6` |
| Omega-7 (per g) | -0.03 (0.04) | 0.00 (0.02) | -0.02 (0.03) | Mechanistic (wide prior) |
| Saturated fat (per g) | +0.025 (0.01) | +0.005 (0.008) | +0.01 (0.01) | {cite}`sacks2017sat` |
| Magnesium (per mg)† | -0.001 (0.0004) | -0.0001 (0.0002) | -0.0002 (0.0001) | {cite}`fang2016mg` |
| Arginine (per 100mg) | -0.002 (0.002) | 0.00 (0.001) | -0.001 (0.002) | Mechanistic (wide prior) |
| Vitamin E (per mg) | -0.005 (0.008) | -0.008 (0.01) | -0.003 (0.005) | Food-based (see note)† |
| Phytosterols (per mg)† | -0.0001 (0.0002) | 0.00 (0.00005) | 0.00 (0.00003) | Mechanistic (wide prior) |
| Protein (per g) | 0.00 (0.005) | 0.00 (0.003) | -0.005 (0.005) | Mechanistic (wide prior) |

†Magnesium and phytosterol priors are specified per mg. Magnesium derived from Fang 2016 (RR 0.90 per 100mg, ln(0.90)/100 = -0.00105/mg); phytosterol derived from LDL-lowering mechanism (-0.001 per 10mg = -0.0001 per mg).

††Vitamin E: RCTs of high-dose supplements (SELECT, HOPE-TOO) found null or harmful effects, but these tested pharmacological doses (400-800 IU/day) far exceeding food-based intake. The vitamin E prior reflects food-matrix effects at nutritional doses (7mg from almonds vs 400mg from supplements), with wide uncertainty (SD = 100% of mean for cancer) to account for conflicting evidence. Dropping vitamin E from the model changes walnut QALYs by <2%.

```{figure} _static/figures/nutrient_contributions.png
:name: fig-nutrients
:width: 90%

**Figure 2: Nutrient contributions to CVD mortality reduction.** Heatmap showing how each nutrient contributes to the CVD pathway effect for each nut type. ALA omega-3 is the dominant driver for walnuts (highest contribution), while fiber and magnesium contribute more evenly across nuts. Negative values indicate harmful effects (e.g., saturated fat).
```

#### Hierarchical structure

I model nut-specific effects as deviations from nutrient-predicted effects using non-centered parameterization. Let $z_{\text{pathway}} \sim \mathcal{N}(0, 1)$ represent standardized deviations and $\tau_{\text{pathway}} \sim \text{HalfNormal}(0.03)$ represent the shrinkage prior. The scale 0.03 reflects an expectation that nut-specific deviations are small (±6% on log-RR scale at 2 SD), since nutrients explain most compositional variation; sensitivity analysis with $\tau \sim \text{HalfNormal}(0.10)$ shows robust results. The true effect for each nut-pathway combination is then $\theta_{\text{true}} = \theta_{\text{nutrients}} + \tau_{\text{pathway}} \cdot z_{\text{pathway}}$. This parameterization ensures appropriate hierarchical shrinkage, pulling nut-specific deviations toward nutrient-predicted effects when evidence is limited.

Prior predictive checks confirm these priors generate plausible ranges: sampling from nutrient priors yields all-cause RRs spanning 0.72-0.92 across nuts (95% interval), consistent with the meta-analytic range of 0.72-0.84 {cite:p}`aune2016nut`.

#### Confounding adjustment

The model includes a causal fraction parameter with Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior (mean {eval}`r.confounding_mean`, 95% interval: {eval}`r.confounding_ci_lower`-{eval}`r.confounding_ci_upper`), calibrated to three evidence sources (see Confounding Calibration section below).

#### Lifecycle integration

I propagate Monte Carlo samples of pathway-specific relative risks through a lifecycle model using CDC life tables for age-specific mortality, age-varying cause fractions (CVD increases from 20% at age 40 to 40% at age 80), quality weights from EQ-5D population norms (mean 0.85) {cite:p}`sullivan2006catalogue`, and 3% annual discounting.

```{figure} _static/figures/cause_fractions.png
:name: fig-cause-fractions
:width: 85%

**Figure 3: Age-varying cause-of-death fractions.** The proportion of deaths attributable to CVD increases with age (from ~20% at age 40 to ~40% at age 90), while cancer peaks in middle age. This age structure means CVD mortality reductions have larger absolute effects at older ages, when most remaining life years are realized.
```

### Confounding calibration

The source meta-analyses adjusted for measured confounders (age, sex, body mass index [BMI], smoking, alcohol, physical activity). This section addresses what fraction of the *residual* association—after these adjustments—reflects causal effects versus unmeasured confounding.

**LDL pathway**: {cite}`delgobbo2015effects` find that nuts reduce LDL cholesterol by 4.8 mg/dL per serving in 61 RCTs. This predicts ~3% CVD mortality reduction via established dose-response relationships, compared to ~25% observed in cohorts. However, this 12% "mechanism explanation" represents only one of several causal pathways. Nuts also reduce blood pressure (~1-3 mmHg), improve glycemic control, provide anti-inflammatory omega-3 fatty acids, and deliver antioxidants and fiber {cite:p}`ros2008mediterranean`. The LDL pathway therefore provides a *floor* on the causal fraction, not a ceiling.

**Sibling comparison evidence**: Within-family designs control for shared genetic and environmental confounding {cite:p}`frisell2012sibling`. If sibling-controlled estimates are 30-50% smaller than unpaired estimates, this implies 50-70% of the association survives sibling control—suggesting a causal fraction in that range for dietary factors generally. However, no sibling studies exist specifically for nut consumption, and sibling designs may over-adjust by removing non-confounding shared factors.

**Golestan cohort**: {cite}`hashemian2017nut` studied nut consumption in Iran, where nut consumers were *more* likely to smoke and be obese (the opposite of Western cohorts). Their adjusted HR of 0.71 represents a *larger effect magnitude* (29% mortality reduction) than {cite:t}`aune2016nut`'s Western estimate of 0.78 (22% reduction). This pattern is consistent with a causal effect and suggests healthy-user confounding in Western cohorts does not grossly inflate observed associations. However, alternative explanations exist: the larger effect in Golestan may reflect (1) higher baseline CVD risk in that population (where relative effects are expected to be larger), (2) compositional differences in nut types consumed (more pistachios and walnuts in Iran), or (3) different residual confounding structures. The Golestan evidence supports a causal fraction of at least 50-100% of the adjusted Western effect, but does not precisely quantify it.

**E-value analysis**: Using VanderWeele's method {cite:p}`vanderweele2017sensitivity`, the E-value for HR=0.78 is {eval}`r.e_value`. An unmeasured confounder would need associations of RR ≥ {eval}`r.e_value` with both nut consumption and mortality to fully explain the observed effect. For context: exercise-mortality RR ≈ 1.5-2.0; income-mortality RR ≈ 1.3-1.5. An E-value of {eval}`r.e_value` suggests moderate residual confounding is plausible but unlikely to explain the entire association.

**Prior specification**: Synthesizing this evidence, I adopt a Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior—a **symmetric, weakly informative prior** with mean {eval}`r.confounding_mean` and 95% CI: {eval}`int(r.confounding_ci_lower * 100)`-{eval}`int(r.confounding_ci_upper * 100)`%. This prior reflects genuine uncertainty rather than a precise calibration: the evidence sources above provide qualitative guidance (LDL floor ~12%, sibling attenuation 50-70%, Golestan suggesting ≥100%), but no formal mapping to prior parameters is possible. The symmetric Beta(2.5, 2.5) represents an agnostic stance—substantial probability mass on both low (25%) and high (75%) causal fractions. Sensitivity analysis with skeptical (mean 0.25) and optimistic (mean 0.75) priors is presented in the Discussion; rankings remain stable across specifications.

```{figure} _static/figures/confounding_calibration.png
:name: fig-confounding
:width: 90%

**Figure 4: Confounding calibration.** Evidence synthesis for the causal fraction prior. The Golestan cohort (HR 0.71) shows effects larger than Western meta-analyses (HR 0.78), suggesting healthy-user bias in Western data is minimal. The Beta(2.5, 2.5) prior reflects symmetric uncertainty around a 50% causal fraction.
```

### Target population

I modeled a {eval}`r.target_age`-year-old from the United States or Europe with {eval}`f"{r.baseline_life_years:.0f}"` years remaining life expectancy. I excluded individuals with nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% prevalence, with peanut allergy alone affecting ~3% of US adults {cite:p}`gupta2021prevalence`).

### Cost-effectiveness analysis

I calculated incremental cost-effectiveness ratios (ICERs) as $\text{ICER} = \frac{\text{Annual cost} \times \text{Years of consumption}}{\text{QALY gain}}$. Annual costs use 2024 US retail prices from USDA Economic Research Service: peanuts (\$37/year for 28g/day), almonds (\$95/year), walnuts (\$97/year), cashews (\$103/year), pistachios (\$114/year), pecans (\$126/year), and macadamias (\$229/year) {cite:p}`usda2024prices`. I discounted costs at 3% annually, matching the QALY discount rate.

## Results

### Consistency validation

As a consistency check, I verified that the model's implied all-cause mortality hazard ratio matches the source meta-analysis. Weighting pathway-specific RRs by cause-specific mortality fractions yields an implied all-cause HR consistent with {cite:t}`aune2016nut`'s estimate of 0.78 (95% CI: 0.72-0.84). This confirms the pathway decomposition preserves the overall effect magnitude.

### Predictive checks

I verified that individual Monte Carlo draws produce scientifically plausible outcomes. All {eval}`r.n_samples` samples yield pathway-specific RRs within a plausible range, with no draws producing implausible values (RR > 1.5 or RR < 0.5). All sampled QALYs fall within plausible ranges consistent with the maximum possible benefit given remaining life expectancy; negative values (reflecting uncertainty about harm) occur in a small fraction of draws. CVD, cancer, and other mortality contributions sum to approximately 100% across all draws, confirming the decomposition is internally consistent. These checks confirm the model produces valid predictions across the full sampled distribution, not just at the mean.

### Primary finding

The model estimates that a {eval}`r.target_age`-year-old consuming 28g/day of nuts over their remaining lifespan gains {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months), with walnuts ({eval}`r.walnut.life_years_fmt` years) ranking highest and cashews ({eval}`r.cashew.life_years_fmt` years) lowest. Approximately {eval}`r.cvd_contribution`% of this benefit operates through CVD mortality prevention.

```{figure} _static/figures/forest_plot.png
:name: fig-forest
:width: 90%

**Figure 5: Life years gained by nut type.** Forest plot showing mean life years gained with 95% uncertainty intervals. Walnuts rank highest due to ALA omega-3 content combined with favorable pathway adjustments; cashews rank lowest. For most nut types, the 95% uncertainty interval excludes zero.
```

**Table 3: Life year and QALY estimates by nut type.** Monte Carlo estimates ({eval}`r.n_samples` samples, seed={eval}`r.seed`). Life years (LY) are the primary metric. QALYs weight life years by age-specific quality of life; both undiscounted and discounted (3% annually) QALYs are shown. P(>0) = probability of positive benefit. 95% uncertainty intervals reflect parameter uncertainty including confounding adjustment.

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.table_3_qalys())
```

Note: "Dominated" indicates ICER undefined when lower CI bound for QALYs is ≤0. Evidence quality: Strong = multiple RCTs or large cohorts (n>100,000); Moderate = single RCT or smaller cohorts; Limited = RCTs with confidence intervals crossing null.

### Age-stratified results

The base case models a 40-year-old. Benefits decrease with age due to shorter remaining lifespan, partially offset by higher CVD mortality fractions at older ages. Table 3b shows how life years gained varies by age at initiation:

**Table 3b: Life years gained by age at initiation.** Walnuts shown as representative. Benefits decrease with age due to shorter remaining lifespan.

| Age | Remaining Life Expectancy | Life Years Gained | Months Gained | % of Base Case |
|-----|---------------------------|-------------------|---------------|----------------|
| 40 | 40 years | 0.96 | 11.5 | 100% |
| 50 | 31 years | 0.91 | 10.9 | 95% |
| 60 | 22 years | 0.84 | 10.1 | 88% |
| 70 | 15 years | 0.74 | 8.9 | 77% |

Benefits decrease by approximately 5-23% across the 40-70 age range because higher CVD mortality fractions at older ages partially offset shorter remaining lifespan. For a 60-year-old, the estimated benefit is approximately 10 months for walnuts.

### Adherence scenarios

The base case assumes 100% adherence. Real-world dietary adherence is typically 50-70% {cite:p}`appel2006adherence`. Table 3c shows life years under realistic adherence:

**Table 3c: Life years by adherence level.** Walnuts shown as representative. Benefits scale proportionally with adherence.

| Adherence | Life Years | Months | ICER |
|-----------|------------|--------|------|
| 100% (base) | 0.96 | 11.5 | $13,115/QALY |
| 70% (realistic) | 0.67 | 8.1 | $18,736/QALY |
| 50% (conservative) | 0.48 | 5.8 | $26,230/QALY |

At 50% adherence (~3.5 servings/week), the model estimates approximately 6 months of additional life expectancy for walnuts, with an ICER of ~$26,000/QALY, which falls below the $50,000/QALY threshold.

### Pathway-specific relative risks

CVD effects are 5-10x larger than cancer effects (17% vs 2% mortality reduction), which explains why walnuts (high ALA omega-3) rank highest among the nuts analyzed.

**Table 4: Pathway-specific relative risks by nut type.** Mean RRs for each mortality pathway. Lower values indicate greater benefit.

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.table_4_pathway_rrs())
```

```{figure} _static/figures/pathway_rrs.png
:name: fig-pathway-rrs
:width: 90%

**Figure 6: Pathway-specific mortality reductions.** Bar chart comparing relative risk reductions (1-RR) across mortality pathways for each nut. CVD effects dominate cancer effects, explaining why ALA-rich walnuts and almonds rank higher than other nuts. Error bars represent sampling uncertainty.
```

### Pathway contributions

Approximately {eval}`r.cvd_contribution`% of the QALY benefit operates through CVD prevention, with the remainder split between other mortality ({eval}`r.other_contribution`%) and cancer mortality ({eval}`r.cancer_contribution`%).

**Table 5: Pathway contribution to total benefit.** Decomposition of QALY gains by mortality pathway. CVD dominates due to both stronger relative risk reductions and higher cause-specific mortality at older ages.

| Pathway | Contribution | Mean RR Range | Key Nutrients |
|---------|-------------|---------------|---------------|
| CVD mortality | ~{eval}`r.cvd_contribution`% | {eval}`r.cvd_effect_range` | ALA omega-3, fiber, magnesium |
| Other mortality | ~{eval}`r.other_contribution`% | 0.90-0.98 | Fiber, protein |
| Cancer mortality | ~{eval}`r.cancer_contribution`% | {eval}`r.cancer_effect_range` | Fiber, vitamin E |

### Cost-effectiveness

As of December 2025, NICE raised its thresholds to £25,000-35,000/QALY (\$33,500-47,000 at current exchange rates {cite:p}`tradingeconomics2025gbpusd`), with interventions below £25,000 falling below the lower threshold {cite:p}`nice2025threshold`. ICER evaluates interventions at \$50,000, \$100,000, and \$150,000/QALY benchmarks {cite:p}`icer2024reference`. Four nuts (peanuts, walnuts, almonds, pistachios) fall below both NICE's new £25,000/QALY threshold and ICER's \$50,000/QALY benchmark. Macadamias and pecans fall between these thresholds, while cashews exceed \$50,000/QALY due to limited evidence and higher uncertainty. Peanuts achieve the lowest ICER due to low cost (\$37/year) combined with a CVD mortality RR of {eval}`r.cvd_effect_range`.

```{figure} _static/figures/icer_comparison.png
:name: fig-icer
:width: 90%

**Figure 7: Cost-effectiveness by nut type.** Incremental cost-effectiveness ratios (ICERs) compared to standard thresholds. Four nuts (peanuts, walnuts, almonds, pistachios) fall below both NICE (£25,000/QALY) and ICER (\$50,000/QALY) benchmarks; cashews and pecans exceed \$50,000/QALY. Peanuts achieve the lowest ICER due to low cost; cashews rank highest due to limited evidence.
```

### Comparison to other health interventions

To contextualize these estimates, Table 6 compares nut consumption to other evidence-based longevity interventions:

**Table 6: Comparative cost-effectiveness.** Life years gained and ICERs for common health interventions. Nut estimates from this analysis; comparator estimates from published meta-analyses and cost-effectiveness studies as cited. Exercise and Mediterranean diet estimates derive from observational associations and may overstate causal effects.

| Intervention | Life Years | ICER | Evidence Quality |
|--------------|------------|------|------------------|
| **Nuts (walnuts, 40yo)** | 0.96 | $13,115/QALY | Meta-analyses + RCTs |
| Regular exercise (150 min/week) | 3-5 | $0-500/year | Strong RCT evidence |
| Mediterranean diet adherence | 1-2 | Variable | {cite:t}`estruch2018primary`, cohorts |
| Smoking cessation (at 40) | 7-10 | Cost-saving | Strong cohort evidence |
| Statin therapy (primary prev.) | 0.5-1 | $10,000-50,000/QALY | RCTs (low-risk) |
| Blood pressure control | 1-2 | $5,000-20,000/QALY | RCTs |

The model estimates {eval}`r.months_range` months of life expectancy gain from nut consumption at ICERs of {eval}`r.icer_range`/QALY. Exercise (3-5 life years) and smoking cessation (7-10 life years) yield larger absolute gains; most nut types fall below the $50,000/QALY threshold used by ICER, though cashews and pecans exceed this benchmark.

### Uncertainty quantification

Uncertainty interval width reflects both nutrient prior uncertainty and hierarchical shrinkage. Nuts with unique nutrient profiles (walnuts: ALA; macadamias: omega-7) have narrower uncertainty intervals because their effects are more mechanistically constrained. Nuts with generic profiles (cashews, pecans) rely more heavily on the hierarchical prior, producing wider uncertainty.

## Discussion

### Key findings

The model estimates {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months) from daily nut consumption, with walnuts ranking highest ({eval}`r.walnut.life_years_fmt` years) and cashews lowest ({eval}`r.cashew.life_years_fmt` years). This 6-fold spread reflects both nutrient composition differences and nut-specific pathway adjustments derived from RCT residual effects.

The CVD pathway accounts for approximately {eval}`r.cvd_contribution`% of benefit, with other mortality contributing {eval}`r.other_contribution`% and cancer {eval}`r.cancer_contribution`%. The difference between walnuts and other nuts reflects both high ALA omega-3 content and a 1.25 CVD pathway adjustment derived from PREDIMED and WAHA RCT residual effects. This mechanistic link provides stronger causal support than overall mortality associations.

### Comparison to prior estimates

These estimates are lower than unadjusted observational associations (22% mortality reduction from {cite}`aune2016nut`) but higher than pure LDL-pathway predictions (~3% reduction). The Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) confounding prior with mean {eval}`r.confounding_mean` mediates between these extremes. Supporting a causal interpretation, {cite:t}`liu2020changes` found that within-person increases in nut consumption of 0.5 servings/day were associated with 8% lower CVD risk (RR 0.92, 95% CI: 0.86-0.98), while decreases were associated with higher risk. However, {cite:t}`shin2024korea` found no significant CVD-specific mortality reduction in a Korean cohort of 114,140 participants, suggesting the CVD-specific association may be population-dependent.

### Cost-effectiveness

ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.cashew.icer_fmt`/QALY (cashews). Four nuts (peanuts, walnuts, almonds, pistachios) fall below both NICE's new £{eval}`f'{r.nice_lower_gbp:,}'`/QALY (\${eval}`f'{r.nice_lower_usd:,}'`) threshold and ICER's \${eval}`f'{r.icer_threshold:,}'`/QALY benchmark. Pecans and cashews exceed at least one threshold. Peanuts achieve the lowest ICER, combining low cost with a CVD mortality RR of {eval}`r.cvd_effect_range`.

### Sensitivity analyses

I examined robustness to key parameter assumptions:

**Confounding prior**: The model uses a Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior with mean {eval}`r.confounding_mean`. Since the model has no likelihood function linking to outcome data (it synthesizes prior information only), the confounding fraction is sampled directly from the prior. This is appropriate because the goal is to quantify uncertainty about causal effects given current evidence, not to update beliefs from new data. Table 7 shows sensitivity to alternative prior specifications:

**Table 7: Sensitivity to confounding prior.** QALY estimates under alternative confounding assumptions. Rankings remain stable across specifications.

| Prior | Mean | Interpretation | Walnut QALY | Peanut QALY | Change |
|-------|------|----------------|-------------|-------------|--------|
| Beta(1.5, 4.5) | 25% | Skeptical | 0.10 | 0.04 | -47% |
| **Beta(2.5, 2.5)** | **50%** | **Base case** | **{eval}`r.walnut.qaly`** | **{eval}`r.peanut.qaly`** | **—** |
| Beta(3, 1) | 75% | Optimistic | 0.28 | 0.12 | +47% |
| Beta(9, 1) | 90% | Very optimistic | 0.33 | 0.14 | +74% |

**Hierarchical shrinkage (τ)**: The baseline model uses τ ~ HalfNormal(0.03), which constrains nut-specific deviations from nutrient-predicted effects to ~±6% on the log-RR scale (95% prior interval). With τ ~ HalfNormal(0.10) (weaker shrinkage), uncertainty intervals widen by ~15% but point estimates and rankings remain stable. This suggests results are driven primarily by nutrient composition rather than nut-specific residual effects.

**Adherence**: The base case assumes 100% adherence over the remaining lifespan. Dietary intervention trials typically achieve 50-70% long-term adherence {cite:p}`appel2006adherence`. At 70% adherence, effective life years decrease proportionally (e.g., walnut from {eval}`r.walnut.life_years_fmt` to {eval}`f'{r.walnut.life_years * 0.7:.2f}'` years) and ICERs increase by ~43%. At 50% adherence, life years halve and ICERs double. All nuts remain below \$50,000/QALY at 50% adherence. Estimates scale linearly with adherence fraction.

**Age at initiation**: For a 60-year-old (vs 40), discounted QALYs decrease ~40% due to shorter remaining lifespan, partially offset by stronger CVD benefit at older ages.

**Dose-response**: The base case models 28g/day (one ounce), the standard serving size. {cite:t}`aune2016nut` find benefits plateau above ~20g/day. At 20g/day (70% of standard serving), estimated QALYs are approximately 90% of the 28g estimates, while costs decrease by 30%, yielding an approximately 20% lower ICER, though the dose-response evidence remains uncertain.

### Substitution effects

The model treats nut consumption as additive to baseline diet, but in practice nuts replace other foods. The net health impact depends on what is displaced. Replacing refined carbohydrates (chips, crackers) would yield the largest incremental benefit, as nuts provide fiber, unsaturated fats, and micronutrients absent from processed snacks; this substitution pattern likely underlies the cohort associations, as snack replacement is the most common use case. Replacing other sources of healthy fats (olive oil, fatty fish) would yield smaller or negligible incremental benefit, since these foods share similar fatty acid profiles and cardioprotective effects. Replacing red meat would yield an intermediate benefit from reduced saturated fat and heme iron intake, partially offset by lower protein bioavailability.

{cite:t}`li2015substitution` modeled isocaloric substitution in the Nurses' Health Study and found that replacing one serving of red meat with nuts reduced all-cause mortality by 19%, while replacing fish showed no significant change. These substitution patterns suggest the QALY estimates in this paper are most applicable when nuts replace less healthy alternatives—the realistic scenario for most consumers adding nuts to their diet.

### Practical interpretation of estimates

Among the seven nut types analyzed, the model estimates the largest life expectancy gains for walnuts ({eval}`r.walnut.life_years_fmt` years) and almonds, while peanuts yield the lowest ICER ({eval}`r.peanut.icer_fmt`/QALY). Because nutrient effects are approximately additive across the profiles examined, combining nut types would be expected to produce intermediate estimates.

The model assumes 28g/day (one ounce), the standard serving size. Dose-response evidence from {cite:t}`aune2016nut` and {cite:t}`liu2025nut` suggests benefits may plateau above 15-20 g/day, such that the marginal gain from 20g to 28g may be smaller than from 0g to 20g. The modeled nutrients (fatty acids, fiber, minerals) are unaffected by roasting method.

Daily consumption of a standard 28g serving of Brazil nuts would provide approximately 544 ug of selenium, exceeding the tolerable upper intake level (400 ug/day), precluding inclusion in this analysis. For peanuts, US and EU regulatory limits (20 ppb) and routine testing make aflatoxin exposure negligible in these markets {cite:p}`wu2010aflatoxin`; this may not hold in regions with less stringent regulatory frameworks.

At 70% adherence (approximately five servings per week), the model estimates approximately 8 months of additional life expectancy for walnuts, with proportionally scaled ICERs remaining below the $50,000/QALY threshold.

### Limitations

Several limitations warrant consideration. First, this analysis models only **mortality effects**—potential morbidity benefits from nuts (fewer non-fatal strokes and heart attacks, improved metabolic markers, better cognitive function) are not captured. The QALY estimates are therefore conservative; actual quality-adjusted benefits may be larger.

Second, estimates rely on observational data, and residual confounding may remain despite calibration. Source studies come predominantly from the US and Europe, limiting generalizability to other populations. I modeled a fixed 28g/day dose, though dose-response may be non-linear—{cite:t}`aune2016nut` find benefits plateau above ~20g/day. The model assumes perfect adherence, whereas dietary intervention studies find real-world adherence of 50-70% {cite:p}`appel2006adherence`.

## Conclusion

Using Monte Carlo uncertainty propagation with pathway-specific nutrient effects, I estimate that daily nut consumption (28g) yields {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months) for a {eval}`r.target_age`-year-old, with walnuts ranking highest followed by almonds. Approximately {eval}`r.cvd_contribution`% of benefit operates through CVD prevention, driven primarily by ALA omega-3, fiber, and magnesium content. For cost-effectiveness comparison, ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias), all below NICE and ICER thresholds. These estimates reflect mortality effects only; potential morbidity benefits (reduced non-fatal CVD events, improved cognitive function) would increase actual QALYs. Findings do not apply to individuals with nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% of adults {cite:p}`gupta2021prevalence`).

## Data and code availability

**Code**: https://github.com/MaxGhenis/whatnut (MIT License)

**Data sources**: Nutrient composition data are from the USDA FoodData Central SR Legacy database (https://fdc.nal.usda.gov/), with FDC IDs for each nut provided in Table 1. Mortality rates are from the CDC National Vital Statistics System, United States Life Tables 2021 (https://www.cdc.gov/nchs/nvss/life-expectancy.htm). Nut prices are from the USDA Economic Research Service, Food Prices and Spending (https://www.ers.usda.gov/data-products/food-prices/). Quality-of-life weights are from Sullivan & Ghushchyan (2006) EuroQol 5-Dimension (EQ-5D) US population norms.

**Reproducibility**: All paper values are generated by `python -m whatnut.pipeline --generate` (seed=42) and loaded from `src/whatnut/data/results.json` via `src/whatnut/results.py`.

```{bibliography}
```

```{tableofcontents}
```
