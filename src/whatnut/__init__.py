"""What Nut: a transparent mortality-potential decision model for daily nuts."""

from whatnut.config import (
    NUT_IDS,
    NUTRIENTS,
    PATHWAYS,
    get_all_nuts,
    get_cause_fractions,
    get_evidence_registry,
    get_mortality_curve,
    get_nut,
    get_nutrient_matrix,
    get_quality_curve,
    validate,
)
from whatnut.decision import (
    DEFAULT_WILLINGNESS_TO_PAY,
    SINGLE_NUT_ADDITION_DECISION,
    DecisionContext,
    MutuallyExclusiveDecision,
    summarize_cost_effectiveness,
    summarize_mutually_exclusive_nmb,
)
from whatnut.lifecycle import (
    BaselineOutcomes,
    LifecycleResult,
    calculate_baseline_outcomes,
    run_lifecycle,
)
from whatnut.model import ModelSamples, sample_model, summarize_rr
from whatnut.provenance import WHATNUT_MODEL_VERSION
from whatnut.reference_case import (
    DEFAULT_COST_DISCOUNT_RATE,
    DEFAULT_QALY_DISCOUNT_RATE,
    DEFAULT_REFERENCE_CASE,
    UNDISCOUNTED_COST_DISCOUNT_RATE,
    UNDISCOUNTED_QALY_DISCOUNT_RATE,
    WHATNUT_CONSUMER_REFERENCE_CASE,
    ReferenceCase,
)
from whatnut.spec import (
    ActionSpec,
    AnalysisSpec,
    CausalFractionSpec,
    DecisionProblemSpec,
    EconomicScenario,
    EffectModelSpec,
    PopulationSpec,
    canonical_analysis_spec,
)

__version__ = WHATNUT_MODEL_VERSION


def __getattr__(name: str):
    """Lazy pipeline exports avoid importing whatnut.pipeline during -m execution."""
    if name in {"AnalysisResults", "NutAnalysis", "run_analysis"}:
        from whatnut.pipeline import AnalysisResults, NutAnalysis, run_analysis

        return {
            "AnalysisResults": AnalysisResults,
            "NutAnalysis": NutAnalysis,
            "run_analysis": run_analysis,
        }[name]
    raise AttributeError(f"module 'whatnut' has no attribute {name!r}")


__all__ = [
    # Config
    "NUTRIENTS",
    "NUT_IDS",
    "PATHWAYS",
    "get_nut",
    "get_all_nuts",
    "get_nutrient_matrix",
    "get_mortality_curve",
    "get_quality_curve",
    "get_cause_fractions",
    "validate",
    # Evidence
    "get_evidence_registry",
    # Model
    "ModelSamples",
    "sample_model",
    "summarize_rr",
    # Lifecycle
    "LifecycleResult",
    "BaselineOutcomes",
    "calculate_baseline_outcomes",
    "run_lifecycle",
    # Decision analysis
    "DecisionContext",
    "MutuallyExclusiveDecision",
    "DEFAULT_WILLINGNESS_TO_PAY",
    "SINGLE_NUT_ADDITION_DECISION",
    "summarize_cost_effectiveness",
    "summarize_mutually_exclusive_nmb",
    # Reference case
    "ReferenceCase",
    "DEFAULT_REFERENCE_CASE",
    "WHATNUT_CONSUMER_REFERENCE_CASE",
    "DEFAULT_QALY_DISCOUNT_RATE",
    "DEFAULT_COST_DISCOUNT_RATE",
    "UNDISCOUNTED_QALY_DISCOUNT_RATE",
    "UNDISCOUNTED_COST_DISCOUNT_RATE",
    # Specification
    "ActionSpec",
    "AnalysisSpec",
    "CausalFractionSpec",
    "DecisionProblemSpec",
    "EconomicScenario",
    "EffectModelSpec",
    "PopulationSpec",
    "canonical_analysis_spec",
    # Pipeline
    "AnalysisResults",
    "NutAnalysis",
    "run_analysis",
]
