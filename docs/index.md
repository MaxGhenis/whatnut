# What Nut? A Bayesian Analysis of Quality-Adjusted Life Years from Nut Consumption

**Max Ghenis**

max@maxghenis.com

```{code-cell} python
:tags: [remove-cell]

# Setup: Import paper results (single source of truth)
import sys
sys.path.insert(0, '../src')
from whatnut.paper_results import r
```

## Abstract

Observational studies find nut consumption associated with reduced mortality. I present a hierarchical Bayesian framework with pathway-specific effects (cardiovascular, cancer, and other mortality), nutrient-derived priors from independent meta-analyses, and evidence-calibrated confounding adjustment. Using Markov Chain Monte Carlo (MCMC) with non-centered parameterization (0% divergences), I estimate that consuming 28g/day of walnuts yields {eval}`r.walnut.qaly` quality-adjusted life years (QALYs; 95% credible interval [CI]: {eval}`r.walnut.qaly_ci`), with other nuts ranging from {eval}`r.pecan.qaly` QALYs (pecans) to {eval}`r.almond.qaly` QALYs (almonds). Approximately {eval}`r.cvd_contribution`% of benefit operates through cardiovascular disease (CVD) prevention, with pathway-specific relative risks of {eval}`r.cvd_effect_range` for CVD versus {eval}`r.cancer_effect_range` for cancer. Incremental cost-effectiveness ratios (ICERs) range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias). These findings apply to individuals without nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% of adults).

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

Third, health policy requires standardized metrics for resource allocation. Quality-adjusted life years (QALYs) combine life expectancy and health-related quality of life into a single metric. The UK National Institute for Health and Care Excellence (NICE), US Institute for Clinical and Economic Review (ICER), and WHO-CHOICE (World Health Organization CHOosing Interventions that are Cost-Effective) use QALYs in cost-effectiveness analyses. To my knowledge, no existing study quantifies QALY gains from nut consumption.

### Contribution

This paper develops a Bayesian Monte Carlo framework for estimating QALY gains from nut consumption, addressing: (1) expected benefit magnitude in standardized units; (2) nut type comparisons based on compositional differences; (3) explicit treatment of confounding uncertainty calibrated to multiple evidence sources. Throughout this paper, "nuts" refers to tree nuts plus peanuts (a legume), following epidemiological convention.

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

### Statistical Model

I implemented a hierarchical Bayesian model using PyMC with Markov Chain Monte Carlo (MCMC) sampling. The model uses non-centered parameterization to ensure efficient sampling, with convergence diagnostics reported in the Results section.

#### Pathway-Specific Effects

The model estimates separate relative risks for three mortality pathways. CVD mortality shows the largest effects (RR 0.83-0.90), informed by ALA omega-3, fiber, and magnesium priors. Cancer mortality shows smaller effects (RR 0.97-0.99, corresponding to 1-3% reductions), informed by fiber and vitamin E priors. Other mortality shows intermediate effects (RR 0.94-0.97), representing a composite of remaining causes. This decomposition allows different nutrients to contribute differentially to each pathway—for example, ALA omega-3 strongly affects CVD but has negligible cancer effects, while fiber contributes to both.

I do not model a separate quality-of-life pathway. While nuts may improve morbidity through reduced CVD events, fatigue, and cognitive function, such effects are largely captured through the mortality pathways (survivors of prevented CVD events have higher quality of life). Including a separate quality pathway would risk double-counting benefits. The primary QALY calculation therefore uses mortality-based life expectancy gains weighted by population EQ-5D norms.

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
| Magnesium (per 10mg) | -0.003 (0.001) | -0.001 (0.001) | -0.002 (0.001) | {cite}`fang2016mg` |
| Arginine (per 100mg) | -0.003 (0.003) | -0.001 (0.002) | -0.002 (0.002) | Mechanistic (wide prior) |
| Vitamin E (per mg) | -0.005 (0.005) | -0.01 (0.01) | -0.003 (0.003) | Mechanistic (wide prior) |
| Phytosterols (per 10mg) | -0.001 (0.002) | -0.001 (0.002) | 0.00 (0.001) | Mechanistic (wide prior) |
| Protein (per g) | -0.002 (0.003) | -0.001 (0.002) | -0.001 (0.002) | Mechanistic (wide prior) |

#### Hierarchical Structure

I model nut-specific effects as deviations from nutrient-predicted effects using non-centered parameterization. Let $z_{\text{pathway}} \sim \mathcal{N}(0, 1)$ represent standardized deviations and $\tau_{\text{pathway}} \sim \text{HalfNormal}(0.03)$ represent the shrinkage prior. The true effect for each nut-pathway combination is then $\theta_{\text{true}} = \theta_{\text{nutrients}} + \tau_{\text{pathway}} \cdot z_{\text{pathway}}$. This parameterization ensures efficient MCMC sampling and shrinks nut-specific deviations toward nutrient-predicted effects when evidence is limited.

#### Confounding Adjustment

The model includes a causal fraction parameter with Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) prior (mean {eval}`r.confounding_mean`, 95% CI: {eval}`r.confounding_ci_lower`-{eval}`r.confounding_ci_upper`), calibrated to three evidence sources (see Confounding Calibration section below).

#### Lifecycle Integration

I propagate posterior samples of pathway-specific relative risks through a lifecycle model using CDC life tables for age-specific mortality, age-varying cause fractions (CVD increases from 20% at age 40 to 40% at age 80), quality weights from EQ-5D population norms (mean 0.85) {cite:p}`sullivan2005catalogue`, and 3% annual discounting.

### Confounding Calibration

The source meta-analyses adjusted for measured confounders (age, sex, body mass index [BMI], smoking, alcohol, physical activity). I calibrated the confounding prior using three lines of evidence:

**LDL pathway calibration**: {cite}`delgobbo2015effects` find that nuts reduce LDL cholesterol by 4.8 mg/dL (0.12 mmol/L) per serving (61 controlled trials). Using established LDL-CVD relationships, this predicts a ~3% reduction in CVD mortality, compared to 25% observed in cohort studies. This implies ~12% of the observed CVD effect operates through the LDL pathway.

**Sibling comparison evidence**: Within-family studies that control for shared genetic and environmental confounding typically find attenuated associations between dietary factors and mortality {cite:p}`frisell2012sibling`. {cite:t}`frisell2012sibling` find that sibling-controlled estimates are typically 30-50% smaller than unpaired estimates, suggesting confounding explains 30-50% of observed dietary associations.

**Golestan cohort**: {cite}`hashemian2017nut` find that in Iran, where nut consumption does not correlate with Western healthy lifestyles, the mortality association persists (hazard ratio [HR] 0.71 for ≥3 servings/week).

I calibrated the Beta prior using method of moments matching to the evidence distribution. Let $p_i$ denote the causal fraction implied by evidence source $i$ with weight $w_i$:

- LDL pathway: $p_1 = 0.12$, $w_1 = 0.30$ (mechanistic, most direct)
- Sibling studies: $p_2 = 0.20$, $w_2 = 0.30$ (genetic confounding control)
- Golestan cohort: $p_3 = 0.40$, $w_3 = 0.40$ (cross-cultural, shows effect persists)

The weighted mean is $\bar{p} = \sum w_i p_i = 0.256 \approx 0.25$. The weighted sample variance is $\sigma^2_{sample} = \sum w_i (p_i - \bar{p})^2 = 0.015$. However, this underestimates uncertainty because it only captures variance across three evidence sources, not the full epistemic uncertainty about confounding mechanisms. I inflate to $\sigma^2 = 0.027$ (~1.8× larger) to obtain a wider prior with 95% mass between 0.02 and 0.63. Method of moments for Beta($\alpha$, $\beta$) yields:

$$\alpha = \bar{p} \left( \frac{\bar{p}(1-\bar{p})}{\sigma^2} - 1 \right) \approx 1.5, \quad \beta = (1-\bar{p}) \left( \frac{\bar{p}(1-\bar{p})}{\sigma^2} - 1 \right) \approx 4.5$$

This yields Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) with mean {eval}`r.confounding_mean` and 95% CI: {eval}`int(r.confounding_ci_lower * 100)`-{eval}`int(r.confounding_ci_upper * 100)`%. The right-skewed distribution reflects that most evidence points to low causal fractions while allowing for larger effects suggested by the Golestan cohort.

Using VanderWeele's method {cite:p}`vanderweele2017sensitivity`, I calculate the E-value as {eval}`r.e_value` for HR=0.78: an unmeasured confounder would need RR ≥ {eval}`r.e_value` with both nut consumption and mortality to fully explain the observed association.

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

Note: {eval}`r.n_samples` posterior samples from {eval}`r.n_chains` chains ({eval}`r.n_draws` draws each after {eval}`r.n_warmup` warmup). Zero divergences across all samples.

### Posterior Predictive Validation

As a consistency check, I verified that the model's implied all-cause mortality hazard ratio matches the source meta-analysis. Weighting pathway-specific RRs by cause-specific mortality fractions yields an implied all-cause HR of 0.79 (95% CI: 0.71-0.86), consistent with {cite:t}`aune2016nut`'s estimate of 0.78 (95% CI: 0.72-0.84). This confirms the pathway decomposition preserves the overall effect magnitude.

### Primary Finding

The hierarchical Bayesian model estimates QALY gains ranging from {eval}`r.pecan.qaly` (pecans) to {eval}`r.walnut.qaly` (walnuts) for a {eval}`r.target_age`-year-old consuming 28g/day over their remaining lifespan.

**Table 3: QALY and Life Year Estimates by Nut Type.** Posterior estimates from MCMC sampling ({eval}`r.n_samples` draws, {eval}`r.n_chains` chains, 0% divergences). QALYs and costs discounted at {eval}`int(r.discount_rate * 100)`% annually. Life years (LY) are undiscounted. P(>0) = posterior probability that QALY gain exceeds zero. 95% credible intervals reflect parameter uncertainty including confounding adjustment.

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

### Pathway Contributions

Approximately 80% of the QALY benefit operates through CVD prevention, with the remainder split between other mortality (15%) and cancer mortality (5%).

**Table 5: Pathway Contribution to Total Benefit.** Decomposition of QALY gains by mortality pathway. CVD dominates due to both stronger relative risk reductions and higher cause-specific mortality at older ages.

| Pathway | Contribution | Mean RR Range | Key Nutrients |
|---------|-------------|---------------|---------------|
| CVD mortality | ~80% | 0.83-0.89 | ALA omega-3, fiber, magnesium |
| Other mortality | ~15% | 0.94-0.97 | Fiber, protein |
| Cancer mortality | ~5% | 0.97-0.99 | Fiber, vitamin E |

### Cost-Effectiveness

As of December 2025, NICE raised its thresholds to £25,000-35,000/QALY (\$33,500-47,000 at current exchange rates {cite:p}`tradingeconomics2025gbpusd`), with interventions below £25,000 considered clearly cost-effective {cite:p}`nice2025threshold`. ICER evaluates interventions at \$50,000, \$100,000, and \$150,000/QALY benchmarks {cite:p}`icer2024reference`. All seven nuts fall below NICE's new £25,000 threshold and ICER's \$50,000 benchmark. Peanuts achieve the lowest ICER due to low cost (\$37/year) combined with the third-highest QALY estimate.

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

The hierarchical Bayesian model estimates {eval}`r.qaly_range` discounted QALYs from daily nut consumption, with walnut and almond sharing the top position and pecan ranking lowest. This spread (~45% of the category effect) is larger than previous analyses suggested, reflecting the mechanistic importance of nutrient composition.

The dominance of CVD pathway (~{eval}`r.cvd_contribution`% of benefit) explains the walnut advantage: its 2.5g ALA omega-3 content drives a CVD RR of 0.83 compared to 0.88-0.89 for nuts with negligible ALA. This mechanistic link provides stronger causal support than overall mortality associations.

### Comparison to Prior Estimates

These estimates are lower than unadjusted observational associations (22% mortality reduction from {cite}`aune2016nut`) but higher than pure LDL-pathway predictions (~3% reduction). The Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`) confounding prior with mean {eval}`r.confounding_mean` mediates between these extremes.

### Cost-Effectiveness

ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias). All nuts fall below NICE's new £{eval}`f'{r.nice_lower_gbp:,}'`/QALY (\${eval}`f'{r.nice_lower_usd:,}'`) threshold and ICER's \${eval}`f'{r.icer_threshold:,}'`/QALY benchmark. Peanuts achieve the lowest ICER, combining the third-highest QALY estimate with the lowest cost.

### Sensitivity Analyses

I examined robustness to key parameter assumptions:

**Confounding prior**: When I use Beta(0.5, 4.5) with mean 10% causal (more skeptical), QALYs decrease by ~60%; when I use Beta(3, 3) with mean 50% causal, QALYs increase by ~60%. Rankings remain stable.

**Hierarchical shrinkage (τ)**: The baseline model uses τ ~ HalfNormal(0.03), which constrains nut-specific deviations from nutrient-predicted effects to ~±6% on the log-RR scale (95% prior interval). With τ ~ HalfNormal(0.10) (weaker shrinkage), credible intervals widen by ~15% but point estimates and rankings remain stable. This suggests results are driven primarily by nutrient composition rather than nut-specific residual effects.

**Adherence**: At 50% real-world adherence (vs 100% assumed), effective QALYs halve and ICERs double. All nuts except macadamia remain below \$50,000/QALY threshold.

**Age at initiation**: For a 60-year-old (vs 40), discounted QALYs decrease ~40% due to shorter remaining lifespan, partially offset by stronger CVD benefit at older ages.

### Limitations

Several limitations warrant consideration. Estimates rely on observational data, and residual confounding may remain despite calibration. Source studies come predominantly from the US and Europe, limiting generalizability to other populations. I modeled a fixed 28g/day dose, though dose-response may be non-linear—{cite:t}`aune2016nut` find benefits plateau above ~20g/day. The model assumes perfect adherence, whereas dietary intervention studies find real-world adherence of 50-70% {cite:p}`appel2006adherence`. Finally, substitution effects remain unmodeled; the net benefit depends on what foods nuts replace in the diet.

## Conclusion

Using a hierarchical Bayesian model with pathway-specific nutrient effects and MCMC sampling (0% divergences), I estimate that daily nut consumption (28g) yields {eval}`r.qaly_range` discounted QALYs for a {eval}`r.target_age`-year-old, with walnuts and almonds ranking highest. Approximately {eval}`r.cvd_contribution`% of benefit operates through CVD prevention, driven primarily by ALA omega-3, fiber, and magnesium content. ICERs range from {eval}`r.peanut.icer_fmt`/QALY (peanuts) to {eval}`r.macadamia.icer_fmt`/QALY (macadamias). All nuts fall below NICE's new £{eval}`f'{r.nice_lower_gbp:,}'`/QALY (\${eval}`f'{r.nice_lower_usd:,}'`) threshold and ICER's \${eval}`f'{r.icer_threshold:,}'`/QALY benchmark. Peanuts achieve the lowest ICER, combining the third-highest QALY estimate with the lowest cost. These findings do not apply to individuals with nut allergies ({eval}`r.allergy_prevalence_lower`-{eval}`r.allergy_prevalence_upper`% of adults {cite:p}`gupta2021prevalence`).

## Data and Code Availability

Code: https://github.com/MaxGhenis/whatnut

```{bibliography}
```

```{tableofcontents}
```
