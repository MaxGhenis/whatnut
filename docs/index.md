# What Nut? A Bayesian Analysis of Quality-Adjusted Life Years from Nut Consumption

**Max Ghenis**

max@maxghenis.com

## Abstract

Nut consumption is consistently associated with reduced mortality in observational studies, but translating these findings into actionable health guidance requires quantifying benefits in meaningful units. We present a Bayesian Monte Carlo framework for estimating quality-adjusted life years (QALYs) gained from daily consumption of seven common nut types. Drawing on meta-analytic evidence from {cite}`aune2016nut`, comprising 819,448 participants, and nut-specific randomized controlled trials, we estimate that consuming 28g/day of any nut yields approximately 2.5 QALYs (95% credible interval: 1.0-4.5) over a lifetime for a 40-year-old adult in the general population. Critically, the difference between the highest-ranked nut (walnuts, 2.9 QALYs) and lowest-ranked (cashews, 2.2 QALYs) is modest compared to the benefit of consuming any nut versus none. After applying a conservative 20% discount for residual confounding, we find that all nut types remain highly cost-effective at \$40-260 per QALY gained. These findings support public health messaging that emphasizes consistent nut consumption over optimal nut selection.

## Introduction

Epidemiological evidence consistently demonstrates that nut consumption is associated with reduced all-cause mortality. The landmark meta-analysis by Aune and colleagues {cite}`aune2016nut`, synthesizing data from 20 prospective cohort studies comprising 819,448 participants, found that consuming one serving (28g) of nuts daily was associated with a 22% reduction in all-cause mortality (relative risk 0.78, 95% CI: 0.72-0.84). Similar findings have been reported by {cite}`bao2013association` in the Nurses' Health Study and Health Professionals Follow-up Study (n=118,962) and by {cite}`grosso2015nut` in an independent meta-analysis (n=354,933).

However, translation of these epidemiological findings into practical health guidance faces several challenges. First, most studies examine "nuts" as a single category, obscuring potential differences between nut types. Second, observational studies cannot fully distinguish causal effects from confounding by healthy lifestyle factors. Third, the clinical significance of relative risk reductions is difficult for both clinicians and patients to interpret.

Quality-adjusted life years (QALYs) provide a standardized metric for comparing health interventions, incorporating both quantity (life expectancy) and quality (health-related quality of life) of survival. QALYs are widely used in cost-effectiveness analyses by bodies such as the UK's National Institute for Health and Care Excellence (NICE) and the US Institute for Clinical and Economic Review (ICER).

In this paper, we develop a Bayesian Monte Carlo framework for estimating QALY gains from nut consumption, addressing three key questions: (1) How large is the expected benefit from regular nut consumption? (2) How do different nut types compare? (3) How sensitive are these estimates to assumptions about residual confounding?

## Methods

### Evidence Sources

We constructed a hierarchical evidence base drawing on four categories of sources, in order of priority:

1. **Meta-analyses of mortality outcomes**: {cite}`aune2016nut` and {cite}`grosso2015nut` provided pooled estimates for all-cause mortality.

2. **Large prospective cohort studies**: {cite}`bao2013association` and {cite}`guasch2017nut` provided nut-specific associations.

3. **Randomized controlled trials**: PREDIMED {cite}`ros2008mediterranean`, WAHA {cite}`rajaram2021walnuts`, and nut-specific lipid trials ({cite}`delgobbo2015effects`; {cite}`hart2025pecan`; {cite}`guarneiri2021pecan`; {cite}`mah2017cashew`) informed nut-specific adjustment factors.

4. **Nutrient composition data**: USDA FoodData Central provided standardized nutrient profiles.

All sources with primary research findings included DOIs for verification.

### Statistical Model

We employed a Bayesian Monte Carlo simulation with 10,000 iterations. For each iteration, we:

1. Sampled a base hazard ratio from a log-normal distribution centered on the Aune et al. meta-analytic estimate: HR ~ LogNormal(log(0.78), 0.08).

2. Applied a nut-specific adjustment factor. Each nut received an adjustment factor (mean, SD) based on available nut-specific evidence: walnuts (1.15, 0.08), pistachios (1.08, 0.10), almonds (1.00, 0.06), pecans (1.00, 0.12), macadamias (1.02, 0.12), peanuts (0.95, 0.07), and cashews (0.95, 0.12). Adjustment factors greater than 1.0 indicate stronger protective effects; higher standard deviations reflect greater uncertainty due to limited evidence.

3. Converted hazard ratios to years of life gained using a proportional hazards approximation calibrated to published life-table analyses.

4. Applied a quality weight sampled from Beta(17, 3) with mean 0.85, reflecting age-adjusted health-related quality of life.

5. Applied a confounding adjustment sampled from Beta(8, 2) with mean 0.80, representing our prior belief that approximately 80% of the observed association is causal after accounting for residual healthy-user bias.

The final QALY estimate for each iteration combined mortality-related life years gained and quality-of-life improvements over remaining life expectancy.

### Confounding Sensitivity Analysis

Although the source meta-analyses adjusted for measured confounders (age, sex, BMI, smoking, alcohol, physical activity), residual confounding from unmeasured factors likely remains. We addressed this through two approaches:

First, we applied an explicit confounding discount. The Beta(8, 2) prior implies a mean 20% reduction from observed effects, with 95% of values falling between 50% and 98% of observed effects.

Second, we calculated the E-value {cite}`mathur2020sensitivity` for the primary estimate. For HR=0.78, the E-value is approximately 1.8, meaning an unmeasured confounder would need associations of at least 1.8 with both nut consumption and mortality to fully explain the observed effect. This exceeds typical effect sizes for moderate socioeconomic confounders such as education or income.

### Target Population

Primary analyses assumed a 40-year-old adult from the general population of the United States or Europe, with 40 years of remaining life expectancy. Results may differ for secondary prevention populations (larger absolute benefit expected) or the very elderly (shorter time horizon). Those with nut allergies (1-2% of population) were excluded.

## Results

### Primary Finding

Across all nut types, the median QALY gain from daily consumption of 28g was 2.5 (95% credible interval: 1.0-4.5). The probability of any positive effect exceeded 95% for all nut types.

### Nut-Specific Estimates

Estimated QALY gains by nut type, ranked by median:

| Nut | Median QALYs | 95% CI | Evidence Strength |
|-----|--------------|--------|-------------------|
| Walnut | 2.9 | 1.2-5.1 | Strong |
| Pistachio | 2.7 | 1.0-4.8 | Moderate |
| Macadamia | 2.6 | 0.9-4.9 | Moderate |
| Almond | 2.5 | 1.1-4.4 | Strong |
| Pecan | 2.5 | 0.8-4.8 | Moderate |
| Peanut | 2.4 | 1.0-4.2 | Strong |
| Cashew | 2.2 | 0.7-4.4 | Limited |

The spread between the highest (walnuts) and lowest (cashews) ranked nuts was 0.7 QALYs, substantially smaller than the benefit of any nut versus none (2.5 QALYs).

### Cost-Effectiveness

At typical US retail prices (2025), estimated cost per QALY gained ranged from \$40 (peanuts) to \$260 (macadamias). All values fall well below standard cost-effectiveness thresholds of \$50,000-100,000 per QALY in the United States and £20,000-30,000 in the United Kingdom.

### Uncertainty Quantification

Following Bayesian principles, nuts with limited RCT evidence (cashews, pecans, macadamias) received wider credible intervals rather than lower point estimates. This approach avoids penalizing options with sparse evidence while appropriately representing uncertainty.

## Discussion

Our analysis yields three principal findings with implications for clinical practice and public health messaging.

First, regular nut consumption appears to confer substantial health benefits. An expected gain of 2.5 QALYs is comparable to other well-established preventive interventions. For context, comprehensive Mediterranean diet interventions have been estimated to yield 2-3 QALYs, and smoking cessation yields 3-5 QALYs depending on age of cessation.

Second, the choice of nut type matters far less than the choice to consume nuts at all. While walnuts showed a modest advantage—consistent with their unique omega-3 (ALA) content and strong RCT evidence from PREDIMED and WAHA trials—the difference between "best" and "worst" nut types (0.7 QALYs) was less than 30% of the category effect. This finding supports pragmatic messaging: "Eat whichever nut you will actually eat consistently."

Third, even after conservative adjustment for residual confounding, nut consumption remains highly cost-effective. At \$40-260 per QALY, nuts represent exceptional value compared to pharmaceutical interventions or medical procedures that often exceed \$50,000 per QALY.

### Limitations

Several limitations warrant consideration. First, our estimates rely heavily on observational data, and residual confounding cannot be fully excluded. We addressed this through explicit confounding discounts and E-value analysis, but the true causal effect may be smaller (or larger) than estimated.

Second, generalizability is limited to populations represented in the source studies, predominantly from the United States and Europe. Effects in other populations may differ.

Third, we modeled a fixed dose of 28g/day based on the meta-analytic reference. Dose-response relationships may be non-linear, with diminishing returns above this threshold.

Fourth, we assumed perfect adherence. Real-world intermittent consumption would likely yield smaller benefits.

### Implications for Practice

For clinical encounters, these findings suggest that specific nut recommendations are less important than encouraging any regular nut consumption. For patients concerned about cost, peanuts offer comparable benefits at one-sixth the price of premium options. For those with specific taste preferences, reassurance that their preferred nut provides meaningful benefit may improve adherence.

For public health communication, the key message is simple: a handful of any nuts, daily, may add years to your life. The details of which nut matter less than consistency.

## Conclusion

Bayesian Monte Carlo analysis of meta-analytic and trial evidence suggests that daily nut consumption yields approximately 2.5 quality-adjusted life years for adults in the general population. Differences between nut types are modest compared to the overall category effect. These findings support public health guidance emphasizing consistent nut consumption over optimal nut selection.

## Data and Code Availability

All analyses were conducted using the `whatnut` Python package, available at https://github.com/MaxGhenis/whatnut. The package provides fully reproducible Monte Carlo simulations with seeded random number generation, comprehensive test coverage, and all evidence sources with DOIs.

```{bibliography}
```

```{tableofcontents}
```
