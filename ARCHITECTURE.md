# What Nut architecture

## Design premise

What Nut starts with the estimand, not the evidence model. Its canonical
question is a conditional benchmark:

> For a 40-year-old US resident, compare adding one 28 g serving of exactly one
> nut every day for life with no modeled daily-nut intervention.

The action is a **gross addition**. The model has no current-diet observation,
displaced food, energy-balance or adiposity response, adherence decay, direct
morbidity effects, direct harms, or mixed-nut interaction. Those are absent
inputs and outcomes, not zero-valued real-world effects. Accordingly, the
output is a partial mortality-potential benchmark rather than a net causal
effect of changing diet.

## Implemented flow

```text
immutable AnalysisSpec
        +
validated nutrients, priors, mortality, cause fractions, quality, prices
        ↓
paired nutrient-coefficient and causal-fraction draws
        ↓
cause-specific hazard ratios [draw, nut, pathway]
        ↓
single batched competing-risk lifecycle kernel
        ↓
life-year, QALY, and gross-cost draws [draw, nut]
        ↓
all-option NMB evaluator + no-nut comparator
        ↓
strict schema-2 artifact with code/input hashes
        ↓
artifact-only result objects, tables, figures, and Quarto manuscript
```

The paired draw axis is preserved across nuts, pathways, discounting
sensitivities, and decision options. This makes draw-wise comparisons meaningful
and prevents sensitivities from introducing unrelated Monte Carlo noise.

## Module boundaries

- `spec.py` defines frozen population, economic, causal-fraction, action, and
  decision specifications. Unsupported actions fail validation instead of being
  silently approximated.
- `config.py` is the typed boundary around versioned YAML inputs and records
  evidence outcome, contrast, source URL, and applicable action for every
  nutrient coefficient.
- `model.py` samples only coefficients declared for the scenario. That
  declaration is a modeling judgment, not proof that a higher-intake cohort
  contrast identifies gross addition. The model has no uncalibrated per-nut
  random effect, residual variance, or hand-authored whole-nut multiplier.
- `lifecycle.py` owns baseline and intervention survival, QALYs, costs, and the
  pathway decomposition. Scalar evaluation is a wrapper around the same core
  used for batched draws.
- `decision.py` owns expected NMB, sign probabilities, ratio-of-means ICERs,
  tie handling, nut-only ordering, and probability of optimality across all
  mutually exclusive options.
- `pipeline.py` executes an `AnalysisSpec` and constructs the canonical artifact
  payload. It also materializes sensitivities from shared structural draws.
- `artifact.py` validates schema 2, numerical identities, decision consistency,
  provenance, and finite JSON values before atomic replacement.
- `results.py` is the artifact-only reporting adapter. It never reruns the
  scientific model.
- `figures.py` separates artifact-backed result figures from input-description
  figures that read the versioned cause-fraction and nutrient YAML through
  `config.py`. The manuscript never resamples the scientific model.
- `cli.py` exposes `summary`, `generate`, `validate`, and `check` as explicit
  operational commands.

## Scientific kernel

### Evidence layer

The gross-addition model retains four outcome-matched coefficients:

- CVD mortality: dietary ALA, fiber, and magnesium.
- Cancer mortality: dietary fiber.
- Other mortality: no retained coefficient.

Every other nutrient-pathway combination is a structural zero. In particular,
fat-composition evidence that identifies replacement of one energy source by
another does not enter a gross-addition action. The code keeps those exclusions
explicit in input metadata so a future substitution model can require a real
displaced-food contrast.

Outcome matching does not identify the treatment contrast. The retained source
estimates compare higher with lower dietary intake, often under energy- or
diet-adjusted cohort models. Mapping them to one nut's composition under the
gross-addition specification is an explicit mechanical transport assumption.

There is no likelihood. Forward Monte Carlo draws propagate coefficient and
causal-fraction uncertainty without calling the result a posterior. HR
centering makes the mean relative risk before causal-fraction attenuation
correspond to the meta-analytic point estimate after exponentiation. Named PCG64 streams isolate uncertainty families;
confounding sensitivities transform shared uniform ranks and leave structural
coefficient draws unchanged.

### Lifecycle layer

The CDC table supplies exact annual death probabilities (`qx`) for every age
0–99 and an explicit open terminal interval at 100. For each age, the kernel:

1. converts all-cause `qx` to an integrated hazard;
2. partitions that hazard using age-specific CVD, cancer, and other-cause
   fractions;
3. multiplies each cause-specific hazard by its modeled hazard ratio;
4. sums the adjusted hazards and converts back to a bounded annual probability;
5. advances survival through the terminal interval.

`AnalysisSpec.effect_model` makes the evidence-to-lifecycle bridge inspectable:
the source measure is a cause-specific mortality relative risk, used as a
proportional cause-specific integrated-hazard multiplier that is constant
across age and begins with zero modeled latency.

Annual person-time is the average of survival at the start and end of each
cycle. Quality, life-year, and cost accruals use this half-cycle occupancy and
are discounted at cycle midpoints. Baseline and intervention outcomes therefore
share the same horizon and numerical convention.

### Decision layer

The economic perspective is consumer out-of-pocket spending. The primary
scenario discounts health and cost at 3% and values a QALY at an illustrative
$50,000. For each paired draw,

```text
NMB = willingness_to_pay × mortality-derived QALYs − gross retail cost
```

The comparator has zero incremental QALYs, cost, and NMB. Probability of
optimality is calculated across the comparator and all eight nuts, with exact
ties split equally at the declared economic resolution. The nut-only rank is
reported separately and cannot be mistaken for the overall recommendation.

## Artifact and reproducibility contract

Schema `2.0.0` stores the full serialized `AnalysisSpec`, scenario-scoped
`evidence_registry`, decision context, reference case, model-interval semantics,
sensitivities, and every reported nut result. Validation checks decomposition
identities, QALY/cost/NMB algebra, probability complements, ranks, pathway
shares, and domain restrictions at the stored precision.

Provenance includes:

- What Nut version and repository;
- the exact Optiqal methodology-reference commit and scope;
- the named RNG algorithm;
- SHA-256 hashes for scientific source files and versioned model inputs; and
- a scientific-content fingerprint over those hashes and declared method
  identifiers. Scenario values remain explicit in the serialized `AnalysisSpec`.

`whatnut generate` writes the canonical artifact only for the canonical
specification. Noncanonical scenarios require another path. `whatnut check`
recomputes the canonical analysis in memory and requires exact artifact
equality.

## Deliberate non-parity with Optiqal

Optiqal is a methodological reference, not a runtime dependency or an oracle.
What Nut adopts HR-centered uncertainty propagation, an explicit decision
specification, and the 3%/3% primary convention. It retains a food-specific,
cause-specific competing-risk kernel and excludes Optiqal features that lack
What Nut inputs, including current-routine personalization and stacked
interventions.

## Extensions that require new evidence or inputs

The next scientifically meaningful additions are separate estimands, not flags
on the current one:

1. A substitution action with an observed baseline diet and an explicit
   displaced food, including nutrient and price differences.
2. An energy-balance and adiposity pathway for a true gross-addition action.
3. Time-varying adherence and finite persistence with evidence-based parameters.
4. Direct morbidity benefits and direct harms measured on compatible outcomes.
5. Population heterogeneity and price channels defined as named scenarios.
6. Calibration or validation against an external outcome dataset before adding
   food-specific residual effects.

Until those inputs exist, the narrow conditional benchmark is the honest model.
