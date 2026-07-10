"""Versioned methodology provenance for generated What Nut results."""

from __future__ import annotations

WHATNUT_MODEL_VERSION = "0.3.0"
OPTIQAL_REFERENCE_COMMIT = "4d22afd53715216cb2ab2cac5bfa23f969fc2c25"


def methodology_provenance() -> dict[str, object]:
    """Return the reproducible boundary of What Nut's Optiqal alignment."""
    return {
        "whatnut_model_version": WHATNUT_MODEL_VERSION,
        "optiqal_reference_commit": OPTIQAL_REFERENCE_COMMIT,
        "optiqal_reference_scope": (
            "The commit pins the committed HR-centering, evidence-tier shrinkage, "
            "and 3%/3% reference-case methods. Active decision-first Optiqal design "
            "work observed separately is not represented by this commit pin."
        ),
        "adopted": [
            "HR-centered uncertainty propagation",
            "evidence-tier publication-bias shrinkage",
            "US Second Panel-style 3%/3% primary reference case",
        ],
        "whatnut_extensions": [
            "explicit no-modeled-nut comparator metadata",
            "expected-net-monetary-benefit decision ranking",
            "draw-wise probability of optimality across mutually exclusive options",
        ],
        "deliberate_differences": [
            "What Nut estimates genuine cause-specific mortality effects.",
            "QALYs include mortality effects only, not direct morbidity or harms.",
            "The default causal prior is nutrition-specific Beta(1.5, 6.0).",
            "Current diet, substitution, persistence, transport, and mixed-nut "
            "stacks are not modeled.",
        ],
        "runtime_dependency": False,
    }
