# What Nut?

Skeptical evidence-synthesis model of the mortality benefit from nut consumption.

## Overview

This package estimates the plausible lifetime health benefit of different nuts using a food-specific version of the newer Optiqal framing: explicit bias/confounding shrinkage, pathway-level effects, lifecycle integration, and transparent uncertainty propagation.

## Key features

- **Evidence-traced claims**: Every health claim links to primary sources (meta-analyses, RCTs, cohort studies)
- **Skeptical by construction**: Strong shrinkage for residual confounding and weak non-CVD pathways
- **Monte Carlo uncertainty propagation**: 10,000 samples with explicit `P(benefit)` and `P(harm)`
- **Hierarchical nutrient model**: Effects derived from nutrient composition, not just nut-level associations
- **Tiered publication-bias shrinkage**: Nut-specific residuals are pulled toward the null by evidence tier (strong/moderate/limited)
- **HR-centered aggregation**: Jensen-corrected so E[RR] matches the exponent of the mean log-RR
- **Separate discounting**: 0% health discounting, 3% cost discounting

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
print(f"Walnuts: {r.walnut.life_years_fmt} life years")   # Output: 0.15
print(f"Walnuts: {r.walnut.qaly} QALYs")                  # Output: 0.10
print(f"Peanuts: {r.peanut.icer_fmt}/QALY")               # Output: $103,938/QALY
print(f"Life years range: {r.life_years_range}")          # Output: 0.03-0.15
```

### Run analysis (advanced)
```python
from whatnut.pipeline import run_analysis

results = run_analysis(n_samples=10_000, seed=42)
for nid, na in results.nuts.items():
    print(f"{nid}: {na.life_years_mean:.2f} life years, QALY={na.qaly_mean:.2f}")
```

**Note on metrics**:
- **Life years** (0.03-0.15) are the primary metric — the model's expected increase in lifespan under skeptical assumptions
- **QALYs** (0.02-0.10) weight those life years by age-specific quality of life with 0% health discounting
- **ICERs** discount costs at 3% annually using the same survival curve as benefits

## Key finding

> **Under skeptical assumptions, daily nut consumption yields about 0.03-0.15 additional life years** (0.4-1.8 months). Walnuts rank highest due to ALA omega-3 content, but the absolute gains are modest and uncertainty remains material for several nut types.

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
