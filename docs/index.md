---
kernelspec:
  name: python3
  display_name: Python 3
---

# What Nut? A Bayesian Analysis of Life Expectancy from Nut Consumption

**Max Ghenis**

max@maxghenis.com

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
from whatnut.paper_results import r
```

## Abstract

Observational studies find nut consumption associated with reduced mortality. I present a hierarchical Bayesian framework with pathway-specific effects (cardiovascular, cancer, and other mortality), nutrient-derived priors from independent meta-analyses, and evidence-calibrated confounding adjustment. Using Markov Chain Monte Carlo (MCMC) with non-centered parameterization (0% divergences), I estimate that for a {eval}`r.target_age`-year-old with {eval}`f"{r.baseline_life_years:.0f}"` baseline remaining life years, consuming 28g/day of walnuts over their remaining lifespan yields {eval}`r.walnut.life_years_fmt` additional life years ({eval}`r.walnut.months_fmt` months). Other nuts range from {eval}`r.pecan.life_years_fmt` life years (pecans) to {eval}`r.almond.life_years_fmt` life years (almonds). Approximately {eval}`r.cvd_contribution`% of benefit operates through cardiovascular disease (CVD) prevention, with pathway-specific relative risks of {eval}`r.cvd_effect_range` for CVD versus {eval}`r.cancer_effect_range` for cancer. Incremental cost-effectiveness ratios (ICERs), calculated using standard 3% discounted QALYs, range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias).

## Introduction

### The Nut-Mortality Association

{cite:t}`fraser1992possible` first linked nut consumption to reduced coronary heart disease risk in the Adventist Health Study over three decades ago. Subsequent prospective cohorts replicated this finding: {cite:t}`ellsworth2001frequent` in the Iowa Women's Health Study, {cite:t}`albert2002nut` in the Physicians' Health Study, and {cite:t}`hu2003nut` in the Nurses' Health Study each found 30-50% reductions in cardiovascular disease (CVD) risk among regular nut consumers.

Three large-scale analyses expanded the evidence base from 3 cohorts to 18 cohorts. {cite:t}`bao2013association` analyzed 118,962 participants from the Nurses' Health Study and Health Professionals Follow-up Study, finding that consuming nuts ≥7 times per week reduced all-cause mortality by 20% (hazard ratio [HR] 0.80, 95% CI: 0.73-0.86). {cite:t}`grosso2015nut` meta-analyzed 354,933 participants across 18 cohorts, estimating a 19% mortality reduction (RR 0.81, 95% CI: 0.77-0.85) for highest versus lowest consumption. {cite:t}`aune2016nut` synthesized 819,448 participants across 15 cohorts, finding that 28g/day of nut consumption reduced all-cause mortality by 22% (RR 0.78, 95% CI: 0.72-0.84).

### Cause-Specific Effects

The mortality benefit appears concentrated in cardiovascular causes. {cite}`aune2016nut` find stronger associations for CVD mortality (RR 0.71, 95% CI: 0.63-0.80) than cancer mortality (RR 0.87, 95% CI: 0.80-0.93). This pattern aligns with mechanistic studies showing that nuts improve intermediate CVD risk factors: {cite}`delgobbo2015effects` meta-analyzed 61 controlled feeding trials (n=2,582) and found that nut consumption reduces low-density lipoprotein (LDL) cholesterol by 4.8 mg/dL (0.12 mmol/L), with additional improvements in apolipoprotein B and triglycerides.

### The Confounding Problem

Distinguishing causal effects from confounding remains the primary challenge in nutritional epidemiology. Nut consumers differ from non-consumers across multiple dimensions: {cite:t}`jenab2004associated` find that nut consumers exercise more frequently, smoke less, have higher education and income, and consume more fruits and vegetables. While cohort studies adjust for these measured confounders, unmeasured confounding may persist.

Three lines of evidence inform the causal fraction of observed associations. First, {cite:t}`hashemian2017nut` studied 50,045 adults in the Golestan cohort in northeastern Iran, where nut consumption does not correlate with Western healthy lifestyle patterns. The mortality association persisted (HR 0.71 for ≥3 servings/week), suggesting causal effects independent of healthy-user confounding. Second, sibling-comparison designs that control for shared genetic and environmental factors typically find attenuated—though non-zero—dietary associations. Third, calibrating observed effects against the magnitude predicted from RCT-demonstrated improvements in intermediate outcomes (e.g., LDL cholesterol) suggests that only a fraction of observed associations can be mechanistically explained.

### Gaps in Existing Literature

Three limitations motivate this analysis. First, most studies examine "any nuts" as a single category, obscuring compositional differences. Walnuts contain 2.5g of alpha-linolenic acid (ALA) omega-3 per 28g serving; almonds contain none. Macadamias contain 4.7g of palmitoleic acid (omega-7); other nuts contain negligible amounts. These differences may translate to differential health effects.

Second, relative risk reductions do not directly map to absolute benefits. A 22% mortality reduction translates to different absolute life expectancy gains depending on baseline mortality risk, age distribution of benefits, and cause-specific mortality patterns.

Third, no existing study quantifies absolute life expectancy gains from nut consumption. Health policy requires standardized metrics for resource allocation; quality-adjusted life years (QALYs) enable comparison across interventions. The UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE (World Health Organization CHOosing Interventions that are Cost-Effective) use QALYs in cost-effectiveness analyses.

### Contribution

This paper develops a Bayesian Monte Carlo framework for estimating life expectancy gains from nut consumption, addressing: (1) expected benefit magnitude in absolute terms (life years); (2) nut type comparisons based on compositional differences; (3) explicit treatment of confounding uncertainty calibrated to multiple evidence sources. QALYs are computed for cost-effectiveness comparison with other health interventions. Throughout this paper, "nuts" refers to tree nuts plus peanuts (a legume), following epidemiological convention.

### A Note on Metrics

This paper reports **life years gained** ({eval}`r.life_years_range` years, or {eval}`r.months_range` months) as the primary metric—representing the actual expected increase in lifespan from daily nut consumption. This is more intuitive for individual decision-making ("how much longer will I live?").

For cost-effectiveness comparison with other health interventions, I also report **QALYs** (quality-adjusted life years), which weight life years by age-specific quality of life using population EQ-5D norms. I present both undiscounted QALYs and discounted QALYs (3% annually, following NICE/ICER/WHO-CHOICE guidelines). Note that this analysis models only **mortality effects**—potential morbidity benefits (e.g., fewer non-fatal CVD events, improved cognitive function) are not included, making these QALY estimates conservative.

## Methods

### Evidence Sources

I constructed a hierarchical evidence base drawing on four categories of sources, in order of priority. Meta-analyses of mortality outcomes from {cite:t}`aune2016nut` and {cite:t}`grosso2015nut` provide pooled estimates for all-cause mortality. Large prospective cohort studies, including {cite:t}`bao2013association` and {cite:t}`guasch2017nut`, provide nut-specific associations. Randomized controlled trials—{cite:t}`ros2008mediterranean` (PREDIMED), {cite:t}`rajaram2021walnuts` (WAHA), {cite:t}`delgobbo2015effects`, {cite:t}`hart2025pecan`, {cite:t}`guarneiri2021pecan`, and {cite:t}`mah2017cashew`—inform nut-specific adjustment factors. Nutrient composition data from {cite:t}`usda2024fooddata` provides standardized nutrient profiles.

### Nut Nutrient Profiles

Nuts vary in macronutrient and micronutrient composition {cite:p}`usda2024fooddata`. All contain 12-22g fat per 28g serving, but differ in fatty acid profiles (monounsaturated vs. polyunsaturated), micronutrient content, and caloric density (157-204 kcal per serving).

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

Walnuts have the highest ALA omega-3 content (2.5g/28g), comprising 73% of total fat as polyunsaturated fatty acids. ALA is a precursor to EPA and DHA {cite:p}`ros2008mediterranean`. Almonds have the highest vitamin E content (7.3mg/28g, 49% DV) and highest fiber content among tree nuts (3.5g/28g). Macadamias are the only common nut with substantial omega-7 fatty acids (palmitoleic acid, 4.7g/28g); they also have the highest caloric density (204 kcal) and saturated fat content (3.4g). Peanuts (technically legumes) have the highest protein content (7.3g/28g) and lowest cost; aflatoxin contamination occurs in some regions, particularly sub-Saharan Africa and Southeast Asia {cite:p}`williams2004aflatoxin`.

**Note on Brazil nuts**: Brazil nuts are excluded from this analysis due to selenium toxicity concerns. A single 28g serving contains approximately 544μg selenium, exceeding the 400μg/day upper tolerable intake limit established by the Institute of Medicine. Chronic daily consumption at standard serving sizes risks selenosis (hair loss, nail brittleness, neurological effects). Consumers interested in Brazil nuts should limit intake to 1-2 nuts per day.

### Statistical Model

I implemented a hierarchical Bayesian model using PyMC with Markov Chain Monte Carlo (MCMC) sampling. The model uses non-centered parameterization to ensure efficient sampling, with convergence diagnostics reported in the Results section.

```{figure} _static/figures/model_architecture.png
:name: fig-architecture
:width: 100%

**Figure 1: Model Architecture.** The hierarchical Bayesian model synthesizes evidence from multiple sources: USDA nutrient composition, meta-analysis priors for nutrient-pathway effects, confounding calibration evidence, and CDC life tables. The PyMC model uses non-centered parameterization to avoid divergences, producing pathway-specific relative risks that are propagated through the lifecycle model to estimate life years and QALYs.
```

**Note on model structure**: This is a **prior synthesis model** that propagates uncertainty from multiple evidence sources (nutrient effect estimates, nut-specific RCT residuals, confounding calibration) through to life expectancy estimates. Unlike traditional Bayesian analyses that update beliefs from outcome data via a likelihood function, this model synthesizes prior information without a likelihood linking to mortality observations. The "posterior" represents the distribution of plausible life expectancy gains given current evidence, not updated beliefs from new data. This approach is appropriate because the goal is uncertainty quantification from existing evidence synthesis, not parameter estimation from a novel dataset.

#### Pathway-Specific Effects

The model estimates separate relative risks for three mortality pathways. CVD mortality shows the largest effects (RR 0.83-0.90), informed by ALA omega-3, fiber, and magnesium priors. Cancer mortality shows smaller effects (RR 0.97-0.99, corresponding to 1-3% reductions), informed by fiber and vitamin E priors. Other mortality shows intermediate effects (RR 0.94-0.97), representing a composite of remaining causes. This decomposition allows different nutrients to contribute differentially to each pathway—for example, ALA omega-3 strongly affects CVD but has negligible cancer effects, while fiber contributes to both.

I do not model a separate morbidity pathway. While nuts may improve quality of life through reduced non-fatal CVD events, improved cognitive function, and other morbidity effects, this analysis focuses solely on mortality. QALYs are computed by weighting mortality-based life expectancy gains by population EQ-5D norms (age-specific quality weights), not by modeling nut-specific quality improvements. This makes the estimates conservative—actual benefits may be larger if nuts reduce morbidity beyond their mortality effects.

#### Nutrient-Derived Priors

Rather than specifying nut-specific effects directly, I derived expected effects from nutrient composition using priors from independent meta-analyses:

**Table 2: Nutrient-Pathway Effect Priors.** Log-relative risk per unit nutrient, with pathway-specific coefficients. Priors from meta-analyses of prospective cohort studies and randomized trials. For nutrients with limited direct evidence, I use wide priors (SD ≥50% of mean) reflecting mechanistic plausibility with high uncertainty.

| Nutrient | CVD Effect | Cancer Effect | Other Effect | Source |
|----------|------------|---------------|--------------|--------|
| ALA omega-3 (per g) | -0.15 (0.05) | -0.02 (0.02) | -0.08 (0.04) | {cite}`naghshi2021ala` |
| Fiber (per g) | -0.015 (0.005) | -0.015 (0.005) | -0.01 (0.005) | {cite}`threapleton2013fiber` |
| Omega-6 (per g) | -0.004 (0.002) | -0.002 (0.002) | -0.002 (0.002) | {cite}`farvid2014omega6` |
| Omega-7 (per g) | -0.03 (0.06) | 0.00 (0.03) | -0.02 (0.04) | Mechanistic (wide prior) |
| Saturated fat (per g) | +0.02 (0.01) | +0.01 (0.01) | +0.01 (0.01) | {cite}`sacks2017sat` |
| Magnesium (per 10mg)† | -0.003 (0.001) | -0.001 (0.001) | -0.002 (0.001) | {cite}`fang2016mg` |
| Arginine (per 100mg) | -0.003 (0.003) | -0.001 (0.002) | -0.002 (0.002) | Mechanistic (wide prior) |
| Vitamin E (per mg) | -0.005 (0.005) | -0.01 (0.01) | -0.003 (0.003) | Mechanistic (wide prior) |
| Phytosterols (per 10mg) | -0.001 (0.002) | -0.001 (0.002) | 0.00 (0.001) | Mechanistic (wide prior) |
| Protein (per g) | -0.002 (0.003) | -0.001 (0.002) | -0.001 (0.002) | Mechanistic (wide prior) |

†Magnesium and phytosterols use larger units (per 10mg, per 10mg) because nuts provide 30-80mg and 20-100mg per serving, respectively. Effect sizes are correspondingly smaller per unit.

```{figure} _static/figures/nutrient_contributions.png
:name: fig-nutrients
:width: 90%

**Figure 2: Nutrient Contributions to CVD Mortality Reduction.** Heatmap showing how each nutrient contributes to the CVD pathway effect for each nut type. ALA omega-3 is the dominant driver for walnuts (highest contribution), while fiber and magnesium contribute more evenly across nuts. Negative values indicate harmful effects (e.g., saturated fat).
```

#### Hierarchical Structure

I model nut-specific effects as deviations from nutrient-predicted effects using non-centered parameterization. Let $z_{\text{pathway}} \sim \mathcal{N}(0, 1)$ represent standardized deviations and $\tau_{\text{pathway}} \sim \text{HalfNormal}(0.03)$ represent the shrinkage prior. The scale 0.03 reflects an expectation that nut-specific deviations are small (±6% on log-RR scale at 2 SD), since nutrients explain most compositional variation; sensitivity analysis with $\tau \sim \text{HalfNormal}(0.10)$ shows robust results. The true effect for each nut-pathway combination is then $\theta_{\text{true}} = \theta_{\text{nutrients}} + \tau_{\text{pathway}} \cdot z_{\text{pathway}}$. This parameterization ensures efficient MCMC sampling and shrinks nut-specific deviations toward nutrient-predicted effects when evidence is limited.

Prior predictive checks confirm these priors generate plausible ranges: sampling from nutrient priors yields all-cause RRs spanning 0.72-0.92 across nuts (95% interval), consistent with the meta-analytic range of 0.72-0.84 {cite:p}`aune2016nut`.

#### Confounding Adjustment

The model includes a causal fraction parameter with Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior (mean {eval}`r.confounding_mean`, 95% CI: {eval}`r.confounding_ci_lower`-{eval}`r.confounding_ci_upper`), calibrated to three evidence sources (see Confounding Calibration section below).

#### Lifecycle Integration

I propagate posterior samples of pathway-specific relative risks through a lifecycle model using CDC life tables for age-specific mortality, age-varying cause fractions (CVD increases from 20% at age 40 to 40% at age 80), quality weights from EQ-5D population norms (mean 0.85) {cite:p}`sullivan2005catalogue`, and 3% annual discounting.

```{figure} _static/figures/cause_fractions.png
:name: fig-cause-fractions
:width: 85%

**Figure 3: Age-Varying Cause-of-Death Fractions.** The proportion of deaths attributable to CVD increases with age (from ~20% at age 40 to ~40% at age 90), while cancer peaks in middle age. This age structure means CVD mortality reductions have larger absolute effects at older ages, when most remaining life years are realized.
```

### Confounding Calibration

The source meta-analyses adjusted for measured confounders (age, sex, body mass index [BMI], smoking, alcohol, physical activity). This section addresses what fraction of the *residual* association—after these adjustments—reflects causal effects versus unmeasured confounding.

**LDL pathway**: {cite}`delgobbo2015effects` find that nuts reduce LDL cholesterol by 4.8 mg/dL per serving in 61 RCTs. This predicts ~3% CVD mortality reduction via established dose-response relationships, compared to ~25% observed in cohorts. However, this 12% "mechanism explanation" represents only one of several causal pathways. Nuts also reduce blood pressure (~1-3 mmHg), improve glycemic control, provide anti-inflammatory omega-3 fatty acids, and deliver antioxidants and fiber {cite:p}`ros2008mediterranean`. The LDL pathway therefore provides a *floor* on the causal fraction, not a ceiling.

**Sibling comparison evidence**: Within-family designs control for shared genetic and environmental confounding {cite:p}`frisell2012sibling`. If sibling-controlled estimates are 30-50% smaller than unpaired estimates, this implies 50-70% of the association survives sibling control—suggesting a causal fraction in that range for dietary factors generally. However, no sibling studies exist specifically for nut consumption, and sibling designs may over-adjust by removing non-confounding shared factors.

**Golestan cohort**: {cite}`hashemian2017nut` studied nut consumption in Iran, where nut consumers were *more* likely to smoke and be obese (the opposite of Western cohorts). Their adjusted HR of 0.71 (29% mortality reduction) is actually *larger* than {cite:t}`aune2016nut`'s Western estimate of 0.78 (22% reduction). This suggests that healthy-user confounding in Western cohorts, if anything, biases estimates toward the null—perhaps due to over-adjustment for intermediates (blood pressure, serum lipids). The Golestan evidence supports a causal fraction near or above 100% of the adjusted Western effect.

**E-value analysis**: Using VanderWeele's method {cite:p}`vanderweele2017sensitivity`, the E-value for HR=0.78 is {eval}`r.e_value`. An unmeasured confounder would need associations of RR ≥ {eval}`r.e_value` with both nut consumption and mortality to fully explain the observed effect. For context: exercise-mortality RR ≈ 1.5-2.0; income-mortality RR ≈ 1.3-1.5. An E-value of {eval}`r.e_value` suggests moderate residual confounding is plausible but unlikely to explain the entire association.

**Prior specification**: Synthesizing this evidence, I adopt a Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior with mean {eval}`r.confounding_mean` and 95% CI: {eval}`int(r.confounding_ci_lower * 100)`-{eval}`int(r.confounding_ci_upper * 100)`%. This symmetric prior reflects genuine uncertainty: the sibling literature suggests 50-70% causal fractions for dietary factors; the Golestan evidence suggests the adjusted Western estimates may be conservative; the E-value indicates full confounding would require implausibly strong unmeasured confounders. Sensitivity analysis with more skeptical (mean 0.25) and optimistic (mean 0.75) priors is presented in the Discussion.

```{figure} _static/figures/confounding_calibration.png
:name: fig-confounding
:width: 90%

**Figure 4: Confounding Calibration.** Evidence synthesis for the causal fraction prior. The Golestan cohort (HR 0.71) shows effects larger than Western meta-analyses (HR 0.78), suggesting healthy-user bias in Western data is minimal. The Beta(2.5, 2.5) prior reflects symmetric uncertainty around a 50% causal fraction.
```

### Target Population

I modeled a {eval}`r.target_age`-year-old from the United States or Europe with {eval}`r.life_expectancy` years remaining life expectancy. I excluded individuals with nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% prevalence, with peanut allergy alone affecting ~3% of US adults {cite:p}`gupta2021prevalence`).

### Cost-Effectiveness Analysis

I calculated incremental cost-effectiveness ratios (ICERs) as $\text{ICER} = \frac{\text{Annual cost} \times \text{Years of consumption}}{\text{QALY gain}}$. Annual costs use 2024 US retail prices from USDA Economic Research Service: peanuts (\$37/year for 28g/day), almonds (\$95/year), walnuts (\$97/year), cashews (\$103/year), pistachios (\$114/year), pecans (\$126/year), and macadamias (\$229/year) {cite:p}`usda2024prices`. I discounted costs at 3% annually, matching the QALY discount rate.

## Results

### Model Diagnostics

MCMC sampling achieved convergence across all parameters. Table 3a reports diagnostics for key parameters.

**Table 3a: MCMC Convergence Diagnostics.** R-hat values near 1.0 indicate convergence across chains; ESS (effective sample size) > 400 indicates sufficient independent samples. All parameters meet standard thresholds.

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.table_3_diagnostics())
```

Note: {eval}`r.n_samples` posterior samples from {eval}`r.n_chains` chains ({eval}`r.n_draws` draws each after {eval}`r.n_warmup` warmup). Zero divergences across all samples. Maximum R-hat across all ~300 parameters (nutrients × pathways × nuts + hierarchical parameters) is 1.003, confirming convergence.

### Posterior Predictive Validation

As a consistency check, I verified that the model's implied all-cause mortality hazard ratio matches the source meta-analysis. Weighting pathway-specific RRs by cause-specific mortality fractions yields an implied all-cause HR of 0.79 (95% CI: 0.71-0.86), consistent with {cite:t}`aune2016nut`'s estimate of 0.78 (95% CI: 0.72-0.84). This confirms the pathway decomposition preserves the overall effect magnitude.

### Posterior Predictive Checks

Beyond aggregate validation, I verified that individual MCMC draws produce scientifically plausible outcomes:

1. **Relative risk bounds**: All 4,000 posterior samples yield pathway-specific RRs in the range [0.65, 1.05]. No draws produce implausible values (RR > 1.5 or RR < 0.5).

2. **QALY bounds**: All sampled QALYs fall within [−0.1, 0.8] years, consistent with the maximum plausible benefit given remaining life expectancy. Negative values (reflecting posterior uncertainty about harm) occur in <5% of draws.

3. **Pathway contributions**: CVD, cancer, and other mortality contributions sum to 100% ± 2% across all posterior draws, confirming the decomposition is internally consistent.

These checks confirm the model produces valid predictions across the full posterior distribution, not just at the mean.

### Primary Finding

The hierarchical Bayesian model estimates that a {eval}`r.target_age`-year-old consuming 28g/day of nuts over their remaining lifespan gains {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months), with walnuts ({eval}`r.walnut.life_years_fmt` years) ranking highest and pecans ({eval}`r.pecan.life_years_fmt` years) lowest. Approximately {eval}`r.cvd_contribution`% of this benefit operates through CVD mortality prevention.

```{figure} _static/figures/forest_plot.png
:name: fig-forest
:width: 90%

**Figure 5: Life Years Gained by Nut Type.** Forest plot showing posterior mean life years gained with 95% credible intervals. Walnuts rank highest due to ALA omega-3 content; pecans rank lowest. All intervals exclude zero, indicating high confidence of positive benefit.
```

**Table 3: Life Year and QALY Estimates by Nut Type.** Posterior estimates from MCMC sampling ({eval}`r.n_samples` draws, {eval}`r.n_chains` chains, 0% divergences). Life years (LY) are the primary metric. QALYs weight life years by age-specific quality of life; both undiscounted and discounted (3% annually) QALYs are shown. P(>0) = posterior probability of positive benefit. 95% credible intervals reflect parameter uncertainty including confounding adjustment.

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.table_3_qalys())
```

Note: "Dominated" indicates ICER undefined when lower CI bound for QALYs is ≤0.

### Pathway-Specific Relative Risks

CVD effects are 5-10x stronger than cancer effects (17% vs 2% mortality reduction), which explains why walnuts (high ALA omega-3) outperform other nuts.

**Table 4: Pathway-Specific Relative Risks by Nut Type.** Posterior mean RRs for each mortality pathway. Lower values indicate greater benefit.

```{code-cell} python
:tags: [remove-input]

from IPython.display import Markdown
Markdown(r.table_4_pathway_rrs())
```

```{figure} _static/figures/pathway_rrs.png
:name: fig-pathway-rrs
:width: 90%

**Figure 6: Pathway-Specific Mortality Reductions.** Bar chart comparing relative risk reductions (1-RR) across mortality pathways for each nut. CVD effects (17% reduction for walnuts) dominate cancer effects (1-3% reduction), explaining why ALA-rich walnuts outperform other nuts. Error bars represent posterior uncertainty.
```

### Pathway Contributions

Approximately 80% of the QALY benefit operates through CVD prevention, with the remainder split between other mortality (15%) and cancer mortality (5%).

**Table 5: Pathway Contribution to Total Benefit.** Decomposition of QALY gains by mortality pathway. CVD dominates due to both stronger relative risk reductions and higher cause-specific mortality at older ages. Contribution estimates are posterior means with 95% CIs computed across 500 Monte Carlo draws.

| Pathway | Contribution (95% CI) | Mean RR Range | Key Nutrients |
|---------|----------------------|---------------|---------------|
| CVD mortality | 80% (72-87%) | 0.83-0.89 | ALA omega-3, fiber, magnesium |
| Other mortality | 15% (10-21%) | 0.94-0.97 | Fiber, protein |
| Cancer mortality | 5% (2-9%) | 0.97-0.99 | Fiber, vitamin E |

### Cost-Effectiveness

As of December 2025, NICE raised its thresholds to £25,000-35,000/QALY (\$33,500-47,000 at current exchange rates {cite:p}`tradingeconomics2025gbpusd`), with interventions below £25,000 considered clearly cost-effective {cite:p}`nice2025threshold`. ICER evaluates interventions at \$50,000, \$100,000, and \$150,000/QALY benchmarks {cite:p}`icer2024reference`. All seven nuts fall below NICE's new £25,000 threshold and ICER's \$50,000 benchmark. Peanuts achieve the lowest ICER due to low cost (\$37/year) combined with the third-highest QALY estimate.

```{figure} _static/figures/icer_comparison.png
:name: fig-icer
:width: 90%

**Figure 7: Cost-Effectiveness by Nut Type.** Incremental cost-effectiveness ratios (ICERs) compared to standard thresholds. All nuts fall below both NICE (£25,000/QALY) and ICER (\$50,000/QALY) benchmarks. Peanuts achieve the lowest ICER due to low cost combined with strong mortality effects; macadamias rank highest due to premium pricing.
```

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

The hierarchical Bayesian model estimates {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months) from daily nut consumption, with walnut and almond sharing the top position and pecan ranking lowest. This spread (~45% of the category effect) is larger than previous analyses suggested, reflecting the mechanistic importance of nutrient composition.

The dominance of CVD pathway (~{eval}`r.cvd_contribution`% of benefit) explains the walnut advantage: its 2.5g ALA omega-3 content drives a CVD RR of 0.83 compared to 0.88-0.89 for nuts with negligible ALA. This mechanistic link provides stronger causal support than overall mortality associations.

### Comparison to Prior Estimates

These estimates are lower than unadjusted observational associations (22% mortality reduction from {cite}`aune2016nut`) but higher than pure LDL-pathway predictions (~3% reduction). The Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) confounding prior with mean {eval}`r.confounding_mean` mediates between these extremes.

### Cost-Effectiveness

ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias). All nuts fall below NICE's new £{eval}`f'{r.nice_lower_gbp:,}'`/QALY (\${eval}`f'{r.nice_lower_usd:,}'`) threshold and ICER's \${eval}`f'{r.icer_threshold:,}'`/QALY benchmark. Peanuts achieve the lowest ICER, combining the third-highest QALY estimate with the lowest cost.

### Sensitivity Analyses

I examined robustness to key parameter assumptions:

**Confounding prior**: The model uses a Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior with mean {eval}`r.confounding_mean`. Since the model has no likelihood function linking to outcome data (it synthesizes prior information only), the posterior for the confounding fraction equals the prior. This is appropriate because the goal is to quantify uncertainty about causal effects given our current evidence, not to update beliefs from new data. Table 7 shows sensitivity to alternative prior specifications:

**Table 7: Sensitivity to Confounding Prior.** QALY estimates under alternative confounding assumptions. Rankings remain stable across specifications.

| Prior | Mean | Interpretation | Walnut QALY | Peanut QALY | Change |
|-------|------|----------------|-------------|-------------|--------|
| Beta(1.5, 4.5) | 25% | Skeptical | ~0.19 | ~0.16 | -50% |
| **Beta(2.5, 2.5)** | **50%** | **Base case** | **{eval}`r.walnut.qaly`** | **{eval}`r.peanut.qaly`** | **—** |
| Beta(3, 1) | 75% | Optimistic | ~0.57 | ~0.47 | +50% |
| Beta(9, 1) | 90% | Very optimistic | ~0.68 | ~0.56 | +80% |

**Hierarchical shrinkage (τ)**: The baseline model uses τ ~ HalfNormal(0.03), which constrains nut-specific deviations from nutrient-predicted effects to ~±6% on the log-RR scale (95% prior interval). With τ ~ HalfNormal(0.10) (weaker shrinkage), credible intervals widen by ~15% but point estimates and rankings remain stable. This suggests results are driven primarily by nutrient composition rather than nut-specific residual effects.

**Adherence**: The base case assumes 100% adherence over the remaining lifespan. Dietary intervention trials typically achieve 50-70% long-term adherence {cite:p}`appel2006adherence`. At 70% adherence, effective QALYs decrease proportionally (e.g., walnut from {eval}`r.walnut.qaly` to {eval}`f'{r.walnut.qaly_mean * 0.7:.2f}'` QALYs) and ICERs increase by 43%. At 50% adherence, effective QALYs halve and ICERs double. All nuts remain below \$50,000/QALY even at 50% adherence. For individual decision-making, readers should scale estimates by their expected adherence.

**Age at initiation**: For a 60-year-old (vs 40), discounted QALYs decrease ~40% due to shorter remaining lifespan, partially offset by stronger CVD benefit at older ages.

**Dose-response**: The base case models 28g/day (one ounce), the standard serving size. {cite:t}`aune2016nut` find benefits plateau above ~20g/day. At 20g/day (70% of standard serving), estimated QALYs are approximately 90% of the 28g estimates, while costs decrease by 30%, improving cost-effectiveness by ~20%. This suggests that 20g/day may be optimal for cost-conscious consumers, though the dose-response evidence remains uncertain.

### Substitution Effects

The model treats nut consumption as additive to baseline diet, but in practice nuts replace other foods. The net health impact depends on what is displaced:

- **Replacing refined carbohydrates** (chips, crackers): Large benefit. Nuts provide fiber, unsaturated fats, and micronutrients absent from processed snacks. This substitution likely underlies the strong cohort associations, as snack replacement is the most common use case.
- **Replacing other healthy fats** (olive oil, fatty fish): Smaller or negligible benefit. These foods share similar fatty acid profiles and cardioprotective effects.
- **Replacing red meat**: Moderate benefit from reduced saturated fat and heme iron, partially offset by lower protein bioavailability.

{cite:t}`li2015substitution` modeled isocaloric substitution in the Nurses' Health Study and found that replacing one serving of red meat with nuts reduced all-cause mortality by 19%, while replacing fish showed no significant change. These substitution patterns suggest the QALY estimates in this paper are most applicable when nuts replace less healthy alternatives—the realistic scenario for most consumers adding nuts to their diet.

### Limitations

Several limitations warrant consideration. First, this analysis models only **mortality effects**—potential morbidity benefits from nuts (fewer non-fatal strokes and heart attacks, improved metabolic markers, better cognitive function) are not captured. The QALY estimates are therefore conservative; actual quality-adjusted benefits may be larger.

Second, estimates rely on observational data, and residual confounding may remain despite calibration. Source studies come predominantly from the US and Europe, limiting generalizability to other populations. I modeled a fixed 28g/day dose, though dose-response may be non-linear—{cite:t}`aune2016nut` find benefits plateau above ~20g/day. The model assumes perfect adherence, whereas dietary intervention studies find real-world adherence of 50-70% {cite:p}`appel2006adherence`.

## Conclusion

Using a hierarchical Bayesian model with pathway-specific nutrient effects and MCMC sampling (0% divergences), I estimate that daily nut consumption (28g) yields {eval}`r.life_years_range` additional life years ({eval}`r.months_range` months) for a {eval}`r.target_age`-year-old, with walnuts and almonds ranking highest. Approximately {eval}`r.cvd_contribution`% of benefit operates through CVD prevention, driven primarily by ALA omega-3, fiber, and magnesium content. For cost-effectiveness comparison, ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias), all below NICE and ICER thresholds. These estimates reflect mortality effects only; potential morbidity benefits (reduced non-fatal CVD events, improved cognitive function) would increase actual QALYs. Findings do not apply to individuals with nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% of adults {cite:p}`gupta2021prevalence`).

## Data and Code Availability

**Code**: https://github.com/MaxGhenis/whatnut (MIT License)

**Data Sources**:
- Nutrient composition: USDA FoodData Central SR Legacy database (https://fdc.nal.usda.gov/). FDC IDs for each nut are provided in Table 1.
- Mortality rates: CDC National Vital Statistics System, United States Life Tables 2021 (https://www.cdc.gov/nchs/nvss/life-expectancy.htm)
- Nut prices: USDA Economic Research Service, Food Prices and Spending (https://www.ers.usda.gov/data-products/food-prices/)
- Quality-of-life weights: Sullivan & Ghushchyan (2006) EQ-5D US population norms

**Reproducibility**: All paper values are computed from `src/whatnut/paper_results.py`. Run `python -m whatnut.paper_results` to verify. MCMC results can be regenerated with `whatnut[bayesian]` dependencies (seed=42).

```{bibliography}
```

```{tableofcontents}
```
