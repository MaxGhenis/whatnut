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

## Bayesian MCMC Algorithm

The analysis uses a hierarchical Bayesian model with non-centered parameterization, implemented in PyMC. The model structure:

**Priors:**
- Nutrient effects: $\beta_{nutrient,pathway} \sim \text{Normal}(\mu_{meta}, \sigma_{meta})$ from Table 2
- Hierarchical shrinkage: $\tau_{pathway} \sim \text{HalfNormal}(0.03)$
- Standardized deviations: $z_{nut,pathway} \sim \text{Normal}(0, 1)$
- Confounding fraction: $c \sim \text{Beta}(1.5, 4.5)$

**Model:**
1. Compute nutrient-predicted effect: $\theta_{nutrients} = \sum_{n} \beta_n \cdot \text{composition}_{nut,n}$
2. Add hierarchical deviation (non-centered): $\theta_{true} = \theta_{nutrients} + \tau \cdot z$
3. Apply nut-specific adjustment prior: $\theta_{adjusted} = \theta_{true} + \log(a_{nut,pathway})$
   - Where $a$ is the RR-scale multiplier from the table below (e.g., walnut CVD $a = 1.25$)
   - Equivalently: $RR_{adjusted} = RR_{true} \times a$
4. Apply confounding: $\theta_{causal} = c \cdot \theta_{adjusted}$
5. Convert to RR: $RR_{pathway} = \exp(\theta_{causal})$

**MCMC Sampling:**
- 4 chains, 1000 warmup + 1000 draws each = 4000 posterior samples
- NUTS sampler with target_accept=0.95, max_treedepth=12
- Seed=42 for reproducibility

**Lifecycle Integration:**
For each of 500 posterior samples:
1. Extract pathway-specific RRs and confounding fraction
2. Compute age-weighted mortality reduction using CDC life tables
3. Sample quality weight: $q \sim \text{Beta}(17, 3)$, mean = 0.85
4. Compute discounted QALYs (3% annual rate)

## Nut-Specific Adjustment Priors

These adjustment factors are **priors** used in the hierarchical model (step 3 above: $\theta_{adjusted} = \theta_{true} + \log(a_{nut,pathway})$). The adjustment is **additive on the log-RR scale**, which is equivalent to multiplicative on the RR scale: $RR_{adjusted} = RR_{nutrients} \times a$. For example, walnut's CVD adjustment of 1.25 means $\log(1.25) = 0.22$ is added to the log-RR, amplifying the protective effect by 25%.

### Derivation of Adjustment Values

Adjustments capture **residual effects** from nut-specific RCTs after accounting for nutrient composition. The derivation for walnut's CVD adjustment illustrates the method:

1. **PREDIMED RCT** {cite:p}`ros2008mediterranean`: Walnut group showed ~30% CVD risk reduction
2. **Nutrient-predicted effect**: Based on 2.5g ALA × (-0.15 log-RR/g) + other nutrients = ~20% reduction
3. **Residual**: 30% - 20% = 10% additional benefit, plus ~15% for polyphenol effects from WAHA {cite:p}`rajaram2021walnuts`
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

**Note on cancer adjustments**: Previous versions applied a 10% cancer penalty to peanuts based on aflatoxin concerns. However, US FDA regulations limit aflatoxin to <20 ppb, and epidemiological studies show no excess cancer risk in US peanut consumers {cite:p}`wu2015aflatoxin`. The cancer adjustment is now set to 1.00 (neutral). Similarly, macadamia and pecan cancer adjustments are set to 1.00 given insufficient evidence for deviation from nutrient predictions.

Nuts with limited evidence (macadamia, pecan, cashew) receive higher SD values to reflect greater uncertainty.

## Confounding Prior Derivation

The evidence-optimized prior Beta(1.5, 4.5) was derived by minimizing squared error to calibration targets:

| Source | Target Causal % | Weight | Rationale |
|--------|-----------------|--------|-----------|
| LDL pathway calibration | 12% | 0.30 | Mechanistic, most direct |
| Sibling comparisons | 20% | 0.30 | Genetic confounding control |
| Golestan cohort (Iran) | 40% | 0.40 | Cross-cultural, shows effect persists |

**Derivation**: The weighted mean is $\bar{p} = 0.30(0.12) + 0.30(0.20) + 0.40(0.40) = 0.256 \approx 0.25$. We inflate variance beyond the weighted sample variance ($\sigma^2_{sample} = 0.015$) to $\sigma^2 = 0.027$ to capture additional epistemic uncertainty about confounding mechanisms. Method of moments yields $\alpha = 1.55 \approx 1.5$, $\beta = 4.50$.

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

## Alternative Approach: Direct Monte Carlo Simulation

The main analysis uses a hierarchical Bayesian model with nutrient-derived priors and MCMC sampling. This section presents the simpler Monte Carlo approach used in earlier versions of this analysis, which serves as a validation check.

### Monte Carlo Model (10,000 iterations)

**Step 1: Sample cause-specific relative risks from meta-analysis**

For each iteration, sample from log-normal distributions based on {cite:t}`aune2016nut`:
- CVD mortality: RR ~ LogNormal(log(0.75), 0.03)
- Cancer mortality: RR ~ LogNormal(log(0.87), 0.04)
- Other mortality: RR ~ LogNormal(log(0.90), 0.03)

**Step 2: Apply nut-specific pathway adjustments**

Nut-specific adjustments are exponents on cause-specific RRs, reflecting RCT evidence beyond meta-analysis averages:

| Nut | CVD Adj (SD) | Cancer Adj (SD) | Other Adj (SD) |
|-----|--------------|-----------------|----------------|
| Walnut | 1.25 (0.08) | 1.05 (0.10) | 1.10 (0.10) |
| Almond | 1.00 (0.06) | 1.05 (0.08) | 1.00 (0.06) |
| Peanut | 0.98 (0.06) | 0.90 (0.08) | 0.98 (0.08) |

**Step 3: Apply confounding adjustment**

Sample causal fraction from Beta(1.5, 4.5) with mean 0.25 and apply to log-RR.

**Step 4: Compute lifecycle QALYs**

Using CDC life tables, age-varying cause fractions, quality weights from Beta(17, 3), and 3% discounting.

### Comparison of Approaches

| Approach | Mean QALY | 95% CI | Computation |
|----------|-----------|--------|-------------|
| Monte Carlo (direct RR) | 0.08 | [0.01, 0.24] | 10,000 iterations, ~1 second |
| MCMC (nutrient-derived) | 0.11-0.20 | [0.01, 0.56] | 4,000 samples, ~10 minutes |

### Why Results Are Similar

Both approaches yield comparable estimates because:
1. Both use the same confounding calibration (Beta(1.5, 4.5))
2. Both use the same pathway decomposition (CVD/cancer/other)
3. The nutrient-derived priors in MCMC are calibrated to match meta-analysis estimates

### Why Use the MCMC Approach?

The hierarchical Bayesian model provides:
- **Mechanistic interpretability**: Effects attributed to specific nutrients (ALA, fiber, magnesium)
- **Principled shrinkage**: Poorly-evidenced nuts shrink toward nutrient-predicted effects
- **Transparent priors**: Each prior is traceable to independent meta-analyses
- **Convergence diagnostics**: R-hat, ESS, divergences confirm valid inference

The Monte Carlo approach is appropriate for quick estimates or validation. The MCMC model is preferred for publication and comparative analysis.

## Limitations

1. **Confounding**: Our 25% causal estimate is uncertain (95% CI: 2-63%). True value could be higher or lower.
2. **Generalizability**: Most studies from Western populations (US, Europe, Australia)
3. **Dose-response**: We model 28g/day; effects may be non-linear above this threshold
4. **Nut-specific evidence**: Limited RCT evidence for cashews, pecans, macadamias
5. **Adherence**: Assumes daily consumption; intermittent eating reduces benefits
6. **Competing risks**: Other mortality causes limit achievable gains in elderly populations
