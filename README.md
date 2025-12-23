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

### Quick Start: Use Paper Results (Recommended)
```python
from whatnut.paper_results import r

# Get exact values from the paper (discounted QALYs)
print(f"Walnuts: {r.walnut.qaly} QALYs")  # Output: 0.20
print(f"Peanuts: {r.peanut.icer}")        # Output: $5,700/QALY
print(f"QALY range: {r.qaly_range}")      # Output: 0.11-0.20
```

### Monte Carlo Simulation (Advanced)
```python
from whatnut import MonteCarloSimulation, DEFAULT_PARAMS

sim = MonteCarloSimulation(seed=42)
result = sim.run(DEFAULT_PARAMS)

for nut_result in result.results:
    print(f"{nut_result.nut_id}: {nut_result.median:.2f} life years")
```

**Note on metrics**:
- `paper_results` contains **discounted QALYs** (0.11-0.20) using 3% annual discounting—the standard for cost-effectiveness analysis
- `MonteCarloSimulation` returns **undiscounted life years** (~0.3-0.5)—more intuitive but not directly comparable to paper values
- For exact paper reproduction, use `paper_results`; for custom scenarios, use Monte Carlo

## Key Finding

> **Eating any nut daily yields 0.11-0.20 discounted QALYs** (equivalent to ~5-6 months of healthy life). Walnuts rank highest (0.20 QALYs), peanuts are most cost-effective ($5,700/QALY). The difference between nuts is small—eat whichever you'll consume consistently.

## Documentation

Full methodology and interactive analysis available in the JupyterBook documentation.

## Reproducibility

**Requirements**: Python ≥3.10

### Run Tests
```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
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
- Nutrient data: [USDA FoodData Central](https://fdc.nal.usda.gov/) (2024) - see `src/whatnut/data/nuts.yaml` for FDC IDs
- Mortality data: [CDC NVSS Life Tables](https://www.cdc.gov/nchs/products/life_tables.htm) (2021)
- Meta-analysis estimates: Published literature (see `docs/references.bib`)

## License

MIT
