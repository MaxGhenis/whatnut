# What Nut architecture

## If we were starting today

What Nut would be a small, decision-first analysis pipeline built around one
paired draw axis. It would not copy Optiqal's current-routine or stack semantics
until it had the inputs needed to support them: current nut intake, displaced
food, substitution, adherence, persistence, and direct harms.

The honest decision problem remains:

> Add one 28 g daily serving of one nut, or do not add a modeled daily nut.

The target flow is:

```text
validated inputs + scenario
          ↓
paired effect draws [draw, option, pathway]
          ↓
one batched lifecycle kernel
          ↓
outcome draws [draw, option]: life years, QALYs, cost
          ↓
all-option decision evaluator, including the comparator
          ↓
versioned result artifact
          ↓
artifact-only tables, figures, and Quarto
```

The ideal module boundaries would be:

- `spec.py`: immutable population, economic scenario, decision problem, and
  option specifications.
- `inputs.py`: validated nuts, priors, life tables, quality weights, prices,
  and source references.
- `effects.py`: paired cause-specific mortality-effect draws.
- `lifecycle.py`: one batched projection kernel; scalar evaluation would be a
  thin wrapper.
- `decision.py`: NMB, probability of beating the comparator, probability of
  optimality, recommendation, nut-only ordering, and ratio-of-means ICER.
- `artifact.py`: one canonical, versioned result schema with strict atomic I/O.
- `reporting/`: pure tables and figures that only consume an artifact.
- `cli.py`: `validate`, `generate`, and `check` commands.

## What version 0.3 adopts now

This refresh implements the safe parts of that design without changing the
underlying lifecycle estimand:

- 3% health and 3% cost discounting is the primary consumer scenario, with a
  named 0% health sensitivity.
- The no-addition comparator participates in the same paired all-option NMB
  analysis as every nut.
- Willingness to pay is an explicit run and CLI input.
- `decision.py` owns the all-option recommendation and tie-safe probability of
  optimality.
- `artifact.py` defines schema `1.0.0`, rejects NaN and Infinity, and writes
  atomically.
- Sensitivity results are materialized during generation; document rendering
  does not rerun the scientific model.
- Only ratio-of-means expected ICERs are emitted. Conditional draw-wise ratio
  diagnostics and ambiguous reference-case aliases were removed.
- Generated metadata distinguishes the consumer scenario from a formal health
  care sector reference case and pins the committed Optiqal methods it adopts.

The repository remains in a transitional shape: `pipeline.py` and `results.py`
still have separate internal and presentation result classes. They agree through
the versioned artifact, but a greenfield implementation would use one canonical
schema end to end. Two input-description figures still read the versioned
cause-fraction and nutrient YAML directly; moving those plotting inputs into the
artifact belongs with that schema consolidation.

## Deliberate non-parity with Optiqal

What Nut keeps genuine cause-specific mortality effects and weights them once by
age-specific cause fractions. It does not port a flat all-cause hazard-ratio
shortcut. It also does not claim current-routine personalization, substitution,
mixed-nut stacks, morbidity, or direct harms. Optiqal is a methodology reference,
not a runtime dependency or an oracle for food-specific assumptions.

## Follow-up sequence

1. Consolidate the duplicate pipeline and presentation result classes around one
   canonical schema and frozen `AnalysisSpec`.
2. Add input hashes and a structured evidence registry covering YAML priors,
   bibliography entries, and raw-data builders.
3. Move price channel, displaced-food cost, adherence, and willingness-to-pay
   frontiers into explicit scenarios.
4. Only then add current-intake, substitution, persistence, and mixed-nut option
   construction.
5. Evaluate a cause-specific competing-risk hazard kernel as a separately
   validated, results-changing release. Do not fold that numerical change into a
   schema or reporting refactor.
