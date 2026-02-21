# What Nut?

Monte Carlo analysis of life expectancy from nut consumption.

## Overview

This package provides a rigorous, evidence-based analysis of the health effects of different nut types, quantified in life years and Quality-Adjusted Life Years (QALYs).

## Key features

- **Evidence-traced claims**: Every health claim links to primary sources (meta-analyses, RCTs, cohort studies)
- **Monte Carlo uncertainty propagation**: 10,000 samples with full uncertainty quantification
- **Hierarchical nutrient model**: Effects derived from nutrient composition, not just nut-level associations

## Installation

```bash
# Install from GitHub (not yet on PyPI)
pip install git+https://github.com/MaxGhenis/whatnut.git

# Or clone and install locally
git clone https://github.com/MaxGhenis/whatnut.git
cd whatnut
pip install -e .
```

**Requirements**: Python >=3.10

## Usage

### Quick start: use paper results (recommended)
```python
from whatnut.results import r

# Get exact values from the paper
print(f"Walnuts: {r.walnut.life_years_fmt} life years")   # Output: 0.96
print(f"Walnuts: {r.walnut.qaly} QALYs (discounted)")     # Output: 0.19
print(f"Peanuts: {r.peanut.icer_fmt}/QALY")               # Output: $11,889/QALY
print(f"Life years range: {r.life_years_range}")           # Output: 0.22-0.96
```

### Run analysis (advanced)
```python
from whatnut.pipeline import run_analysis

results = run_analysis(n_samples=10_000, seed=42)
for nid, na in results.nuts.items():
    print(f"{nid}: {na.life_years_mean:.2f} life years, QALY={na.qaly_mean:.2f}")
```

**Note on metrics**:
- **Life years** (0.22-0.96) are the primary metric — the actual expected increase in lifespan
- **QALYs discounted** (0.04-0.19) weight life years by quality of life and discount at 3%/year
- **QALYs undiscounted** (0.14-0.59) weight life years by quality of life without discounting

## Key finding

> **Eating any nut daily yields 0.22-0.96 additional life years** (2.6-11.5 months). Walnuts rank highest due to ALA omega-3 content; peanuts are most cost-effective ($11,889/QALY). The difference between nuts is substantial — walnuts provide ~4x more life years than cashews.

## Documentation

Full methodology and interactive analysis available in the MyST documentation.

## Reproducibility

**Requirements**: Python >=3.10

### Run tests
```bash
pip install -e ".[dev]"
python -m pytest tests/ -v
```

### Generate results
All paper values are generated from code and stored in `src/whatnut/data/results.json`:
```bash
python -m whatnut.pipeline --generate
```

**Runtime**: ~30 seconds (pure numpy, no external inference library)
**Reproducibility**: Same seed (42) produces identical results across platforms.

### Build the paper
```bash
cd docs/
myst build --html  # or --pdf
```

### Data sources
All data are from public sources:
- Nutrient data: [USDA FoodData Central](https://fdc.nal.usda.gov/) (2024) - see `src/whatnut/data/nuts.yaml` for FDC IDs
- Mortality data: [CDC NVSS Life Tables](https://www.cdc.gov/nchs/products/life_tables.htm) (2021)
- Meta-analysis estimates: Published literature (see `docs/references.bib`)

## License

MIT
