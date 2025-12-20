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
from whatnut.precomputed import (
    get_results,
    get_lifecycle_results,
    RESULTS,
    LIFECYCLE_RESULTS,
    PrecomputedResults,
    PrecomputedLifecycleResults,
    PrecomputedLifecycleResult,
)
from whatnut.lifecycle import (
    LifecycleCEA,
    LifecycleParams,
    LifecycleResult,
    NutCostData,
    NUT_COSTS,
    get_nut_cost,
    run_nut_cea,
    get_mortality_curve,
    get_quality_curve,
)
from whatnut.lifecycle_pathways import (
    PathwayLifecycleCEA,
    PathwayParams,
    PathwayResult,
    CAUSE_SPECIFIC_RR,
)

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
    "get_lifecycle_results",
    "RESULTS",
    "LIFECYCLE_RESULTS",
    "PrecomputedResults",
    "PrecomputedLifecycleResults",
    "PrecomputedLifecycleResult",
    # Lifecycle CEA
    "LifecycleCEA",
    "LifecycleParams",
    "LifecycleResult",
    "NutCostData",
    "NUT_COSTS",
    "get_nut_cost",
    "run_nut_cea",
    "get_mortality_curve",
    "get_quality_curve",
    # Pathway-specific lifecycle
    "PathwayLifecycleCEA",
    "PathwayParams",
    "PathwayResult",
    "CAUSE_SPECIFIC_RR",
]
