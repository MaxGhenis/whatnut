"""Whatnut: Bayesian QALY analysis of nut consumption."""

from whatnut.evidence import SOURCES, Source, EffectSize, get_source, validate_sources
from whatnut.nuts import NUTS, Nut, Nutrients, AdjustmentFactor, get_nut
from whatnut.simulation import (
    MonteCarloSimulation,
    SimulationParams,
    SimulationResult,
    NutResult,
    CategoryEffect,
    DEFAULT_PARAMS,
)
from whatnut.precomputed import get_results, RESULTS, PrecomputedResults

__version__ = "0.1.0"

__all__ = [
    # Evidence
    "SOURCES",
    "Source",
    "EffectSize",
    "get_source",
    "validate_sources",
    # Nuts
    "NUTS",
    "Nut",
    "Nutrients",
    "AdjustmentFactor",
    "get_nut",
    # Simulation
    "MonteCarloSimulation",
    "SimulationParams",
    "SimulationResult",
    "NutResult",
    "CategoryEffect",
    "DEFAULT_PARAMS",
    # Precomputed
    "get_results",
    "RESULTS",
    "PrecomputedResults",
]
