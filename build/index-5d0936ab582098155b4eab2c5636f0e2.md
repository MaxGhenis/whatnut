# What Nut?

**A Bayesian QALY Analysis of Nut Consumption**

## The Question

How many quality-adjusted life years (QALYs) do you gain from eating different types of nuts?

## Key Finding

> **Eating any nut daily: ~2.5 QALYs.** The difference between "best" (walnuts) and "worst" (cashews) is only ~0.7 QALYs. Eat whichever nut you'll actually eat consistently.

## This Analysis

This document presents a rigorous, evidence-based analysis that:

1. **Traces every claim to primary sources** - Meta-analyses, RCTs, cohort studies
2. **Quantifies uncertainty** - Monte Carlo simulation with 10,000 iterations
3. **Applies Bayesian reasoning** - Sparse evidence widens confidence intervals, doesn't lower point estimates

## Table of Contents

```{tableofcontents}
```

## Quick Start

```python
from whatnut import MonteCarloSimulation, DEFAULT_PARAMS

sim = MonteCarloSimulation(seed=42)
result = sim.run(DEFAULT_PARAMS)

for nut in result.results[:3]:
    print(f"{nut.nut_id}: {nut.median:.2f} QALYs (95% CI: [{nut.ci_95[0]:.1f}, {nut.ci_95[1]:.1f}])")
```
