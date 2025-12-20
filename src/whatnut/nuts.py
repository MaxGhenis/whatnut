"""Nut data with nutrients, evidence, and adjustment factors.

All nutrient data sourced from USDA FoodData Central.
All health claims linked to primary sources.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Nutrients:
    """Nutrient composition per 100g. Source: USDA FoodData Central."""

    serving_size_g: int = 100
    calories_kcal: float = 0
    protein_g: float = 0
    fat_g: float = 0
    carbs_g: float = 0
    fiber_g: float = 0
    omega3_g: float = 0  # ALA (alpha-linolenic acid)
    omega6_g: float = 0  # LA (linoleic acid)
    omega7_g: float = 0  # Palmitoleic acid
    mufa_g: float = 0  # Monounsaturated fatty acids
    vitamin_e_mg: float = 0
    magnesium_mg: float = 0
    sources: list[str] = field(default_factory=lambda: ["usda_fdc"])


@dataclass
class AdjustmentFactor:
    """Nut-specific adjustment to base mortality effect.

    mean > 1.0 means better than average nut
    mean < 1.0 means worse than average nut
    Higher SD means more uncertainty (less evidence)
    """

    mean: float
    sd: float
    rationale: str
    sources: list[str] = field(default_factory=list)


@dataclass
class Nut:
    """A nut type with all associated data."""

    id: str
    name: str
    nutrients: Nutrients
    adjustment_factor: AdjustmentFactor
    evidence_sources: list[str] = field(default_factory=list)
    evidence_strength: str = "limited"  # "strong", "moderate", "limited"
    notes: str = ""


# Nut data - all nutrients from USDA FoodData Central
# https://fdc.nal.usda.gov/
NUTS: list[Nut] = [
    Nut(
        id="walnut",
        name="Walnut",
        nutrients=Nutrients(
            calories_kcal=654,
            protein_g=15.2,
            fat_g=65.2,
            carbs_g=13.7,
            fiber_g=6.7,
            omega3_g=9.08,  # Highest ALA of any nut
            omega6_g=38.1,
            omega7_g=0.0,
            mufa_g=8.9,
            vitamin_e_mg=0.7,
            magnesium_mg=158,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=1.15,
            sd=0.08,
            rationale="Strongest CVD outcome data (PREDIMED, WAHA), unique omega-3 content",
            sources=["guasch2017", "predimed_walnuts", "waha2021"],
        ),
        evidence_sources=["guasch2017", "predimed_walnuts", "waha2021", "delgobbo2015"],
        evidence_strength="strong",
        notes="Only nut with significant omega-3 (ALA). Most nut-specific RCT data.",
    ),
    Nut(
        id="almond",
        name="Almond",
        nutrients=Nutrients(
            calories_kcal=579,
            protein_g=21.2,  # Highest protein
            fat_g=49.9,
            carbs_g=21.6,
            fiber_g=12.5,  # Highest fiber
            omega3_g=0.003,  # Negligible
            omega6_g=12.3,
            omega7_g=0.3,
            mufa_g=31.6,
            vitamin_e_mg=25.6,  # Highest vitamin E
            magnesium_mg=270,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=1.00,
            sd=0.06,
            rationale="Reference category. Robust RCT base, highest vitamin E and fiber.",
            sources=["delgobbo2015"],
        ),
        evidence_sources=["delgobbo2015", "aune2016"],
        evidence_strength="moderate",
        notes="Used as reference nut in many studies. Most studied after walnuts.",
    ),
    Nut(
        id="pistachio",
        name="Pistachio",
        nutrients=Nutrients(
            calories_kcal=560,
            protein_g=20.2,
            fat_g=45.3,
            carbs_g=27.2,
            fiber_g=10.6,
            omega3_g=0.25,
            omega6_g=13.2,
            omega7_g=0.5,
            mufa_g=23.3,
            vitamin_e_mg=2.9,
            magnesium_mg=121,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=1.08,
            sd=0.10,
            rationale="Best lipid improvements in network meta-analysis",
            sources=["delgobbo2015"],
        ),
        evidence_sources=["delgobbo2015"],
        evidence_strength="moderate",
        notes="Ranked #1 for LDL and triglyceride reduction in Del Gobbo 2015.",
    ),
    Nut(
        id="macadamia",
        name="Macadamia",
        nutrients=Nutrients(
            calories_kcal=718,
            protein_g=7.9,  # Lowest protein
            fat_g=75.8,  # Highest fat
            carbs_g=13.8,
            fiber_g=8.6,
            omega3_g=0.21,
            omega6_g=1.3,  # Lowest omega-6
            omega7_g=12.0,  # Unique: highest omega-7
            mufa_g=58.9,  # Highest MUFA (80% of fat)
            vitamin_e_mg=0.5,
            magnesium_mg=130,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=1.02,
            sd=0.15,  # High uncertainty due to limited evidence
            rationale="Limited direct evidence. FDA qualified health claim. Unique omega-7 adds optionality.",
            sources=["fda_macadamia"],
        ),
        evidence_sources=["fda_macadamia", "usda_fdc"],
        evidence_strength="limited",
        notes="Best omega-6:3 ratio (~6:1). Highest MUFA. Omega-7 may have unique benefits but evidence sparse.",
    ),
    Nut(
        id="peanut",
        name="Peanut",
        nutrients=Nutrients(
            calories_kcal=567,
            protein_g=25.8,  # Very high protein (legume)
            fat_g=49.2,
            carbs_g=16.1,
            fiber_g=8.5,
            omega3_g=0.003,
            omega6_g=15.6,
            omega7_g=0.0,
            mufa_g=24.4,
            vitamin_e_mg=8.3,
            magnesium_mg=168,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=0.95,
            sd=0.07,
            rationale="Large cohort data, but technically a legume. Slight discount for aflatoxin risk.",
            sources=["aune2016", "bao2013"],
        ),
        evidence_sources=["aune2016", "bao2013"],
        evidence_strength="strong",
        notes="Technically a legume. Included in most nut meta-analyses. Excellent cost-effectiveness.",
    ),
    Nut(
        id="pecan",
        name="Pecan",
        nutrients=Nutrients(
            calories_kcal=691,
            protein_g=9.2,
            fat_g=72.0,
            carbs_g=13.9,
            fiber_g=9.6,
            omega3_g=0.99,
            omega6_g=20.6,
            omega7_g=0.0,
            mufa_g=40.8,
            vitamin_e_mg=1.4,
            magnesium_mg=121,
        ),
        adjustment_factor=AdjustmentFactor(
            mean=0.98,
            sd=0.18,  # Very high uncertainty
            rationale="Minimal nut-specific evidence. Estimate relies on category prior.",
            sources=[],
        ),
        evidence_sources=["usda_fdc"],
        evidence_strength="limited",
        notes="Very limited nut-specific research. Prior-dominated estimate.",
    ),
    Nut(
        id="cashew",
        name="Cashew",
        nutrients=Nutrients(
            calories_kcal=553,
            protein_g=18.2,
            fat_g=43.9,
            carbs_g=30.2,  # Highest carbs
            fiber_g=3.3,  # Lowest fiber
            omega3_g=0.06,
            omega6_g=7.8,
            omega7_g=0.0,
            mufa_g=23.8,
            vitamin_e_mg=0.9,
            magnesium_mg=292,  # Highest magnesium
        ),
        adjustment_factor=AdjustmentFactor(
            mean=0.92,
            sd=0.14,
            rationale="Lowest fiber, highest carbs. Very limited RCT data.",
            sources=[],
        ),
        evidence_sources=["usda_fdc"],
        evidence_strength="limited",
        notes="Lower fiber and higher carbs than other nuts. Limited nut-specific evidence.",
    ),
]


def get_nut(nut_id: str) -> Optional[Nut]:
    """Get a nut by ID."""
    for nut in NUTS:
        if nut.id == nut_id:
            return nut
    return None
