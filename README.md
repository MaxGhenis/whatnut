# What Nut?

Skeptical evidence-synthesis model of the mortality benefit from nut consumption.

## Overview

This package estimates the plausible lifetime health benefit of different nuts using a food-specific adaptation of Optiqal's evidence, lifecycle, reference-case, and decision-reporting layers. What Nut has no runtime dependency on Optiqal; generated results pin the Optiqal source commit used for methodological provenance.

## Key features

- **Evidence-traced claims**: Every health claim links to primary sources (meta-analyses, RCTs, cohort studies)
- **Skeptical by construction**: Strong shrinkage for residual confounding and weak non-CVD pathways
- **Monte Carlo uncertainty propagation**: 10,000 samples with explicit `P(benefit)` and `P(harm)`
- **Hierarchical nutrient model**: Effects derived from nutrient composition, not just nut-level associations
- **Tiered publication-bias shrinkage**: Nut-specific residuals are pulled toward the null by evidence tier (strong/moderate/limited)
- **HR-centered aggregation**: Jensen-corrected so E[RR] matches the exponent of the mean log-RR
- **Reference-case first**: 3% health / 3% cost discounting is primary; 0% health discounting is an explicit sensitivity
- **Decision-first output**: expected NMB and draw-wise probability of optimality include the no-intervention comparator
- **Honest model intervals**: 95% Monte Carlo intervals are not described as confidence or posterior intervals

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
print(f"Walnuts: {r.walnut.qaly} reference-case QALYs")
print(f"Walnuts: {r.walnut.qaly_model_interval}")
print(f"Walnuts: {r.walnut.qaly_undiscounted_fmt} at 0%")
print(f"Walnuts: {r.walnut.icer_fmt}/QALY")               # Output: $211,399/QALY
print(r.decision_summary["recommended_option"])           # No modeled daily-nut intervention.
print(r.peanut.nut_alternative_rank)                       # 1 (conditional among nuts)
print(f"Peanut P(optimal): {r.peanut.p_optimal:.1%}")
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
- **Reference-case QALYs** (0.01-0.03) weight life years by age-specific quality of life and discount health at 3%
- **Undiscounted-health sensitivity QALYs** (0.02-0.10) retain 0% health discounting while costs remain at 3%
- **Expected ICERs** divide expected survival-weighted lifetime gross retail cost by expected reference-case QALYs

The decision comparison is deliberately narrow: add one 28 g/day nut versus no modeled daily-nut intervention. At the illustrative $50,000/QALY valuation, every nut has negative expected NMB, so the model prefers the comparator; peanuts are the highest-ranked nut alternative. Current diet, displaced food cost and calories, substitution, direct morbidity or harms, adherence decay, and mixed-nut stacking are not modeled.

## Key finding

> **Under skeptical assumptions, daily nut consumption yields about 0.03-0.15 additional life years** (0.4-1.8 months). Walnuts have the largest expected health gain, while the decision model prefers no intervention at the stated valuation.

## Documentation

Full methodology, figures, and an interactive tour of the model are at
[maxghenis.com/whatnut](https://maxghenis.com/whatnut). The paper is built
with [Quarto](https://quarto.org) from `docs/index.qmd` and
`docs/appendix.qmd`.

The [architecture note](ARCHITECTURE.md) records how the project would be
structured from scratch, what this refresh adopts now, and which larger
results-changing refactors are intentionally deferred.

## Reproducibility

**Requirements**: Python >=3.10

### Run tests
```bash
uv venv --python 3.13
uv pip install -e ".[dev,docs]"
.venv/bin/python -m pytest tests/ -v
```

### Generate results
All paper values are generated from code and stored in `src/whatnut/data/results.json`:
```bash
.venv/bin/python -m whatnut.pipeline --generate
# Explore another illustrative QALY value without replacing the paper artifact.
.venv/bin/python -m whatnut.pipeline --willingness-to-pay 100000
# Or write a separate, schema-valid scenario artifact.
.venv/bin/python -m whatnut.pipeline --generate --willingness-to-pay 100000 \
  --output tmp/results-wtp-100000.json
```

**Runtime**: typically under a few seconds (pure NumPy, no external inference library)
**Reproducibility**: The committed schema-versioned artifact is generated with
seed 42 and the default $50,000/QALY valuation, then checked against a fresh run
in CI. Strict artifact writes reject NaN/Infinity and replace the prior file
atomically; custom valuations require a separate output path.

### Build the paper
Requires [Quarto](https://quarto.org/docs/get-started/) installed. The setup
above already installs the `[docs]` extras into the project environment.
The paper render regenerates tracked result figures from `results.json` and
input-description figures from the versioned source YAML before including them.

```bash
export QUARTO_PYTHON="$PWD/.venv/bin/python"
export JUPYTER_PREFER_ENV_PATH=1
quarto render docs/ --to html       # HTML + figures into docs/_build/
quarto render docs/ --to pdf        # PDF (needs LaTeX: MacTeX, TeX Live, etc.)
quarto preview docs/                # live reload during edits
```

### Data sources
All data are from public sources:
- Nutrient data: [USDA FoodData Central](https://fdc.nal.usda.gov/) (2024) - see `src/whatnut/data/nuts.yaml` for FDC IDs
- Mortality data: [CDC NVSS Life Tables](https://www.cdc.gov/nchs/products/life_tables.htm) (2021)
- Meta-analysis estimates: Published literature (see `docs/references.bib`)

## License

MIT
