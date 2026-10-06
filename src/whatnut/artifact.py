"""Versioned, strict I/O for generated What Nut result artifacts."""

from __future__ import annotations

import json
import hashlib
import math
import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

RESULTS_SCHEMA_VERSION = "2.0.0"

_TOP_LEVEL_FIELDS = frozenset(
    {
        "schema_version",
        "analysis_spec",
        "seed",
        "n_samples",
        "start_age",
        "qaly_discount_rate",
        "cost_discount_rate",
        "undiscounted_qaly_discount_rate",
        "undiscounted_cost_discount_rate",
        "willingness_to_pay",
        "confounding_alpha",
        "confounding_beta",
        "confounding_mean",
        "confounding_prior_interval_lower",
        "confounding_prior_interval_upper",
        "baseline_life_years",
        "baseline_qalys_undiscounted",
        "baseline_qalys_discounted",
        "average_quality_weight",
        "e_value",
        "cvd_contribution_mean",
        "cancer_contribution_mean",
        "other_contribution_mean",
        "constants",
        "reference_case",
        "decision_context",
        "decision_summary",
        "model_interval",
        "evidence_registry",
        "methodology_provenance",
        "sensitivity_results",
        "nuts",
    }
)

_CONSTANT_FIELDS = frozenset(
    {
        "target_age",
        "life_expectancy_approx",
        "allergy_prevalence_lower",
        "allergy_prevalence_upper",
        "nice_lower_gbp",
        "nice_upper_gbp",
        "gbp_usd_rate",
        "gbp_usd_rate_date",
    }
)

_REFERENCE_CASE_FIELDS = frozenset(
    {
        "id",
        "name",
        "perspective",
        "health_discount_rate",
        "cost_discount_rate",
        "utility_preference_order",
        "reporting_standard",
        "formal_reference_case",
        "source_urls",
        "notes",
    }
)

_DECISION_CONTEXT_FIELDS = frozenset(
    {
        "intervention",
        "comparator",
        "outcome",
        "cost_basis",
        "not_modeled",
        "ranking_metric",
        "probability_metric",
    }
)

_DECISION_SUMMARY_FIELDS = frozenset(
    {
        "criterion",
        "willingness_to_pay_usd_per_qaly",
        "comparator_option",
        "comparator_expected_net_monetary_benefit",
        "comparator_probability_optimal",
        "recommended_option_ids",
        "recommended_option",
        "recommended_nut_id",
        "best_nut_alternative_id",
        "best_nut_alternative",
        "best_nut_expected_net_monetary_benefit",
        "all_nut_interventions_have_negative_expected_nmb",
        "nut_rank_scope",
        "all_option_evaluation",
    }
)

_MODEL_INTERVAL_FIELDS = frozenset({"kind", "level", "quantiles", "posterior"})
_EVIDENCE_REGISTRY_FIELDS = frozenset(
    {
        "action_kind",
        "active_coefficients",
        "structurally_excluded_coefficients",
        "deferred_substitution_contrasts",
    }
)
_EVIDENCE_COEFFICIENT_FIELDS = frozenset(
    {
        "pathway",
        "nutrient",
        "mean",
        "sd",
        "unit",
        "outcome",
        "contrast",
        "source",
        "source_url",
    }
)

_ANALYSIS_SPEC_FIELDS = frozenset(
    {
        "n_samples",
        "seed",
        "population",
        "economics",
        "causal_fraction",
        "effect_model",
        "action",
        "decision",
    }
)
_POPULATION_SPEC_FIELDS = frozenset(
    {"start_age", "terminal_age", "geography", "life_table", "quality_weights"}
)
_ECONOMIC_SPEC_FIELDS = frozenset(
    {
        "health_discount_rate",
        "cost_discount_rate",
        "willingness_to_pay_usd_per_qaly",
        "perspective",
        "price_year",
    }
)
_CAUSAL_FRACTION_SPEC_FIELDS = frozenset(
    {"distribution", "alpha", "beta", "interpretation"}
)
_EFFECT_MODEL_SPEC_FIELDS = frozenset(
    {
        "source_effect_measure",
        "lifecycle_scale",
        "translation",
        "age_pattern",
        "latency_years",
    }
)
_ACTION_SPEC_FIELDS = frozenset(
    {
        "kind",
        "serving_grams_per_day",
        "adherence",
        "persistence",
        "displaced_food",
        "baseline_diet_observed",
        "energy_compensation_modeled",
        "adiposity_effects_modeled",
        "direct_morbidity_and_harms_modeled",
    }
)
_DECISION_SPEC_FIELDS = frozenset({"comparator_option_id", "option_ids", "criterion"})

_METHODOLOGY_PROVENANCE_FIELDS = frozenset(
    {
        "provenance_schema_version",
        "whatnut_model_version",
        "whatnut_repository_url",
        "optiqal_repository_url",
        "optiqal_reference_commit",
        "optiqal_reference_url",
        "optiqal_reference_scope",
        "rng_algorithm",
        "content_hash_algorithm",
        "scientific_code_sha256",
        "input_data_sha256",
        "analysis_spec_sha256",
        "analysis_fingerprint_sha256",
        "runtime_dependency",
        "adopted",
        "whatnut_extensions",
        "deliberate_differences",
    }
)

_NUT_FIELDS = frozenset(
    {
        "name",
        "life_years_mean",
        "life_years_model_interval_lower",
        "life_years_model_interval_upper",
        "qaly_mean",
        "qaly_model_interval_lower",
        "qaly_model_interval_upper",
        "expected_qaly_cvd",
        "expected_qaly_cancer",
        "expected_qaly_other",
        "qaly_undiscounted_mean",
        "qaly_undiscounted_model_interval_lower",
        "qaly_undiscounted_model_interval_upper",
        "expected_upside",
        "expected_downside",
        "p_positive",
        "p_negative",
        "annual_cost",
        "lifetime_cost_mean",
        "icer_expected",
        "icer_undiscounted_expected",
        "p_nmb_positive",
        "p_nmb_positive_undiscounted",
        "p_optimal",
        "expected_net_monetary_benefit",
        "expected_net_monetary_benefit_undiscounted",
        "nut_alternative_rank",
        "rr_cvd",
        "rr_cancer",
        "rr_other",
        "cvd_contribution",
        "cancer_contribution",
        "other_contribution",
    }
)

_TOP_LEVEL_INTEGER_FIELDS = frozenset({"seed", "n_samples", "start_age"})
_TOP_LEVEL_NUMBER_FIELDS = (
    _TOP_LEVEL_FIELDS
    - _TOP_LEVEL_INTEGER_FIELDS
    - {
        "schema_version",
        "analysis_spec",
        "constants",
        "reference_case",
        "decision_context",
        "decision_summary",
        "model_interval",
        "evidence_registry",
        "methodology_provenance",
        "sensitivity_results",
        "nuts",
    }
)
_NUT_STRING_FIELDS = frozenset({"name"})
_NUT_OPTIONAL_NUMBER_FIELDS = frozenset({"icer_expected", "icer_undiscounted_expected"})
_EXPECTED_NUT_IDS = frozenset(
    {
        "walnut",
        "almond",
        "pistachio",
        "pecan",
        "macadamia",
        "peanut",
        "hazelnut",
        "cashew",
    }
)
_COMPARATOR_OPTION_ID = "no_modeled_nut_intervention"
_EXPECTED_OPTION_IDS = _EXPECTED_NUT_IDS | {_COMPARATOR_OPTION_ID}
_ALL_OPTION_EVALUATION_FIELDS = frozenset(
    {"expected_nmb", "probability_optimal", "ranking", "recommended_option_ids"}
)

# Schema 2.0.0 stores derived quantities at these canonical precisions.  The
# validator allows exactly the uncertainty introduced by rounding the inputs
# and output, rather than using broad relative tolerances that could hide a
# materially contradictory artifact.
_QALY_DECIMALS = 9
_COST_DECIMALS = 6
_ICER_DECIMALS = 0
_NUT_NMB_DECIMALS = 2
_DECISION_NMB_DECIMALS = 6
_NUT_PROBABILITY_DECIMALS = 4
_OPTION_PROBABILITY_DECIMALS = 9
_PATHWAY_CONTRIBUTION_DECIMALS = 6
_TOP_PATHWAY_CONTRIBUTION_DECIMALS = 2
_BASELINE_OUTCOME_DECIMALS = 2
_AVERAGE_QUALITY_DECIMALS = 3
_MIN_SUPPORTED_START_AGE = 30
_MAX_SUPPORTED_START_AGE = 70


def _format_field_names(fields: set[object]) -> str:
    return ", ".join(sorted(repr(field) for field in fields))


def _require_mapping(value: Any, *, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"Results artifact {path} must be a JSON object.")
    return value


def _validate_exact_fields(
    value: Any,
    expected: frozenset[str],
    *,
    path: str,
) -> Mapping[str, Any]:
    mapping = _require_mapping(value, path=path)
    actual = set(mapping)
    missing = set(expected) - actual
    unexpected = actual - set(expected)
    if missing:
        raise ValueError(
            f"Results artifact {path} is missing required fields: "
            f"{_format_field_names(missing)}."
        )
    if unexpected:
        raise ValueError(
            f"Results artifact {path} has unexpected fields for schema "
            f"{RESULTS_SCHEMA_VERSION}: {_format_field_names(unexpected)}."
        )
    return mapping


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _require_number(value: Any, *, path: str) -> float:
    if not _is_number(value) or not math.isfinite(float(value)):
        raise ValueError(f"Results artifact {path} must be a finite number.")
    return float(value)


def _require_probability(value: Any, *, path: str) -> float:
    probability = _require_number(value, path=path)
    if not 0 <= probability <= 1:
        raise ValueError(f"Results artifact {path} must be between 0 and 1.")
    return probability


def _require_string(value: Any, *, path: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"Results artifact {path} must be a non-empty string.")
    return value


def _require_string_sequence(value: Any, *, path: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(
            f"Results artifact {path} must be a non-empty array of strings."
        )
    if any(not isinstance(item, str) or not item for item in value):
        raise ValueError(
            f"Results artifact {path} must contain only non-empty strings."
        )
    return tuple(value)


def _rounding_error(decimal_places: int) -> float:
    """Return the maximum absolute error from decimal rounding."""
    return 0.5 * 10.0**-decimal_places


def _require_stored_precision_close(
    actual: float,
    expected: float,
    *,
    path: str,
    relationship: str,
    absolute_tolerance: float,
) -> None:
    """Require an algebraic invariant within its declared storage precision."""
    # A few ulps cover binary evaluation of decimal JSON values without
    # broadening the domain-level rounding allowance.
    floating_point_slack = 4 * max(math.ulp(actual), math.ulp(expected))
    if not math.isclose(
        actual,
        expected,
        rel_tol=0.0,
        abs_tol=absolute_tolerance + floating_point_slack,
    ):
        raise ValueError(
            f"Results artifact {path} must agree with {relationship} "
            "within stored precision."
        )


def _nmb_tolerance(willingness_to_pay: float, *, output_decimals: int) -> float:
    """Bound NMB error induced by the stored QALY, cost, and NMB values."""
    return (
        abs(willingness_to_pay) * _rounding_error(_QALY_DECIMALS)
        + _rounding_error(_COST_DECIMALS)
        + _rounding_error(output_decimals)
    )


def _icer_tolerance(cost: float, qaly: float) -> float:
    """Bound ratio error induced by stored cost, QALY, and ICER precision."""
    qaly_error = _rounding_error(_QALY_DECIMALS)
    cost_error = _rounding_error(_COST_DECIMALS)
    if qaly <= qaly_error:
        return math.inf
    expected = cost / qaly
    lowest = max(0.0, cost - cost_error) / (qaly + qaly_error)
    highest = (cost + cost_error) / (qaly - qaly_error)
    return max(abs(expected - lowest), abs(highest - expected)) + _rounding_error(
        _ICER_DECIMALS
    )


def _validate_finite_numbers(value: Any, *, path: str = "$") -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(
            f"Results artifact contains a non-finite number at {path}; "
            "the value is not JSON compliant."
        )
    if isinstance(value, Mapping):
        for key, child in value.items():
            _validate_finite_numbers(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _validate_finite_numbers(child, path=f"{path}[{index}]")


def _validate_scalar_types(data: Mapping[str, Any]) -> None:
    for field in _TOP_LEVEL_INTEGER_FIELDS:
        if not isinstance(data[field], int) or isinstance(data[field], bool):
            raise ValueError(f"Results artifact $.{field} must be an integer.")
    for field in _TOP_LEVEL_NUMBER_FIELDS:
        _require_number(data[field], path=f"$.{field}")

    if data["seed"] < 0:
        raise ValueError("Results artifact $.seed must be non-negative.")
    if data["n_samples"] < 1:
        raise ValueError("Results artifact $.n_samples must be positive.")
    if not _MIN_SUPPORTED_START_AGE <= data["start_age"] <= _MAX_SUPPORTED_START_AGE:
        raise ValueError(
            "Results artifact $.start_age must be within the supported adult "
            f"model domain [{_MIN_SUPPORTED_START_AGE}, "
            f"{_MAX_SUPPORTED_START_AGE}]."
        )
    for field in (
        "qaly_discount_rate",
        "cost_discount_rate",
        "undiscounted_qaly_discount_rate",
        "undiscounted_cost_discount_rate",
    ):
        rate = float(data[field])
        if not 0 <= rate < 1:
            raise ValueError(f"Results artifact $.{field} must be in [0, 1).")
    if data["willingness_to_pay"] <= 0:
        raise ValueError("Results artifact $.willingness_to_pay must be positive.")
    for field in ("confounding_alpha", "confounding_beta"):
        if data[field] <= 0:
            raise ValueError(f"Results artifact $.{field} must be positive.")
    for field in (
        "confounding_mean",
        "confounding_prior_interval_lower",
        "confounding_prior_interval_upper",
        "average_quality_weight",
    ):
        _require_probability(data[field], path=f"$.{field}")
    if not (
        data["confounding_prior_interval_lower"]
        <= data["confounding_mean"]
        <= data["confounding_prior_interval_upper"]
    ):
        raise ValueError("Results artifact confounding interval must contain its mean.")
    if (
        data["baseline_life_years"] <= 0
        or data["baseline_qalys_undiscounted"] <= 0
        or data["baseline_qalys_discounted"] <= 0
    ):
        raise ValueError("Results artifact baseline outcomes must be positive.")
    if data["baseline_qalys_undiscounted"] > data["baseline_life_years"]:
        raise ValueError(
            "Results artifact baseline QALYs cannot exceed baseline life-years."
        )
    if data["baseline_qalys_discounted"] > data["baseline_qalys_undiscounted"]:
        raise ValueError(
            "Results artifact discounted baseline QALYs cannot exceed "
            "undiscounted baseline QALYs."
        )
    expected_average_quality = float(data["baseline_qalys_undiscounted"]) / float(
        data["baseline_life_years"]
    )
    baseline_ratio_tolerance = 2 * _rounding_error(_BASELINE_OUTCOME_DECIMALS) / float(
        data["baseline_life_years"]
    ) + _rounding_error(_AVERAGE_QUALITY_DECIMALS)
    _require_stored_precision_close(
        float(data["average_quality_weight"]),
        expected_average_quality,
        path="$.average_quality_weight",
        relationship="baseline_qalys_undiscounted / baseline_life_years",
        absolute_tolerance=baseline_ratio_tolerance,
    )
    if data["qaly_discount_rate"] == 0:
        _require_stored_precision_close(
            float(data["baseline_qalys_discounted"]),
            float(data["baseline_qalys_undiscounted"]),
            path="$.baseline_qalys_discounted",
            relationship="undiscounted baseline QALYs at a zero health discount rate",
            absolute_tolerance=2 * _rounding_error(_BASELINE_OUTCOME_DECIMALS),
        )
    contribution_total = sum(
        float(data[field])
        for field in (
            "cvd_contribution_mean",
            "cancer_contribution_mean",
            "other_contribution_mean",
        )
    )
    # Pathway fields are signed additive attributions, not probabilities. A
    # protective pathway can therefore exceed one when another pathway is
    # harmful; their invariant is the unit total.
    _require_stored_precision_close(
        contribution_total,
        1.0,
        path="top-level pathway contributions",
        relationship="a unit total",
        absolute_tolerance=3 * _rounding_error(_TOP_PATHWAY_CONTRIBUTION_DECIMALS),
    )


def _validate_analysis_spec(value: Any, data: Mapping[str, Any]) -> None:
    """Validate the immutable run contract and its top-level projections."""
    spec = _validate_exact_fields(value, _ANALYSIS_SPEC_FIELDS, path="$.analysis_spec")

    for field in ("n_samples", "seed"):
        if not isinstance(spec[field], int) or isinstance(spec[field], bool):
            raise ValueError(
                f"Results artifact $.analysis_spec.{field} must be an integer."
            )
        if spec[field] != data[field]:
            raise ValueError(
                f"Results artifact analysis_spec.{field} must match top-level {field}."
            )

    population = _validate_exact_fields(
        spec["population"],
        _POPULATION_SPEC_FIELDS,
        path="$.analysis_spec.population",
    )
    for field in ("start_age", "terminal_age"):
        if not isinstance(population[field], int) or isinstance(
            population[field], bool
        ):
            raise ValueError(
                f"Results artifact $.analysis_spec.population.{field} must be an integer."
            )
    if (
        population["start_age"] != data["start_age"]
        or population["terminal_age"] != 100
    ):
        raise ValueError(
            "Results artifact analysis_spec population must match start_age and "
            "use terminal_age 100."
        )
    for field in ("geography", "life_table", "quality_weights"):
        _require_string(population[field], path=f"$.analysis_spec.population.{field}")

    economics = _validate_exact_fields(
        spec["economics"],
        _ECONOMIC_SPEC_FIELDS,
        path="$.analysis_spec.economics",
    )
    projected_economics = {
        "health_discount_rate": "qaly_discount_rate",
        "cost_discount_rate": "cost_discount_rate",
        "willingness_to_pay_usd_per_qaly": "willingness_to_pay",
    }
    for field, top_level_field in projected_economics.items():
        number = _require_number(
            economics[field], path=f"$.analysis_spec.economics.{field}"
        )
        if number != data[top_level_field]:
            raise ValueError(
                f"Results artifact analysis_spec.economics.{field} must match "
                f"top-level {top_level_field}."
            )
    _require_string(
        economics["perspective"], path="$.analysis_spec.economics.perspective"
    )
    if not isinstance(economics["price_year"], int) or isinstance(
        economics["price_year"], bool
    ):
        raise ValueError(
            "Results artifact analysis_spec.economics.price_year must be an integer."
        )

    causal = _validate_exact_fields(
        spec["causal_fraction"],
        _CAUSAL_FRACTION_SPEC_FIELDS,
        path="$.analysis_spec.causal_fraction",
    )
    if causal["distribution"] != "beta":
        raise ValueError("Results artifact causal-fraction distribution must be beta.")
    for field in ("alpha", "beta"):
        shape = _require_number(
            causal[field], path=f"$.analysis_spec.causal_fraction.{field}"
        )
        if shape != data[f"confounding_{field}"]:
            raise ValueError(
                f"Results artifact analysis_spec causal {field} must match top-level confounding_{field}."
            )
    _require_string(
        causal["interpretation"], path="$.analysis_spec.causal_fraction.interpretation"
    )

    effect_model = _validate_exact_fields(
        spec["effect_model"],
        _EFFECT_MODEL_SPEC_FIELDS,
        path="$.analysis_spec.effect_model",
    )
    expected_effect_model = {
        "source_effect_measure": "cause_specific_mortality_relative_risk",
        "lifecycle_scale": "cause_specific_integrated_hazard",
        "translation": "relative_risk_used_as_proportional_hazard_ratio",
        "age_pattern": "constant_proportional_effect",
        "latency_years": 0,
    }
    if effect_model != expected_effect_model:
        raise ValueError("Results artifact effect-model specification is unsupported.")

    action = _validate_exact_fields(
        spec["action"],
        _ACTION_SPEC_FIELDS,
        path="$.analysis_spec.action",
    )
    if (
        action["kind"] != "gross_addition"
        or _require_number(
            action["serving_grams_per_day"],
            path="$.analysis_spec.action.serving_grams_per_day",
        )
        != 28.0
        or _require_number(action["adherence"], path="$.analysis_spec.action.adherence")
        != 1.0
        or action["persistence"] != "lifetime_while_alive"
        or action["displaced_food"] is not None
    ):
        raise ValueError("Results artifact action specification is not implemented.")
    for field in (
        "baseline_diet_observed",
        "energy_compensation_modeled",
        "adiposity_effects_modeled",
        "direct_morbidity_and_harms_modeled",
    ):
        if action[field] is not False:
            raise ValueError(
                f"Results artifact analysis_spec.action.{field} must be false."
            )

    decision = _validate_exact_fields(
        spec["decision"],
        _DECISION_SPEC_FIELDS,
        path="$.analysis_spec.decision",
    )
    if decision["comparator_option_id"] != _COMPARATOR_OPTION_ID:
        raise ValueError("Results artifact decision comparator ID is unsupported.")
    option_ids = _require_string_sequence(
        decision["option_ids"], path="$.analysis_spec.decision.option_ids"
    )
    if set(option_ids) != set(_EXPECTED_NUT_IDS) or len(option_ids) != len(
        _EXPECTED_NUT_IDS
    ):
        raise ValueError(
            "Results artifact analysis_spec must contain every configured nut option exactly once."
        )
    if decision["criterion"] != "maximum_expected_net_monetary_benefit":
        raise ValueError("Results artifact decision criterion is unsupported.")


def _validate_nuts(value: Any, data: Mapping[str, Any]) -> Mapping[str, Any]:
    nuts = _validate_exact_fields(value, _EXPECTED_NUT_IDS, path="$.nuts")
    ranks: list[int] = []
    for nut_id, raw_nut in nuts.items():
        path = f"$.nuts.{nut_id}"
        nut = _validate_exact_fields(raw_nut, _NUT_FIELDS, path=path)
        for field in _NUT_STRING_FIELDS:
            _require_string(nut[field], path=f"{path}.{field}")
        rank = nut["nut_alternative_rank"]
        if not isinstance(rank, int) or isinstance(rank, bool):
            raise ValueError(
                f"Results artifact {path}.nut_alternative_rank must be an integer."
            )
        ranks.append(rank)
        number_fields = (
            _NUT_FIELDS
            - _NUT_STRING_FIELDS
            - {
                "nut_alternative_rank",
            }
        )
        for field in number_fields:
            field_value = nut[field]
            if field in _NUT_OPTIONAL_NUMBER_FIELDS and field_value is None:
                continue
            _require_number(field_value, path=f"{path}.{field}")
        for field in (
            "p_positive",
            "p_negative",
            "p_nmb_positive",
            "p_nmb_positive_undiscounted",
            "p_optimal",
        ):
            _require_probability(nut[field], path=f"{path}.{field}")
        for field in ("annual_cost", "lifetime_cost_mean"):
            if nut[field] < 0:
                raise ValueError(
                    f"Results artifact {path}.{field} must be non-negative."
                )
        for field in _NUT_OPTIONAL_NUMBER_FIELDS:
            if nut[field] is not None and nut[field] < 0:
                raise ValueError(
                    f"Results artifact {path}.{field} must be non-negative when "
                    "defined."
                )
        for prefix in ("life_years", "qaly", "qaly_undiscounted"):
            if not (
                nut[f"{prefix}_model_interval_lower"]
                <= nut[f"{prefix}_mean"]
                <= nut[f"{prefix}_model_interval_upper"]
            ):
                raise ValueError(
                    f"Results artifact {path} {prefix} interval must contain its mean."
                )

        expected_upside = float(nut["expected_upside"])
        expected_downside = float(nut["expected_downside"])
        if expected_upside < 0:
            raise ValueError(
                f"Results artifact {path}.expected_upside must be non-negative."
            )
        if expected_downside > 0:
            raise ValueError(
                f"Results artifact {path}.expected_downside must be non-positive."
            )
        _require_stored_precision_close(
            float(nut["qaly_mean"]),
            expected_upside + expected_downside,
            path=f"{path}.qaly_mean",
            relationship="expected_upside + expected_downside",
            absolute_tolerance=3 * _rounding_error(_QALY_DECIMALS),
        )

        qaly = float(nut["qaly_mean"])
        component_fields = (
            "expected_qaly_cvd",
            "expected_qaly_cancer",
            "expected_qaly_other",
        )
        share_fields = (
            "cvd_contribution",
            "cancer_contribution",
            "other_contribution",
        )
        pathway_qaly_total = sum(float(nut[field]) for field in component_fields)
        _require_stored_precision_close(
            qaly,
            pathway_qaly_total,
            path=f"{path}.qaly_mean",
            relationship="the sum of signed pathway QALY components",
            absolute_tolerance=4 * _rounding_error(_QALY_DECIMALS),
        )
        for component_field, share_field in zip(
            component_fields,
            share_fields,
            strict=True,
        ):
            component = float(nut[component_field])
            share = float(nut[share_field])
            share_product_tolerance = (
                abs(qaly) * _rounding_error(_PATHWAY_CONTRIBUTION_DECIMALS)
                + abs(share) * _rounding_error(_QALY_DECIMALS)
                + _rounding_error(_QALY_DECIMALS)
            )
            _require_stored_precision_close(
                component,
                share * qaly,
                path=f"{path}.{share_field}",
                relationship=f"{component_field} / qaly_mean",
                absolute_tolerance=share_product_tolerance,
            )

        positive_probability = float(nut["p_positive"])
        negative_probability = float(nut["p_negative"])
        if expected_upside == 0.0 and expected_downside == 0.0:
            _require_stored_precision_close(
                positive_probability + negative_probability,
                0.0,
                path=f"{path}.p_positive and p_negative",
                relationship="zero probability for an identically zero effect",
                absolute_tolerance=2 * _rounding_error(_NUT_PROBABILITY_DECIMALS),
            )
        else:
            _require_stored_precision_close(
                positive_probability + negative_probability,
                1.0,
                path=f"{path}.p_positive and p_negative",
                relationship="complementary positive and negative effect probabilities",
                absolute_tolerance=2 * _rounding_error(_NUT_PROBABILITY_DECIMALS),
            )

        pathway_total = sum(float(nut[field]) for field in share_fields)
        # As above, do not range-check signed attribution shares individually.
        _require_stored_precision_close(
            pathway_total,
            0.0 if qaly == 0 else 1.0,
            path=f"{path} pathway contributions",
            relationship=(
                "a zero total for a null effect"
                if qaly == 0
                else "a unit total"
            ),
            absolute_tolerance=3 * _rounding_error(_PATHWAY_CONTRIBUTION_DECIMALS),
        )

        cost = float(nut["lifetime_cost_mean"])
        expected_nmb = float(data["willingness_to_pay"]) * qaly - cost
        _require_stored_precision_close(
            float(nut["expected_net_monetary_benefit"]),
            expected_nmb,
            path=f"{path}.expected_net_monetary_benefit",
            relationship="willingness_to_pay * qaly_mean - lifetime_cost_mean",
            absolute_tolerance=_nmb_tolerance(
                float(data["willingness_to_pay"]),
                output_decimals=_NUT_NMB_DECIMALS,
            ),
        )

        for icer_field, qaly_field in (
            ("icer_expected", "qaly_mean"),
            ("icer_undiscounted_expected", "qaly_undiscounted_mean"),
        ):
            if nut[qaly_field] > 0 and nut[icer_field] is None:
                raise ValueError(
                    f"Results artifact {path}.{icer_field} must be defined when "
                    f"{qaly_field} is positive."
                )
            if nut[qaly_field] <= 0 and nut[icer_field] is not None:
                raise ValueError(
                    f"Results artifact {path}.{icer_field} must be null when "
                    f"{qaly_field} is non-positive."
                )
        if nut["icer_expected"] is not None:
            _require_stored_precision_close(
                float(nut["icer_expected"]),
                cost / qaly,
                path=f"{path}.icer_expected",
                relationship="lifetime_cost_mean / qaly_mean",
                absolute_tolerance=_icer_tolerance(cost, qaly),
            )

    expected_ranks = list(range(1, len(_EXPECTED_NUT_IDS) + 1))
    if sorted(ranks) != expected_ranks:
        raise ValueError(
            "Results artifact nut_alternative_rank values must be unique and "
            f"cover {expected_ranks}."
        )
    for pathway in ("cvd", "cancer", "other"):
        expected_mean = sum(
            float(nut[f"{pathway}_contribution"]) for nut in nuts.values()
        ) / len(nuts)
        _require_stored_precision_close(
            float(data[f"{pathway}_contribution_mean"]),
            expected_mean,
            path=f"$.{pathway}_contribution_mean",
            relationship=f"the mean per-nut {pathway} contribution share",
            absolute_tolerance=(
                _rounding_error(_TOP_PATHWAY_CONTRIBUTION_DECIMALS)
                + _rounding_error(_PATHWAY_CONTRIBUTION_DECIMALS)
            ),
        )
    return nuts


def _validate_constants(value: Any, data: Mapping[str, Any]) -> None:
    constants = _validate_exact_fields(value, _CONSTANT_FIELDS, path="$.constants")
    for field in ("target_age", "life_expectancy_approx"):
        if (
            not isinstance(constants[field], int)
            or isinstance(constants[field], bool)
            or constants[field] <= 0
        ):
            raise ValueError(f"Results artifact $.constants.{field} must be positive.")
    for field in ("allergy_prevalence_lower", "allergy_prevalence_upper"):
        prevalence = _require_number(constants[field], path=f"$.constants.{field}")
        if not 0 <= prevalence <= 100:
            raise ValueError(
                f"Results artifact $.constants.{field} must be between 0 and 100."
            )
    for field in ("nice_lower_gbp", "nice_upper_gbp", "gbp_usd_rate"):
        if _require_number(constants[field], path=f"$.constants.{field}") <= 0:
            raise ValueError(f"Results artifact $.constants.{field} must be positive.")
    _require_string(
        constants["gbp_usd_rate_date"], path="$.constants.gbp_usd_rate_date"
    )
    if constants["target_age"] != data["start_age"]:
        raise ValueError(
            "Results artifact constants.target_age must match top-level start_age."
        )
    if constants["life_expectancy_approx"] != round(data["baseline_life_years"]):
        raise ValueError(
            "Results artifact constants.life_expectancy_approx must match the "
            "rounded baseline life expectancy."
        )


def _validate_reference_case(value: Any, data: Mapping[str, Any]) -> None:
    reference = _validate_exact_fields(
        value,
        _REFERENCE_CASE_FIELDS,
        path="$.reference_case",
    )
    for field in ("id", "name", "perspective", "reporting_standard"):
        _require_string(reference[field], path=f"$.reference_case.{field}")
    for field in ("health_discount_rate", "cost_discount_rate"):
        rate = _require_number(reference[field], path=f"$.reference_case.{field}")
        if not 0 <= rate < 1:
            raise ValueError(
                f"Results artifact $.reference_case.{field} must be in [0, 1)."
            )
    if reference["health_discount_rate"] != data["qaly_discount_rate"]:
        raise ValueError(
            "Results artifact reference-case health discount rate must match "
            "qaly_discount_rate."
        )
    if reference["cost_discount_rate"] != data["cost_discount_rate"]:
        raise ValueError(
            "Results artifact reference-case cost discount rate must match "
            "cost_discount_rate."
        )
    if not isinstance(reference["formal_reference_case"], bool):
        raise ValueError(
            "Results artifact $.reference_case.formal_reference_case must be a boolean."
        )
    for field in ("utility_preference_order", "source_urls", "notes"):
        _require_string_sequence(reference[field], path=f"$.reference_case.{field}")


def _validate_decision_context(value: Any) -> None:
    context = _validate_exact_fields(
        value,
        _DECISION_CONTEXT_FIELDS,
        path="$.decision_context",
    )
    for field in _DECISION_CONTEXT_FIELDS - {"not_modeled"}:
        _require_string(context[field], path=f"$.decision_context.{field}")
    _require_string_sequence(
        context["not_modeled"],
        path="$.decision_context.not_modeled",
    )


def _validate_model_interval(value: Any) -> None:
    interval = _validate_exact_fields(
        value,
        _MODEL_INTERVAL_FIELDS,
        path="$.model_interval",
    )
    kind = _require_string(interval["kind"], path="$.model_interval.kind")
    level = _require_probability(interval["level"], path="$.model_interval.level")
    quantiles = interval["quantiles"]
    if not isinstance(quantiles, (list, tuple)) or len(quantiles) != 2:
        raise ValueError(
            "Results artifact $.model_interval.quantiles must contain two values."
        )
    lower = _require_probability(quantiles[0], path="$.model_interval.quantiles[0]")
    upper = _require_probability(quantiles[1], path="$.model_interval.quantiles[1]")
    if not lower < upper or not math.isclose(upper - lower, level, abs_tol=1e-12):
        raise ValueError(
            "Results artifact model-interval quantiles must be ordered and match level."
        )
    if not isinstance(interval["posterior"], bool):
        raise ValueError(
            "Results artifact $.model_interval.posterior must be a boolean."
        )
    if (
        kind != "monte_carlo_model_interval"
        or level != 0.95
        or (lower, upper) != (0.025, 0.975)
        or interval["posterior"] is not False
    ):
        raise ValueError(
            "Results artifact schema 2.0.0 requires a non-posterior 95% "
            "Monte Carlo model interval."
        )


def _validate_evidence_registry(value: Any, data: Mapping[str, Any]) -> None:
    registry = _validate_exact_fields(
        value,
        _EVIDENCE_REGISTRY_FIELDS,
        path="$.evidence_registry",
    )
    action_kind = _require_string(
        registry["action_kind"], path="$.evidence_registry.action_kind"
    )
    if action_kind != data["analysis_spec"]["action"]["kind"]:
        raise ValueError(
            "Results artifact evidence-registry action must match analysis_spec."
        )

    seen: set[tuple[str, str]] = set()
    active_seen: set[tuple[str, str]] = set()
    for field, active in (
        ("active_coefficients", True),
        ("structurally_excluded_coefficients", False),
    ):
        records = registry[field]
        if not isinstance(records, list) or not records:
            raise ValueError(
                f"Results artifact $.evidence_registry.{field} must be a nonempty array."
            )
        for index, raw_record in enumerate(records):
            path = f"$.evidence_registry.{field}[{index}]"
            record = _validate_exact_fields(
                raw_record,
                _EVIDENCE_COEFFICIENT_FIELDS,
                path=path,
            )
            pathway = _require_string(record["pathway"], path=f"{path}.pathway")
            nutrient = _require_string(record["nutrient"], path=f"{path}.nutrient")
            key = (pathway, nutrient)
            if key in seen:
                raise ValueError(
                    "Results artifact evidence registry contains a duplicate coefficient."
                )
            seen.add(key)
            mean = _require_number(record["mean"], path=f"{path}.mean")
            sd = _require_number(record["sd"], path=f"{path}.sd")
            if sd < 0:
                raise ValueError(f"Results artifact {path}.sd must be nonnegative.")
            for string_field in ("unit", "outcome", "contrast", "source"):
                _require_string(record[string_field], path=f"{path}.{string_field}")
            if active:
                active_seen.add(key)
                _require_string(record["source_url"], path=f"{path}.source_url")
            elif (
                mean != 0
                or sd != 0
                or record["source_url"] is not None
                and not isinstance(record["source_url"], str)
            ):
                raise ValueError(
                    "Results artifact structurally excluded coefficients must be "
                    "fixed at zero with a null or string source URL."
                )

    expected_pathways = {"cvd", "cancer", "other"}
    expected_nutrients = {
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
    }
    expected = {
        (pathway, nutrient)
        for pathway in expected_pathways
        for nutrient in expected_nutrients
    }
    if seen != expected:
        raise ValueError(
            "Results artifact evidence registry must classify every pathway-nutrient coefficient."
        )
    expected_active = {
        ("cvd", "ala_omega3"),
        ("cvd", "fiber"),
        ("cvd", "magnesium"),
        ("cancer", "fiber"),
    }
    if active_seen != expected_active:
        raise ValueError(
            "Results artifact evidence registry has an unexpected active coefficient set."
        )
    deferred = _require_mapping(
        registry["deferred_substitution_contrasts"],
        path="$.evidence_registry.deferred_substitution_contrasts",
    )
    if not deferred:
        raise ValueError(
            "Results artifact must retain deferred substitution evidence explicitly."
        )


def _validate_methodology_provenance(
    value: Any,
    analysis_spec: Mapping[str, Any],
) -> None:
    provenance = _validate_exact_fields(
        value,
        _METHODOLOGY_PROVENANCE_FIELDS,
        path="$.methodology_provenance",
    )
    for field in (
        "provenance_schema_version",
        "whatnut_model_version",
        "whatnut_repository_url",
        "optiqal_repository_url",
        "optiqal_reference_commit",
        "optiqal_reference_url",
        "optiqal_reference_scope",
        "rng_algorithm",
        "content_hash_algorithm",
        "analysis_spec_sha256",
        "analysis_fingerprint_sha256",
    ):
        _require_string(provenance[field], path=f"$.methodology_provenance.{field}")
    commit = provenance["optiqal_reference_commit"]
    if len(commit) != 40 or any(
        character not in "0123456789abcdef" for character in commit
    ):
        raise ValueError(
            "Results artifact Optiqal reference commit must be a 40-character "
            "lowercase hexadecimal SHA."
        )
    if not isinstance(provenance["runtime_dependency"], bool):
        raise ValueError(
            "Results artifact $.methodology_provenance.runtime_dependency must "
            "be a boolean."
        )
    if provenance["content_hash_algorithm"] != "sha256":
        raise ValueError(
            "Results artifact methodology provenance must use SHA-256 hashes."
        )
    for field in ("analysis_spec_sha256", "analysis_fingerprint_sha256"):
        digest = provenance[field]
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError(
                f"Results artifact methodology provenance {field} must be a "
                "64-character lowercase SHA-256 digest."
            )
    for field in ("scientific_code_sha256", "input_data_sha256"):
        hashes = _require_mapping(
            provenance[field], path=f"$.methodology_provenance.{field}"
        )
        if not hashes:
            raise ValueError(
                f"Results artifact methodology provenance {field} must be nonempty."
            )
        for file_path, digest in hashes.items():
            _require_string(file_path, path=f"$.methodology_provenance.{field} key")
            digest = _require_string(
                digest,
                path=f"$.methodology_provenance.{field}.{file_path}",
            )
            if len(digest) != 64 or any(
                character not in "0123456789abcdef" for character in digest
            ):
                raise ValueError(
                    f"Results artifact methodology provenance hash for {file_path} "
                    "must be a 64-character lowercase SHA-256 digest."
                )
    serialized_spec = json.dumps(
        analysis_spec,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    expected_spec_digest = hashlib.sha256(serialized_spec).hexdigest()
    if provenance["analysis_spec_sha256"] != expected_spec_digest:
        raise ValueError(
            "Results artifact analysis-spec provenance hash must match analysis_spec."
        )

    fingerprint_boundary = {
        "analysis_spec_sha256": provenance["analysis_spec_sha256"],
        "content_hash_algorithm": provenance["content_hash_algorithm"],
        "input_data_sha256": provenance["input_data_sha256"],
        "optiqal_reference_commit": provenance["optiqal_reference_commit"],
        "provenance_schema_version": provenance["provenance_schema_version"],
        "rng_algorithm": provenance["rng_algorithm"],
        "scientific_code_sha256": provenance["scientific_code_sha256"],
        "whatnut_model_version": provenance["whatnut_model_version"],
    }
    serialized_boundary = json.dumps(
        fingerprint_boundary,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    expected_fingerprint = hashlib.sha256(serialized_boundary).hexdigest()
    if provenance["analysis_fingerprint_sha256"] != expected_fingerprint:
        raise ValueError(
            "Results artifact analysis fingerprint must match its hashed boundary."
        )
    for field in ("adopted", "whatnut_extensions", "deliberate_differences"):
        _require_string_sequence(
            provenance[field],
            path=f"$.methodology_provenance.{field}",
        )


def _validate_option_ids(
    value: Any,
    *,
    path: str,
    require_all: bool,
) -> tuple[str, ...]:
    option_ids = _require_string_sequence(value, path=path)
    if len(set(option_ids)) != len(option_ids):
        raise ValueError(f"Results artifact {path} must not contain duplicate IDs.")
    actual = set(option_ids)
    if require_all and actual != set(_EXPECTED_OPTION_IDS):
        raise ValueError(
            f"Results artifact {path} must contain every configured option ID."
        )
    if not actual <= set(_EXPECTED_OPTION_IDS):
        raise ValueError(f"Results artifact {path} contains an unknown option ID.")
    return option_ids


def _validate_decision_summary(
    value: Any,
    data: Mapping[str, Any],
    nuts: Mapping[str, Any],
) -> None:
    summary = _validate_exact_fields(
        value,
        _DECISION_SUMMARY_FIELDS,
        path="$.decision_summary",
    )
    for field in (
        "criterion",
        "comparator_option",
        "recommended_option",
        "best_nut_alternative",
        "nut_rank_scope",
    ):
        _require_string(summary[field], path=f"$.decision_summary.{field}")
    wtp = _require_number(
        summary["willingness_to_pay_usd_per_qaly"],
        path="$.decision_summary.willingness_to_pay_usd_per_qaly",
    )
    if wtp != data["willingness_to_pay"]:
        raise ValueError(
            "Results artifact decision-summary willingness-to-pay must match "
            "the top-level value."
        )
    comparator_nmb = _require_number(
        summary["comparator_expected_net_monetary_benefit"],
        path="$.decision_summary.comparator_expected_net_monetary_benefit",
    )
    comparator_probability = _require_probability(
        summary["comparator_probability_optimal"],
        path="$.decision_summary.comparator_probability_optimal",
    )
    best_nut_nmb = _require_number(
        summary["best_nut_expected_net_monetary_benefit"],
        path="$.decision_summary.best_nut_expected_net_monetary_benefit",
    )
    if not isinstance(
        summary["all_nut_interventions_have_negative_expected_nmb"], bool
    ):
        raise ValueError(
            "Results artifact decision-summary negative-NMB flag must be a boolean."
        )

    evaluation = _validate_exact_fields(
        summary["all_option_evaluation"],
        _ALL_OPTION_EVALUATION_FIELDS,
        path="$.decision_summary.all_option_evaluation",
    )
    expected_nmb = _validate_exact_fields(
        evaluation["expected_nmb"],
        _EXPECTED_OPTION_IDS,
        path="$.decision_summary.all_option_evaluation.expected_nmb",
    )
    probabilities = _validate_exact_fields(
        evaluation["probability_optimal"],
        _EXPECTED_OPTION_IDS,
        path="$.decision_summary.all_option_evaluation.probability_optimal",
    )
    for option_id in _EXPECTED_OPTION_IDS:
        _require_number(
            expected_nmb[option_id],
            path=(f"$.decision_summary.all_option_evaluation.expected_nmb.{option_id}"),
        )
        _require_probability(
            probabilities[option_id],
            path=(
                "$.decision_summary.all_option_evaluation.probability_optimal."
                f"{option_id}"
            ),
        )
    _require_stored_precision_close(
        float(sum(probabilities.values())),
        1.0,
        path="$.decision_summary.all_option_evaluation.probability_optimal",
        relationship="a unit total across mutually exclusive options",
        absolute_tolerance=len(_EXPECTED_OPTION_IDS)
        * _rounding_error(_OPTION_PROBABILITY_DECIMALS),
    )
    _require_stored_precision_close(
        float(expected_nmb[_COMPARATOR_OPTION_ID]),
        0.0,
        path=(
            "$.decision_summary.all_option_evaluation.expected_nmb."
            f"{_COMPARATOR_OPTION_ID}"
        ),
        relationship="the zero-cost, zero-effect comparator",
        absolute_tolerance=_rounding_error(_DECISION_NMB_DECIMALS),
    )
    for nut_id, nut in nuts.items():
        qaly = float(nut["qaly_mean"])
        cost = float(nut["lifetime_cost_mean"])
        expected_from_outcomes = float(data["willingness_to_pay"]) * qaly - cost
        _require_stored_precision_close(
            float(expected_nmb[nut_id]),
            expected_from_outcomes,
            path=(f"$.decision_summary.all_option_evaluation.expected_nmb.{nut_id}"),
            relationship="willingness_to_pay * qaly_mean - lifetime_cost_mean",
            absolute_tolerance=_nmb_tolerance(
                float(data["willingness_to_pay"]),
                output_decimals=_DECISION_NMB_DECIMALS,
            ),
        )

    ranking = _validate_option_ids(
        evaluation["ranking"],
        path="$.decision_summary.all_option_evaluation.ranking",
        require_all=True,
    )
    expected_ranking = tuple(
        sorted(
            _EXPECTED_OPTION_IDS,
            key=lambda option_id: (-expected_nmb[option_id], option_id),
        )
    )
    if ranking != expected_ranking:
        raise ValueError(
            "Results artifact all-option ranking must follow expected NMB."
        )
    inner_recommended = _validate_option_ids(
        evaluation["recommended_option_ids"],
        path="$.decision_summary.all_option_evaluation.recommended_option_ids",
        require_all=False,
    )
    outer_recommended = _validate_option_ids(
        summary["recommended_option_ids"],
        path="$.decision_summary.recommended_option_ids",
        require_all=False,
    )
    if inner_recommended != outer_recommended:
        raise ValueError(
            "Results artifact inner and outer recommended option IDs must match."
        )
    max_expected_nmb = max(expected_nmb.values())
    expected_recommended_ids = {
        option_id
        for option_id, option_nmb in expected_nmb.items()
        if option_nmb == max_expected_nmb
    }
    if set(inner_recommended) != expected_recommended_ids:
        raise ValueError(
            "Results artifact recommended option IDs must maximize expected NMB."
        )

    recommended_nut_id = summary["recommended_nut_id"]
    expected_recommended_nut_id = (
        outer_recommended[0]
        if len(outer_recommended) == 1 and outer_recommended[0] in _EXPECTED_NUT_IDS
        else None
    )
    if recommended_nut_id != expected_recommended_nut_id:
        raise ValueError(
            "Results artifact recommended_nut_id is inconsistent with the "
            "recommended option IDs."
        )

    best_nut_id = summary["best_nut_alternative_id"]
    if best_nut_id not in _EXPECTED_NUT_IDS:
        raise ValueError(
            "Results artifact best_nut_alternative_id must identify a configured nut."
        )
    ranked_nut_ids = tuple(option_id for option_id in ranking if option_id in nuts)
    rank_field_order = tuple(
        sorted(nuts, key=lambda option_id: nuts[option_id]["nut_alternative_rank"])
    )
    if ranked_nut_ids != rank_field_order or best_nut_id != ranked_nut_ids[0]:
        raise ValueError(
            "Results artifact nut ranks must agree with the all-option decision ranking."
        )
    if summary["best_nut_alternative"] != nuts[best_nut_id]["name"]:
        raise ValueError(
            "Results artifact best-nut label must agree with best_nut_alternative_id."
        )
    if not math.isclose(
        best_nut_nmb,
        nuts[best_nut_id]["expected_net_monetary_benefit"],
        abs_tol=1e-8,
    ):
        raise ValueError("Results artifact best-nut expected NMB fields must agree.")
    expected_all_negative = all(
        expected_nmb[nut_id] < 0 for nut_id in _EXPECTED_NUT_IDS
    )
    if (
        summary["all_nut_interventions_have_negative_expected_nmb"]
        != expected_all_negative
    ):
        raise ValueError(
            "Results artifact negative-NMB flag must agree with per-nut summaries."
        )
    if comparator_nmb != round(expected_nmb[_COMPARATOR_OPTION_ID], 2) or (
        comparator_probability != round(probabilities[_COMPARATOR_OPTION_ID], 4)
    ):
        raise ValueError("Results artifact comparator decision summaries must agree.")
    for nut_id, nut in nuts.items():
        if nut["expected_net_monetary_benefit"] != round(
            expected_nmb[nut_id], 2
        ) or nut["p_optimal"] != round(probabilities[nut_id], 4):
            raise ValueError(
                f"Results artifact decision summaries disagree for {nut_id}."
            )


def _validate_sensitivities(
    value: Any,
    data: Mapping[str, Any],
    nuts: Mapping[str, Any],
) -> None:
    sensitivities = _validate_exact_fields(
        value,
        frozenset({"confounding_prior"}),
        path="$.sensitivity_results",
    )
    rows = sensitivities["confounding_prior"]
    if not isinstance(rows, list) or not rows:
        raise ValueError(
            "Results artifact $.sensitivity_results.confounding_prior must "
            "contain at least one materialized scenario."
        )
    expected_fields = frozenset(
        {"alpha", "beta", "mean", "interpretation", "is_base", "qaly_mean"}
    )
    interpretations: list[str] = []
    base_count = 0
    base_row: Mapping[str, Any] | None = None
    for index, raw_row in enumerate(rows):
        path = f"$.sensitivity_results.confounding_prior[{index}]"
        row = _validate_exact_fields(raw_row, expected_fields, path=path)
        alpha = _require_number(row["alpha"], path=f"{path}.alpha")
        beta = _require_number(row["beta"], path=f"{path}.beta")
        mean = _require_probability(row["mean"], path=f"{path}.mean")
        if alpha <= 0 or beta <= 0:
            raise ValueError(f"Results artifact {path} Beta shapes must be positive.")
        if not math.isclose(mean, alpha / (alpha + beta), abs_tol=1e-12):
            raise ValueError(
                f"Results artifact {path}.mean must agree with its Beta shapes."
            )
        interpretation = _require_string(
            row["interpretation"],
            path=f"{path}.interpretation",
        )
        interpretations.append(interpretation)
        if not isinstance(row["is_base"], bool):
            raise ValueError(f"Results artifact {path}.is_base must be a boolean.")
        base_count += int(row["is_base"])
        if interpretation == "Base case":
            base_row = row
        qaly_mean = _validate_exact_fields(
            row["qaly_mean"],
            frozenset({"walnut", "peanut"}),
            path=f"{path}.qaly_mean",
        )
        for nut_id, qaly in qaly_mean.items():
            _require_number(qaly, path=f"{path}.qaly_mean.{nut_id}")

    expected_interpretations = {
        "Very skeptical",
        "Base case",
        "Moderate",
        "Optimistic",
    }
    if set(interpretations) != expected_interpretations or len(interpretations) != 4:
        raise ValueError(
            "Results artifact confounding sensitivities must contain each "
            "configured scenario exactly once."
        )
    if base_count != 1:
        raise ValueError(
            "Results artifact confounding sensitivities must identify one base case."
        )
    if base_row is None or not base_row["is_base"]:
        raise ValueError(
            "Results artifact sensitivity row labeled Base case must be the base case."
        )
    if (
        base_row["alpha"] != data["confounding_alpha"]
        or base_row["beta"] != data["confounding_beta"]
        or base_row["mean"] != data["confounding_mean"]
    ):
        raise ValueError(
            "Results artifact base sensitivity prior must match top-level confounding."
        )
    for nut_id in ("walnut", "peanut"):
        if base_row["qaly_mean"][nut_id] != nuts[nut_id]["qaly_mean"]:
            raise ValueError(
                "Results artifact base sensitivity QALYs must match base nut results."
            )


def validate_results_artifact(data: Mapping[str, Any]) -> None:
    """Validate the complete schema boundary required by the result loader."""
    data = _require_mapping(data, path="$")
    version = data.get("schema_version")
    if version != RESULTS_SCHEMA_VERSION:
        raise ValueError(
            "Unsupported What Nut results schema: "
            f"{version!r}; expected {RESULTS_SCHEMA_VERSION!r}."
        )

    data = _validate_exact_fields(data, _TOP_LEVEL_FIELDS, path="$")
    _validate_finite_numbers(data)
    _validate_scalar_types(data)
    _validate_analysis_spec(data["analysis_spec"], data)
    _validate_constants(data["constants"], data)
    _validate_reference_case(data["reference_case"], data)
    _validate_decision_context(data["decision_context"])
    _validate_model_interval(data["model_interval"])
    _validate_evidence_registry(data["evidence_registry"], data)
    _validate_methodology_provenance(
        data["methodology_provenance"],
        data["analysis_spec"],
    )
    nuts = _validate_nuts(data["nuts"], data)
    _validate_sensitivities(data["sensitivity_results"], data, nuts)
    _validate_decision_summary(data["decision_summary"], data, nuts)


def _reject_nonstandard_constant(value: str) -> None:
    raise ValueError(
        f"Results artifact contains non-standard JSON constant {value!r}; "
        "the value is not JSON compliant."
    )


def read_results_artifact(path: Path) -> dict[str, Any]:
    """Read and validate a generated result artifact."""
    with path.open() as file:
        data = json.load(file, parse_constant=_reject_nonstandard_constant)
    validate_results_artifact(data)
    return data


def write_results_artifact(path: Path, data: Mapping[str, Any]) -> Path:
    """Atomically write strict JSON, rejecting NaN and Infinity."""
    validate_results_artifact(data)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as file:
            temporary_path = Path(file.name)
            json.dump(data, file, indent=2, allow_nan=False)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return path


__all__ = [
    "RESULTS_SCHEMA_VERSION",
    "read_results_artifact",
    "validate_results_artifact",
    "write_results_artifact",
]
