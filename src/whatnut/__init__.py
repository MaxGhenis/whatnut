"""Whatnut: Monte Carlo analysis of life expectancy from nut consumption."""

from whatnut.config import (
    NUTRIENTS,
    NUT_IDS,
    PATHWAYS,
    get_nut,
    get_all_nuts,
    get_nutrient_matrix,
    get_mortality_curve,
    get_quality_curve,
    get_cause_fractions,
    validate,
)
from whatnut.evidence import SOURCES, Source, EffectSize, get_source, validate_sources
from whatnut.lifecycle import LifecycleResult, run_lifecycle
from whatnut.model import ModelSamples, sample_model, summarize_rr
from whatnut.pipeline import AnalysisResults, NutAnalysis, run_analysis

__version__ = "0.2.0"

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
    # Pipeline
    "AnalysisResults",
    "NutAnalysis",
    "run_analysis",
]
