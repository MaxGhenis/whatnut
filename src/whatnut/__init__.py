"""Whatnut: Monte Carlo analysis of life expectancy from nut consumption."""

from whatnut.config import (
    NUT_IDS,
    NUTRIENTS,
    PATHWAYS,
    get_all_nuts,
    get_cause_fractions,
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
from whatnut.evidence import SOURCES, EffectSize, Source, get_source, validate_sources
from whatnut.lifecycle import LifecycleResult, run_lifecycle
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
    "SOURCES",
    "Source",
    "EffectSize",
    "get_source",
    "validate_sources",
    # Model
    "ModelSamples",
    "sample_model",
    "summarize_rr",
    # Lifecycle
    "LifecycleResult",
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
    # Pipeline
    "AnalysisResults",
    "NutAnalysis",
    "run_analysis",
]
