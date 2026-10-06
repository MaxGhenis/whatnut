"""Configuration module: loads YAML data, defines typed dataclasses, validates.

This is the single entry point for all data used by the model.
All YAML files live in src/whatnut/data/.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import yaml

DATA_DIR = Path(__file__).parent / "data"

# Nutrient keys used by the model (must match priors.yaml and nuts.yaml)
NUTRIENTS = [
    "ala_omega3",
    "omega6",
    "omega7",
    "fiber",
    "saturated_fat",
    "magnesium",
    "arginine",
    "vitamin_e",
    "phytosterols",
    "protein",
]

PATHWAYS = ["cvd", "cancer", "other"]

NUT_IDS = [
    "walnut",
    "almond",
    "pistachio",
    "pecan",
    "macadamia",
    "peanut",
    "hazelnut",
    "cashew",
]


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NutrientPrior:
    """Normal prior for a single nutrient-pathway effect (log-RR per unit)."""

    mean: float
    sd: float
    unit: str
    source: str
    outcome: str
    contrast: str
    source_url: str | None
    applicable_actions: tuple[str, ...]


@dataclass(frozen=True)
class ConfoundingPrior:
    """Beta prior for the causal fraction."""

    alpha: float
    beta: float
    mean: float
    ci_lower: float
    ci_upper: float
    rationale: str


@dataclass(frozen=True)
class NutProfile:
    """Complete nut profile: nutrient composition and retail cost."""

    id: str
    fdc_id: int
    nutrients: dict[str, float]  # model nutrient key -> value per 28g
    cost_per_kg_usd: float

    @property
    def annual_cost(self) -> float:
        """Annual cost for 28g/day consumption. 28g/day * 365 = 10.22 kg/year."""
        return self.cost_per_kg_usd * 10.22


# ---------------------------------------------------------------------------
# YAML loaders (cached at module level)
# ---------------------------------------------------------------------------

_cache: dict = {}


def _load_yaml(filename: str) -> dict:
    """Load a YAML file from the data directory, with caching."""
    if filename not in _cache:
        with open(DATA_DIR / filename) as f:
            _cache[filename] = yaml.safe_load(f)
    return _cache[filename]


def load_priors() -> dict:
    """Load priors.yaml."""
    return _load_yaml("priors.yaml")


def load_nuts_yaml() -> dict:
    """Load nuts.yaml."""
    return _load_yaml("nuts.yaml")


def load_mortality() -> dict:
    """Load mortality.yaml."""
    return _load_yaml("mortality.yaml")


def load_quality_weights() -> dict:
    """Load quality_weights.yaml."""
    return _load_yaml("quality_weights.yaml")


def load_cause_fractions() -> dict:
    """Load cause_fractions.yaml."""
    return _load_yaml("cause_fractions.yaml")


def load_constants() -> dict:
    """Load narrative constants (target age, NICE thresholds, FX rates)."""
    return _load_yaml("constants.yaml")


# ---------------------------------------------------------------------------
# Typed accessors
# ---------------------------------------------------------------------------


def get_nutrient_prior(pathway: str, nutrient: str) -> NutrientPrior:
    """Get the prior for a specific pathway-nutrient combination."""
    data = load_priors()
    entry = data[pathway][nutrient]
    return NutrientPrior(
        mean=entry["mean"],
        sd=entry["sd"],
        unit=entry["unit"],
        source=entry["source"],
        outcome=entry.get("outcome", f"{pathway} mortality"),
        contrast=entry.get("contrast", "additional intake per stated unit"),
        source_url=entry.get("source_url"),
        applicable_actions=tuple(entry.get("applicable_actions", ["gross_addition"])),
    )


def get_pathway_priors(pathway: str) -> dict[str, NutrientPrior]:
    """Get all nutrient priors for a pathway."""
    return {n: get_nutrient_prior(pathway, n) for n in NUTRIENTS}


def get_evidence_registry(action_kind: str = "gross_addition") -> dict[str, object]:
    """Return the machine-readable evidence status of every model coefficient."""
    active: list[dict[str, object]] = []
    excluded: list[dict[str, object]] = []
    for pathway in PATHWAYS:
        for nutrient in NUTRIENTS:
            prior = get_nutrient_prior(pathway, nutrient)
            record = {
                "pathway": pathway,
                "nutrient": nutrient,
                "mean": prior.mean,
                "sd": prior.sd,
                "unit": prior.unit,
                "outcome": prior.outcome,
                "contrast": prior.contrast,
                "source": prior.source,
                "source_url": prior.source_url,
            }
            if action_kind in prior.applicable_actions:
                active.append(record)
            else:
                excluded.append(record)

    substitution = load_priors().get("substitution_contrasts", {})
    return {
        "action_kind": action_kind,
        "active_coefficients": active,
        "structurally_excluded_coefficients": excluded,
        "deferred_substitution_contrasts": substitution,
    }


def get_confounding_prior() -> ConfoundingPrior:
    """Get the confounding prior."""
    data = load_priors()
    c = data["confounding"]
    return ConfoundingPrior(
        alpha=c["alpha"],
        beta=c["beta"],
        mean=c["mean"],
        ci_lower=c["ci_lower"],
        ci_upper=c["ci_upper"],
        rationale=c["rationale"],
    )


def _extract_model_nutrients(raw_nutrients: dict) -> dict[str, float]:
    """Extract the 10 model nutrients from raw YAML nutrient dict.

    Maps YAML keys to model keys:
      omega3_ala_g -> ala_omega3
      polyunsaturated_fat_g - omega3_ala_g -> omega6
      omega7_g -> omega7
      fiber_g -> fiber
      saturated_fat_g -> saturated_fat
      magnesium_mg -> magnesium
      arginine_g -> arginine
      vitamin_e_mg -> vitamin_e
      phytosterols_mg -> phytosterols
      protein_g -> protein
    """
    return {
        "ala_omega3": raw_nutrients.get("omega3_ala_g", 0),
        "omega6": raw_nutrients.get("polyunsaturated_fat_g", 0)
        - raw_nutrients.get("omega3_ala_g", 0),
        "omega7": raw_nutrients.get("omega7_g", 0),
        "fiber": raw_nutrients.get("fiber_g", 0),
        "saturated_fat": raw_nutrients.get("saturated_fat_g", 0),
        "magnesium": raw_nutrients.get("magnesium_mg", 0),
        "arginine": raw_nutrients.get("arginine_g", 0),
        "vitamin_e": raw_nutrients.get("vitamin_e_mg", 0),
        "phytosterols": raw_nutrients.get("phytosterols_mg", 0),
        "protein": raw_nutrients.get("protein_g", 0),
    }


def get_nut(nut_id: str) -> NutProfile:
    """Get a complete nut profile by ID."""
    data = load_nuts_yaml()
    if nut_id not in data:
        raise ValueError(f"Unknown nut: {nut_id}. Available: {list(data.keys())}")
    raw = data[nut_id]
    model_nutrients = _extract_model_nutrients(raw["nutrients"])
    return NutProfile(
        id=nut_id,
        fdc_id=raw["fdc_id"],
        nutrients=model_nutrients,
        cost_per_kg_usd=raw["cost_per_kg_usd"],
    )


def get_all_nuts() -> list[NutProfile]:
    """Get all nut profiles."""
    return [get_nut(nid) for nid in NUT_IDS]


def get_nutrient_matrix(nut_ids: list[str] | None = None) -> np.ndarray:
    """Build (n_nuts x n_nutrients) matrix for vectorized computation."""
    if nut_ids is None:
        nut_ids = NUT_IDS
    X = np.zeros((len(nut_ids), len(NUTRIENTS)))
    for i, nid in enumerate(nut_ids):
        nut = get_nut(nid)
        for j, nutrient in enumerate(NUTRIENTS):
            X[i, j] = nut.nutrients.get(nutrient, 0)
    return X


# ---------------------------------------------------------------------------
# Mortality / quality / cause fractions interpolation
# ---------------------------------------------------------------------------


def _interpolate_table(
    table: dict[int, float], age: int, *, log_space: bool = False, floor: float = 0.0
) -> float:
    """Interpolate a value from an age-keyed table."""
    ages = sorted(table.keys())
    if age <= ages[0]:
        return table[ages[0]]
    if age >= ages[-1]:
        val = table[ages[-1]]
        if log_space:
            return min(1.0, val * 1.1 ** (age - ages[-1]))
        return max(floor, val - 0.02 * (age - ages[-1]))
    lower_age = max(a for a in ages if a <= age)
    upper_age = min(a for a in ages if a > age)
    lower_val = table[lower_age]
    upper_val = table[upper_age]
    frac = (age - lower_age) / (upper_age - lower_age)
    if log_space and lower_val > 0 and upper_val > 0:
        log_lower = np.log(lower_val)
        log_upper = np.log(upper_val)
        return float(np.exp(log_lower + frac * (log_upper - log_lower)))
    return lower_val + frac * (upper_val - lower_val)


def get_mortality_rate(age: int) -> float:
    """Get an exact published single-age mortality probability."""
    if isinstance(age, bool) or not isinstance(age, (int, np.integer)):
        raise ValueError("age must be an integer between 0 and 100.")
    age = int(age)
    table = load_mortality()["rates"]
    if age not in table:
        raise ValueError("age must be an integer between 0 and 100.")
    return float(table[age])


def get_terminal_expected_years() -> float:
    """Return CDC remaining life expectancy in the age-100+ open interval."""
    value = load_mortality().get("terminal_expected_years")
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not np.isfinite(value)
        or value <= 0
    ):
        raise ValueError("terminal_expected_years must be a positive finite value.")
    return float(value)


def get_mortality_curve(start_age: int, max_age: int = 100) -> np.ndarray:
    """Get mortality rates from start_age to max_age."""
    if max_age < start_age:
        raise ValueError("max_age must be greater than or equal to start_age.")
    return np.array([get_mortality_rate(a) for a in range(start_age, max_age + 1)])


def get_quality_weight(age: int) -> float:
    """Get the published US EQ-5D-5L mean for an age band."""
    if isinstance(age, bool) or not isinstance(age, (int, np.integer)):
        raise ValueError("age must be an integer.")
    age = int(age)
    table = load_quality_weights()["weights"]
    boundaries = sorted(table)
    boundary = max((value for value in boundaries if value <= age), default=None)
    if boundary is None:
        return float(table[boundaries[0]])
    return float(table[boundary])


def get_quality_curve(start_age: int, max_age: int = 100) -> np.ndarray:
    """Get quality weights from start_age to max_age."""
    return np.array([get_quality_weight(a) for a in range(start_age, max_age + 1)])


def get_cause_fractions(age: int) -> tuple[float, float, float]:
    """Get (cvd, cancer, other) cause fractions for a given age.

    Values are interpolated linearly from the NVSR-sourced anchor grid
    in cause_fractions.yaml and then renormalized so the triple sums to
    exactly 1.0 (anchors are rounded to three decimals, so raw sums can
    drift by ~0.001 between anchors).
    """

    def _normalize(
        cvd: float, cancer: float, other: float
    ) -> tuple[float, float, float]:
        total = cvd + cancer + other
        if total <= 0:
            return cvd, cancer, other
        return cvd / total, cancer / total, other / total

    raw = load_cause_fractions()["fractions"]
    ages = sorted(raw.keys())
    if age <= ages[0]:
        d = raw[ages[0]]
        return _normalize(d["cvd"], d["cancer"], d["other"])
    if age >= ages[-1]:
        d = raw[ages[-1]]
        return _normalize(d["cvd"], d["cancer"], d["other"])
    lower_age = max(a for a in ages if a <= age)
    upper_age = min(a for a in ages if a > age)
    frac = (age - lower_age) / (upper_age - lower_age)
    lower = raw[lower_age]
    upper = raw[upper_age]
    return _normalize(
        lower["cvd"] + frac * (upper["cvd"] - lower["cvd"]),
        lower["cancer"] + frac * (upper["cancer"] - lower["cancer"]),
        lower["other"] + frac * (upper["other"] - lower["other"]),
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate() -> list[str]:
    """Validate all data files. Returns list of errors (empty = OK)."""
    errors = []

    # Check cause fractions sum to 1
    raw = load_cause_fractions()["fractions"]
    for age, fracs in raw.items():
        total = fracs["cvd"] + fracs["cancer"] + fracs["other"]
        if abs(total - 1.0) > 0.01:
            errors.append(f"Cause fractions at age {age} sum to {total}, not 1.0")

    # Check nutrient values are non-negative
    for nid in NUT_IDS:
        nut = get_nut(nid)
        for key, val in nut.nutrients.items():
            if key != "omega6" and val < 0:
                errors.append(f"{nid}.{key} = {val} (negative)")

    # Check mortality rates are in (0, 1]. CDC life tables set qx=1.0 at
    # the terminal age (everyone has died by the end of that year), so
    # the upper bound is closed.
    rates = load_mortality()["rates"]
    for age, rate in rates.items():
        if not (0 < rate <= 1):
            errors.append(f"Mortality rate at age {age} = {rate} (out of range)")
    try:
        get_terminal_expected_years()
    except ValueError as error:
        errors.append(str(error))

    # Check quality weights are in (0, 1]
    weights = load_quality_weights()["weights"]
    for age, w in weights.items():
        if not (0 < w <= 1):
            errors.append(f"Quality weight at age {age} = {w} (out of range)")

    # Check priors have required nutrients for each pathway
    priors = load_priors()
    for pathway in PATHWAYS:
        for nutrient in NUTRIENTS:
            if nutrient not in priors.get(pathway, {}):
                errors.append(f"Missing prior: {pathway}/{nutrient}")
                continue
            entry = priors[pathway][nutrient]
            mean = entry.get("mean")
            sd = entry.get("sd")
            if (
                isinstance(mean, bool)
                or not isinstance(mean, (int, float))
                or not np.isfinite(mean)
            ):
                errors.append(f"Invalid prior mean: {pathway}/{nutrient}")
            if (
                isinstance(sd, bool)
                or not isinstance(sd, (int, float))
                or not np.isfinite(sd)
                or sd < 0
            ):
                errors.append(f"Invalid prior SD: {pathway}/{nutrient}")
            applicable_actions = entry.get("applicable_actions", ["gross_addition"])
            if not isinstance(applicable_actions, list) or any(
                action != "gross_addition" for action in applicable_actions
            ):
                errors.append(f"Invalid applicable actions: {pathway}/{nutrient}")
            if not applicable_actions and (mean != 0 or sd != 0):
                errors.append(
                    f"Inactive prior must be structurally zero: {pathway}/{nutrient}"
                )
            if applicable_actions:
                for field in ("outcome", "contrast", "source_url"):
                    if not isinstance(entry.get(field), str) or not entry[field]:
                        errors.append(
                            f"Active prior missing {field}: {pathway}/{nutrient}"
                        )

    return errors
