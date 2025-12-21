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

> **Eating any nut daily yields 0.11-0.20 discounted QALYs** (equivalent to ~5-6 months of healthy life). Walnuts rank highest (0.20 QALYs), peanuts are most cost-effective ($5,700/QALY). The difference between nuts is small—eat whichever you'll consume consistently.

## Documentation

Full methodology and interactive analysis available in the JupyterBook documentation.

## Reproducibility

**Requirements**: Python ≥3.10

### Run Tests
```bash
pip install whatnut[dev]
pytest tests/ -v
```

### Validate Paper Values
All paper values are stored in `src/whatnut/paper_results.py`. To verify consistency:
```bash
python src/whatnut/paper_results.py
```

### Regenerate from MCMC
To regenerate results from scratch:
```bash
pip install whatnut[bayesian]
python src/whatnut/bayesian_model.py
```

**Hardware requirements**: ~8GB RAM, 4+ CPU cores
**Runtime**: ~10 minutes (4 chains × 2000 samples on Apple M1)
**Note**: MCMC results may vary slightly across hardware due to floating-point differences. For exact reproduction, use precomputed values in `paper_results.py`.

### Build the Paper
```bash
cd docs/
myst build --html  # or --pdf
```

### Data Sources
All data are from public sources:
- Nutrient data: USDA FoodData Central (2024)
- Mortality data: CDC life tables (2021)
- Meta-analysis estimates: Published literature (see references in paper)

## License

MIT
