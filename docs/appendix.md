# Technical Appendix

## Target population

This analysis applies to adults aged 30-70 years (the primary analysis uses a 40-year-old baseline) drawn from the general population rather than specifically high-risk groups, with estimates derived primarily from US and European cohorts. Individuals with nut allergies (~1-2% of the population) are excluded. The model does not cover secondary prevention (existing CVD), the very elderly (80+), or non-Western populations.

## Monte Carlo uncertainty propagation algorithm

The analysis uses a hierarchical forward sampling model with non-centered parameterization. Since there is no likelihood function linking to outcome data, inference is via direct Monte Carlo sampling from priors rather than MCMC.

**Priors:**
- Nutrient effects: $\beta_{nutrient,pathway} \sim \text{Normal}(\mu_{meta}, \sigma_{meta})$ from Table 2
- Hierarchical shrinkage: $\tau_{pathway} \sim \text{HalfNormal}(0.03)$
- Standardized deviations: $z_{nut,pathway} \sim \text{Normal}(0, 1)$
- Confounding fraction: $c \sim \text{Beta}(2.5, 2.5)$

**Justification for τ ~ HalfNormal(0.03):** The scale parameter 0.03 constrains nut-specific deviations to approximately ±6% on the log-RR scale at 2 standard deviations (95% prior interval). This was calibrated through pilot analyses. Setting τ ~ HalfNormal(0.01) produced excessive shrinkage, making all nuts nearly identical despite known compositional differences. Setting τ ~ HalfNormal(0.10) produced implausibly wide between-nut variation (±20% deviations), larger than compositional differences would justify. The chosen value of τ ~ HalfNormal(0.03) balances information sharing across nuts with nut-specific flexibility, allowing walnuts to differ from almonds by the magnitude seen in RCT residual effects (~10-15%).

**Model:**
1. Compute nutrient-predicted effect: $\theta_{nutrients} = \sum_{n} \beta_n \cdot \text{composition}_{nut,n}$
2. Add hierarchical deviation (non-centered): $\theta_{true} = \theta_{nutrients} + \tau \cdot z$
3. Apply nut-specific adjustment: $RR_{adjusted} = RR_{true}^{a_{nut,pathway}}$
   - Where $a$ is the adjustment exponent from the table below (e.g., walnut CVD $a = 1.25$)
   - On log scale: $\theta_{adjusted} = a \times \theta_{true}$
   - For protective effects (RR < 1), adjustments $a > 1$ amplify the effect
4. Apply confounding: $\theta_{causal} = c \cdot \theta_{adjusted}$
5. Convert to RR: $RR_{pathway} = \exp(\theta_{causal})$

**Monte Carlo sampling:** The model draws 10,000 forward samples from priors (no MCMC is needed since there is no likelihood). A fixed seed of 42 ensures reproducibility, and runtime is approximately 30 seconds using pure NumPy with no external inference library required.

**Lifecycle integration:** For each of the 10,000 samples, the model extracts pathway-specific RRs (already confounding-adjusted), computes age-weighted mortality reduction using CDC life tables, applies EQ-5D quality weights by age (population norms), and computes discounted QALYs at a 3% annual rate.

## Nut-specific adjustment priors

These adjustment factors are **priors** used in the hierarchical model. The adjustment is applied as an **exponent** on the RR scale: $RR_{adjusted} = RR_{nutrients}^{a}$. On the log-RR scale, this is multiplicative: $\log(RR_{adjusted}) = a \times \log(RR_{nutrients})$. For protective effects (RR < 1), adjustments > 1 amplify the effect. For example, walnut's CVD adjustment of 1.25 applied to a nutrient-predicted RR of 0.80 yields $0.80^{1.25} = 0.75$ (a 25% mortality reduction becomes a 25% stronger effect, yielding 25% × 1.25 ≈ 31% reduction).

### Derivation of adjustment values

Adjustments capture **residual effects** from nut-specific RCTs after accounting for nutrient composition. The derivation for walnut's CVD adjustment illustrates the method:

1. **PREDIMED RCT** {cite:p}`ros2008mediterranean`: Walnut group showed ~30% CVD risk reduction
2. **Nutrient-predicted effect**: Based on 2.5g ALA × (-0.05 log-RR/g) + other nutrients = ~15% reduction
3. **Residual**: 30% - 15% = 15% additional benefit, plus polyphenol effects from WAHA {cite:p}`rajaram2021walnuts`
4. **Adjustment**: exp(0.22) ≈ 1.25 (25% stronger than nutrients alone)

Almonds serve as the reference nut (adjustment = 1.00) because their RCT effects are well-explained by nutrient composition (vitamin E, fiber, MUFA). This ensures adjustments represent genuine "beyond-nutrient" effects rather than artifacts.

**Independence from nutrient priors**: The nutrient priors (Table 2) use effect estimates from studies that pool across food sources (e.g., Naghshi 2021 for ALA includes fish and plant sources). The nut-specific adjustments use residual effects from nut-only RCTs, avoiding double-counting.

| Nut | CVD Adj | Cancer Adj | Other Adj | Evidence | Rationale |
|-----|---------|------------|-----------|----------|-----------|
| Walnut | 1.25 (0.08) | 1.05 (0.10) | 1.10 (0.10) | Strong | PREDIMED, WAHA residual effects beyond nutrients |
| Pistachio | 1.12 (0.08) | 1.02 (0.10) | 1.05 (0.10) | Moderate | Del Gobbo: lipid improvements exceed predictions |
| Almond | 1.00 (0.06) | 1.05 (0.08) | 1.00 (0.06) | Strong | Reference nut, effects well-explained by nutrients |
| Pecan | 1.08 (0.10) | 1.00 (0.12) | 1.00 (0.12) | Moderate | {cite}`hart2025pecan`, {cite}`guarneiri2021pecan` |
| Macadamia | 1.08 (0.10) | 1.00 (0.15) | 1.05 (0.12) | Moderate | FDA qualified health claim, MUFA profile |
| Peanut | 0.98 (0.06) | 1.00 (0.08) | 0.98 (0.08) | Strong | {cite}`bao2013association` (n=118,962) |
| Cashew | 0.95 (0.10) | 0.95 (0.12) | 0.95 (0.12) | Limited | {cite}`mah2017cashew`, wider CIs reflect uncertainty |

**Note on cancer adjustments**: Previous versions applied a 10% cancer penalty to peanuts based on aflatoxin concerns. However, US FDA regulations limit aflatoxin to <20 ppb, and epidemiological studies show no excess cancer risk in US peanut consumers {cite:p}`wu2010aflatoxin`. The cancer adjustment is now set to 1.00 (neutral). Similarly, macadamia and pecan cancer adjustments are set to 1.00 given insufficient evidence for deviation from nutrient predictions.

Nuts with limited evidence (macadamia, pecan, cashew) receive higher SD values to reflect greater uncertainty.

## Confounding prior derivation

I adopt a **symmetric, weakly informative** Beta(2.5, 2.5) prior with mean 0.50 and 95% interval: 12-88%. This prior reflects genuine uncertainty about the causal fraction rather than a precise calibration.

Three evidence sources inform this choice:

| Source | Implied Causal % | Interpretation |
|--------|-----------------|----------------|
| LDL pathway calibration | ~12% (floor) | Mechanistic, most direct; but only one of many causal pathways |
| Sibling comparisons | 50-70% | Genetic confounding control; no nut-specific studies exist |
| Golestan cohort (Iran) | ≥50-100% | Cross-cultural, shows effect persists without Western healthy-user bias |

The LDL pathway provides a **floor** on the causal fraction (not a ceiling), since nuts affect multiple causal pathways beyond LDL. The Golestan cohort shows effects at least as large as Western estimates, consistent with a high causal fraction. The symmetric Beta(2.5, 2.5) represents an agnostic stance that allows the full range of possibilities.

**Sensitivity analysis**: Beta(1.5, 4.5) with mean 0.25 is presented as a skeptical alternative. Rankings remain stable across prior specifications (see Table 7 in main text).

## Cost-effectiveness model

### Data sources

The cost-effectiveness model draws on CDC National Vital Statistics (2021) life tables for age-specific mortality, age-varying health-related quality of life weights from Sullivan et al. (2006), a 3% annual discount rate (standard for NICE, ICER, and WHO-CHOICE), and USDA ERS retail prices (2024) for cost data.

### Lifecycle model

For a 40-year-old beginning daily nut consumption:
The model estimates 0.22-0.96 additional life years (3-12 months) across nut types, corresponding to 0.14-0.59 undiscounted QALYs (life years weighted by age-specific EQ-5D quality weights) and 0.04-0.19 discounted QALYs (at 3% annual discounting over the remaining lifespan). ICERs range from approximately $11,900/QALY (peanuts) to $57,000/QALY (cashews).

## E-value analysis

Per {cite}`vanderweele2017sensitivity`, the E-value quantifies the minimum strength of association an unmeasured confounder would need with both exposure and outcome to fully explain an observed association.

For a protective exposure with hazard ratio $HR$, I first convert to relative risk $RR = 1/HR$, then calculate:

$$E\text{-value} = RR + \sqrt{RR \times (RR - 1)}$$

For HR = 0.78:
- $RR = 1/0.78 = 1.28$
- $E\text{-value} = 1.28 + \sqrt{1.28 \times 0.28} = 1.28 + 0.60 \approx 1.8$

An unmeasured confounder would need RR ≥ 1.8 with both nut consumption and mortality to fully explain the observed effect.

## Pathway-specific mortality effects

From {cite}`aune2016nut`:

| Cause of Death | Relative Risk | 95% CI | Deaths in Meta-Analysis |
|----------------|--------------|--------|------------------------|
| CVD | 0.75 | 0.71-0.79 | 20,381 |
| Cancer | 0.87 | 0.80-0.93 | 21,353 |
| Other | 0.90 | 0.85-0.95 | Assumed |

### Age-varying cause fractions

Cause-of-death proportions vary by age (CDC WONDER 2021):

| Age | CVD | Cancer | Other |
|-----|-----|--------|-------|
| 40 | 20% | 25% | 55% |
| 50 | 25% | 35% | 40% |
| 60 | 30% | 35% | 35% |
| 70 | 35% | 30% | 35% |
| 80 | 40% | 20% | 40% |

CVD fraction increases with age; CVD has the lowest RR (0.75).

## Comparison with direct meta-analysis sampling

An alternative approach samples cause-specific relative risks directly from meta-analysis estimates (e.g., log-normal distributions based on {cite:t}`aune2016nut`) rather than deriving them from nutrient composition. This simpler approach yields broadly comparable results because the nutrient-derived priors are calibrated to match meta-analysis estimates.

The nutrient-derived approach used in this analysis provides several advantages over direct meta-analysis sampling. First, it offers mechanistic interpretability by attributing effects to specific nutrients (ALA, fiber, magnesium). Second, poorly-evidenced nuts shrink toward nutrient-predicted effects through principled hierarchical shrinkage. Third, each prior is traceable to independent meta-analyses, ensuring transparency. Fourth, compositional differences drive differential estimates across nut types—for example, the model can distinguish walnuts from almonds based on ALA content rather than relying on a single pooled nut estimate.

Both approaches use forward Monte Carlo sampling (no MCMC is needed since there is no likelihood function). The nutrient-derived approach is preferred for its mechanistic transparency and ability to differentiate nuts based on composition.

## Limitations

The 50% causal fraction estimate is uncertain (95% interval: 12-88%), and the true value could be higher or lower. Most source studies come from Western populations (US, Europe, Australia), limiting generalizability. The model assumes 28g/day, though effects may be non-linear above this threshold. RCT evidence for cashews, pecans, and macadamias remains limited relative to walnuts and almonds. The base case assumes daily consumption; intermittent intake would reduce estimated benefits proportionally. Finally, competing risks from other mortality causes limit the achievable gains in elderly populations.
