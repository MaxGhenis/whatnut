# What Nut?

Bayesian QALY analysis of nut consumption.

## Overview

This package provides a rigorous, evidence-based analysis of the health effects of different nut types, quantified in Quality-Adjusted Life Years (QALYs).

## Key Features

- **Evidence-traced claims**: Every health claim links to primary sources (meta-analyses, RCTs, cohort studies)
- **Monte Carlo simulation**: 10,000 iterations with full uncertainty quantification
- **Bayesian approach**: Sparse evidence widens confidence intervals, doesn't lower point estimates

## Installation

```bash
pip install whatnut
```

## Usage

```python
from whatnut import MonteCarloSimulation, DEFAULT_PARAMS

sim = MonteCarloSimulation(seed=42)
result = sim.run(DEFAULT_PARAMS)

for nut_result in result.results:
    print(f"{nut_result.nut_id}: {nut_result.median:.2f} QALYs (95% CI: {nut_result.ci_95})")
```

## Key Finding

> **Eating any nut daily: ~2.5 QALYs.** The difference between "best" (walnuts) and "worst" (cashews) is only ~0.7 QALYs. Eat whichever nut you'll actually eat consistently.

## Documentation

Full methodology and interactive analysis available in the JupyterBook documentation.

## License

MIT
