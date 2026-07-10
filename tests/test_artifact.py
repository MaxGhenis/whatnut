"""Tests for strict, versioned result artifact I/O."""

import json
from pathlib import Path

import pytest

from whatnut.artifact import (
    RESULTS_SCHEMA_VERSION,
    read_results_artifact,
    validate_results_artifact,
    write_results_artifact,
)

COMMITTED_RESULTS_PATH = (
    Path(__file__).parents[1] / "src" / "whatnut" / "data" / "results.json"
)


def _valid_artifact() -> dict:
    """Return an independent schema-1.0.0 artifact without invoking its loader."""
    return json.loads(COMMITTED_RESULTS_PATH.read_text())


def test_artifact_round_trip_is_versioned_and_atomic(tmp_path):
    path = tmp_path / "results.json"
    data = _valid_artifact()

    assert write_results_artifact(path, data) == path
    assert read_results_artifact(path) == data
    assert not (tmp_path / ".results.json.tmp").exists()


def test_artifact_write_rejects_nonstandard_nan_without_overwriting(tmp_path):
    path = tmp_path / "results.json"
    original = _valid_artifact()
    write_results_artifact(path, original)

    invalid = _valid_artifact()
    invalid["e_value"] = float("nan")
    with pytest.raises(ValueError, match="JSON compliant"):
        write_results_artifact(path, invalid)

    assert read_results_artifact(path) == original


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_artifact_read_rejects_nonstandard_numeric_constants(tmp_path, constant):
    path = tmp_path / "results.json"
    data = _valid_artifact()
    data["e_value"] = "__NONSTANDARD_CONSTANT__"
    serialized = json.dumps(data).replace('"__NONSTANDARD_CONSTANT__"', constant)
    path.write_text(serialized)

    with pytest.raises(ValueError, match="not JSON compliant"):
        read_results_artifact(path)


def test_artifact_loader_rejects_unknown_schema(tmp_path):
    path = tmp_path / "results.json"
    data = _valid_artifact()
    data["schema_version"] = "999.0.0"
    path.write_text(json.dumps(data))

    with pytest.raises(ValueError, match="Unsupported What Nut results schema"):
        read_results_artifact(path)


def test_artifact_validator_requires_complete_current_schema():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_results_artifact({"schema_version": RESULTS_SCHEMA_VERSION})


def test_artifact_validator_rejects_legacy_top_level_alias():
    data = _valid_artifact()
    data["cost_effectiveness_threshold"] = data["willingness_to_pay"]

    with pytest.raises(ValueError, match="unexpected fields"):
        validate_results_artifact(data)


@pytest.mark.parametrize(
    "legacy_field",
    ["icer_median", "p_cost_effective", "decision_rank"],
)
def test_artifact_validator_rejects_legacy_nut_aliases(legacy_field):
    data = _valid_artifact()
    data["nuts"]["walnut"][legacy_field] = 1

    with pytest.raises(ValueError, match="unexpected fields"):
        validate_results_artifact(data)


def test_artifact_validator_requires_materialized_sensitivities():
    data = _valid_artifact()
    data["sensitivity_results"] = {"confounding_prior": []}

    with pytest.raises(ValueError, match="materialized scenario"):
        validate_results_artifact(data)


@pytest.mark.parametrize(
    ("path", "value", "message"),
    [
        (
            ("decision_summary", "comparator_probability_optimal"),
            "0.97",
            "finite number",
        ),
        (
            ("decision_summary", "all_option_evaluation"),
            None,
            "JSON object",
        ),
        (
            ("reference_case", "formal_reference_case"),
            "false",
            "boolean",
        ),
        (
            ("model_interval", "level"),
            "0.95",
            "finite number",
        ),
    ],
)
def test_artifact_validator_rejects_invalid_nested_types(path, value, message):
    data = _valid_artifact()
    target = data
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match=message):
        validate_results_artifact(data)


def test_artifact_validator_requires_every_configured_nut():
    data = _valid_artifact()
    del data["nuts"]["cashew"]

    with pytest.raises(ValueError, match="missing required fields"):
        validate_results_artifact(data)


def test_artifact_validator_rejects_duplicate_nut_ranks():
    data = _valid_artifact()
    data["nuts"]["walnut"]["nut_alternative_rank"] = data["nuts"]["almond"][
        "nut_alternative_rank"
    ]

    with pytest.raises(ValueError, match="nut_alternative_rank"):
        validate_results_artifact(data)


def test_artifact_validator_rejects_swapped_sensitivity_base_flag():
    data = _valid_artifact()
    rows = data["sensitivity_results"]["confounding_prior"]
    base = next(row for row in rows if row["interpretation"] == "Base case")
    non_base = next(row for row in rows if row["interpretation"] != "Base case")
    base["is_base"] = False
    non_base["is_base"] = True

    with pytest.raises(ValueError, match="Base case must be the base case"):
        validate_results_artifact(data)
