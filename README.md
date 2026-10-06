# What Nut?

What Nut is a reproducible mortality-potential and consumer-value benchmark for
one deliberately narrow question:

> What would the modeled mortality benefit and gross retail cost be if a
> 40-year-old US resident added one 28 g serving of one nut every day for life?

It is not a net causal estimate of adding nuts to an unchanged diet. The
canonical action is conditional on no displaced food, no calorie or adiposity
effect, full lifelong adherence, and no direct morbidity benefits or harms.

## What the model does

- Defines the population, action, economic scenario, comparator, and options in
  one immutable `AnalysisSpec`.
- Uses four outcome-matched nutrient coefficients: ALA, fiber, and magnesium
  for cardiovascular mortality, plus fiber for cancer mortality. Every other
  nutrient-pathway coefficient is a structural zero in the canonical
  gross-addition benchmark.
- Samples a skeptical Beta(1.5, 6.0) causal-fraction prior and propagates
  uncertainty with deterministic named random-number streams.
- Converts exact CDC 2021 single-age death probabilities for ages 0–99 to
  hazards, applies age-specific competing-risk hazard ratios, and closes the
  model with an explicit terminal interval at age 100.
- Records the translation from published cause-specific mortality relative
  risks to constant proportional hazard ratios with zero modeled latency as an
  explicit assumption in `AnalysisSpec`.
- Uses half-cycle occupancy and midpoint discounting for life years, QALYs, and
  costs.
- Evaluates every nut and the no-modeled-nut comparator together using expected
  net monetary benefit and draw-wise probability of optimality.
- Writes a strictly validated schema-2 result artifact with SHA-256 hashes for
  scientific code and model inputs.

The model has no runtime dependency on Optiqal. The artifact records the exact
Optiqal commit used as a methodological reference and the ways What Nut differs.

## Current result

Cost aside, walnuts produce the largest expected modeled health gain. At the
illustrative $50,000/QALY consumer valuation and specialty-retail prices, the
no-modeled-daily-nut comparator has the highest expected net monetary benefit;
peanuts are the best nut alternative.

The canonical results for a 40-year-old span about 0.04–0.11 life years
(0.5–1.3 months). These are partial mortality-potential estimates, conditional
on the exclusions above, not diet recommendations.

## Installation

```bash
git clone https://github.com/MaxGhenis/whatnut.git
cd whatnut
uv sync --all-extras
```

Python 3.10 or newer is supported. The locked development workflow uses `uv`.

## Usage

Read the committed paper results without rerunning the model:

```python
from whatnut.results import r

print(r.walnut.life_years_fmt)
print(r.walnut.qaly_model_interval)
print(r.best_nut_alternative.name)
print(r.decision_summary["recommended_option"])
```

Run an analysis from Python:

```python
from whatnut.pipeline import run_analysis

results = run_analysis(n_samples=10_000, seed=42)
for nut_id, nut in results.nuts.items():
    print(nut_id, nut.life_years_mean, nut.qaly_mean)
```

Use the command-line interface for reproducible artifacts:

```bash
# Validate inputs and print the canonical summary.
uv run whatnut summary

# Regenerate the canonical schema-2 artifact.
uv run whatnut generate

# Validate its schema and internal algebra.
uv run whatnut validate

# Recompute in memory and require an exact match with the committed artifact.
uv run whatnut check
```

A noncanonical scenario cannot overwrite the canonical artifact:

```bash
uv run whatnut generate --willingness-to-pay 100000 \
  --output tmp/results-wtp-100000.json
```

## Interpretation

Life years are undiscounted survival gains. Reference-case QALYs apply exact
age-band means from a published US EQ-5D-5L norms table and 3% health
discounting; the artifact also
contains a 0% health-discount sensitivity. Expected ICERs are ratios of mean
survival-weighted lifetime gross retail cost to mean mortality-derived QALYs.
Expected NMB, not the ICER ranking, determines the recommendation.

`P(positive)` and `P(negative)` describe the sign of the modeled mortality
effect. They are not probabilities of overall benefit or harm because the model
does not represent direct morbidity, adverse effects, calorie surplus, or the
food that a nut would replace.

## Reproducibility

```bash
uv sync --frozen --all-extras
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen whatnut check
```

The canonical artifact is
`src/whatnut/data/results.json`. Schema 2 embeds the complete `AnalysisSpec`,
the scenario-scoped evidence registry, result-interval definition, decision
context, methodology provenance, named RNG algorithm, per-file SHA-256 hashes,
and a scientific-content fingerprint over the hashed code, inputs, and declared
method identifiers. Writes are finite-only, validated, atomic, and protected
against noncanonical replacement.

Build the paper with Quarto:

```bash
export QUARTO_PYTHON="$PWD/.venv/bin/python"
export JUPYTER_PREFER_ENV_PATH=1
quarto render docs/
```

The manuscript consumes the committed artifact; rendering does not rerun the
scientific model. See [ARCHITECTURE.md](ARCHITECTURE.md) for the implemented
design and remaining extensions.

## Data sources

- Nutrient composition: [USDA FoodData Central](https://fdc.nal.usda.gov/)
- Mortality: [CDC United States Life Tables, 2021](https://www.cdc.gov/nchs/products/life_tables.htm)
- Cause fractions: CDC/NVSS 2021 deaths tables
- Retail prices: archived April 2026 single-retailer snapshot
- Outcome coefficients: primary meta-analyses listed in
  `docs/references.bib` and described in the manuscript

## License

MIT
