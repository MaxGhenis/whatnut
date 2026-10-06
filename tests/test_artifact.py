"""Tests for strict, versioned result artifact I/O."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

import whatnut.artifact as artifact_module
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
    """Return an independent schema-2.0.0 artifact without invoking its loader."""
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


def test_artifact_concurrent_writes_use_unique_atomic_tempfiles(
    tmp_path,
    monkeypatch,
):
    path = tmp_path / "results.json"
    artifacts = [_valid_artifact() for _ in range(4)]
    for seed, artifact in enumerate(artifacts, start=100):
        artifact["seed"] = seed
        artifact["analysis_spec"]["seed"] = seed

    real_named_temporary_file = artifact_module.tempfile.NamedTemporaryFile
    created_paths: list[Path] = []
    creation_barrier = threading.Barrier(len(artifacts))

    def synchronized_named_temporary_file(*args, **kwargs):
        file = real_named_temporary_file(*args, **kwargs)
        created_paths.append(Path(file.name))
        creation_barrier.wait(timeout=5)
        return file

    monkeypatch.setattr(
        artifact_module.tempfile,
        "NamedTemporaryFile",
        synchronized_named_temporary_file,
    )

    with ThreadPoolExecutor(max_workers=len(artifacts)) as executor:
        written_paths = list(
            executor.map(
                lambda artifact: write_results_artifact(path, artifact),
                artifacts,
            )
        )

    assert written_paths == [path] * len(artifacts)
    assert len(created_paths) == len(set(created_paths)) == len(artifacts)
    assert all(not temporary_path.exists() for temporary_path in created_paths)
    assert read_results_artifact(path)["seed"] in {100, 101, 102, 103}


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


def test_artifact_validator_rejects_legacy_ci_field_names():
    data = _valid_artifact()
    walnut = data["nuts"]["walnut"]
    walnut["qaly_ci_lower"] = walnut.pop("qaly_model_interval_lower")

    with pytest.raises(ValueError, match="missing required fields"):
        validate_results_artifact(data)


def test_artifact_validator_enforces_analysis_spec_projections():
    data = _valid_artifact()
    data["analysis_spec"]["population"]["start_age"] = 60

    with pytest.raises(ValueError, match="population must match"):
        validate_results_artifact(data)


def test_artifact_validator_rejects_invalid_provenance_hash():
    data = _valid_artifact()
    data["methodology_provenance"]["analysis_fingerprint_sha256"] = "not-a-hash"

    with pytest.raises(ValueError, match="64-character"):
        validate_results_artifact(data)


def test_artifact_validator_requires_structural_exclusions_to_be_zero():
    data = _valid_artifact()
    excluded = data["evidence_registry"]["structurally_excluded_coefficients"]
    excluded[0]["sd"] = 0.01

    with pytest.raises(ValueError, match="fixed at zero"):
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


@pytest.mark.parametrize("start_age", [29, 71])
def test_artifact_validator_enforces_supported_adult_start_age(start_age):
    data = _valid_artifact()
    data["start_age"] = start_age
    data["constants"]["target_age"] = start_age

    with pytest.raises(ValueError, match="supported adult model domain"):
        validate_results_artifact(data)


def test_artifact_validator_rejects_qalys_above_life_years():
    data = _valid_artifact()
    data["baseline_qalys_undiscounted"] = data["baseline_life_years"] + 1

    with pytest.raises(ValueError, match="QALYs cannot exceed"):
        validate_results_artifact(data)


def test_artifact_validator_enforces_qaly_upside_downside_identity():
    data = _valid_artifact()
    data["nuts"]["walnut"]["expected_upside"] += 0.001

    with pytest.raises(ValueError, match=r"expected_upside \+ expected_downside"):
        validate_results_artifact(data)


def test_artifact_validator_enforces_complementary_effect_probabilities():
    data = _valid_artifact()
    data["nuts"]["walnut"]["p_negative"] = 0.05

    with pytest.raises(ValueError, match="complementary positive and negative"):
        validate_results_artifact(data)


def test_artifact_validator_allows_effect_probability_rounding_error():
    data = _valid_artifact()
    data["nuts"]["cashew"]["p_positive"] += 0.0001

    validate_results_artifact(data)


def test_artifact_validator_enforces_per_nut_pathway_total():
    data = _valid_artifact()
    data["nuts"]["walnut"]["cvd_contribution"] += 0.001

    with pytest.raises(ValueError, match="pathway contributions"):
        validate_results_artifact(data)


def test_artifact_validator_allows_pathway_rounding_error():
    data = _valid_artifact()
    data["nuts"]["walnut"]["cvd_contribution"] += 0.000001

    validate_results_artifact(data)


def test_artifact_validator_allows_signed_pathway_attribution_shares():
    data = _valid_artifact()
    walnut = data["nuts"]["walnut"]
    walnut["cvd_contribution"] = 1.2
    walnut["cancer_contribution"] = -0.1
    walnut["other_contribution"] = -0.1
    data["cvd_contribution_mean"] = 1.1
    data["cancer_contribution_mean"] = -0.05
    data["other_contribution_mean"] = -0.05

    validate_results_artifact(data)


def test_artifact_validator_enforces_expected_nmb_identity():
    data = _valid_artifact()
    data["nuts"]["walnut"]["expected_net_monetary_benefit"] += 1

    with pytest.raises(
        ValueError,
        match=r"willingness_to_pay \* qaly_mean - lifetime_cost_mean",
    ):
        validate_results_artifact(data)


def test_artifact_validator_enforces_detailed_expected_nmb_identity():
    data = _valid_artifact()
    evaluation = data["decision_summary"]["all_option_evaluation"]
    evaluation["expected_nmb"]["walnut"] += 1

    with pytest.raises(
        ValueError,
        match=r"willingness_to_pay \* qaly_mean - lifetime_cost_mean",
    ):
        validate_results_artifact(data)


def test_artifact_validator_enforces_zero_comparator_nmb():
    data = _valid_artifact()
    summary = data["decision_summary"]
    summary["comparator_expected_net_monetary_benefit"] = 1
    summary["all_option_evaluation"]["expected_nmb"]["no_modeled_nut_intervention"] = 1

    with pytest.raises(ValueError, match="zero-cost, zero-effect comparator"):
        validate_results_artifact(data)


def test_artifact_validator_enforces_expected_icer_ratio():
    data = _valid_artifact()
    data["nuts"]["walnut"]["icer_expected"] += 1

    with pytest.raises(ValueError, match="lifetime_cost_mean / qaly_mean"):
        validate_results_artifact(data)


def test_artifact_validator_requires_icer_for_positive_expected_qalys():
    data = _valid_artifact()
    data["nuts"]["walnut"]["icer_expected"] = None

    with pytest.raises(ValueError, match="must be defined"):
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
