"""Tests for content-addressed methodology provenance metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from whatnut import __version__
from whatnut.config import NUT_IDS
from whatnut.model import RNG_ALGORITHM
from whatnut.provenance import (
    CONTENT_HASH_ALGORITHM,
    INPUT_DATA_FILES,
    OPTIQAL_REFERENCE_COMMIT,
    OPTIQAL_REFERENCE_URL,
    OPTIQAL_REPOSITORY_URL,
    PROVENANCE_SCHEMA_VERSION,
    SCIENTIFIC_CODE_FILES,
    WHATNUT_MODEL_VERSION,
    WHATNUT_REPOSITORY_URL,
    methodology_provenance,
)
from whatnut.spec import canonical_analysis_spec

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEX_DIGITS = frozenset("0123456789abcdef")
ANALYSIS_SPEC = canonical_analysis_spec(tuple(NUT_IDS)).to_dict()


def _assert_sha256(value: object) -> str:
    assert isinstance(value, str)
    assert len(value) == 64
    assert set(value) <= HEX_DIGITS
    return value


def test_provenance_is_versioned_pinned_and_explicit():
    provenance = methodology_provenance(ANALYSIS_SPEC)

    assert provenance["provenance_schema_version"] == PROVENANCE_SCHEMA_VERSION
    assert provenance["whatnut_model_version"] == WHATNUT_MODEL_VERSION
    assert __version__ == WHATNUT_MODEL_VERSION
    assert provenance["whatnut_repository_url"] == WHATNUT_REPOSITORY_URL
    assert provenance["optiqal_repository_url"] == OPTIQAL_REPOSITORY_URL
    assert provenance["optiqal_reference_commit"] == OPTIQAL_REFERENCE_COMMIT
    assert provenance["optiqal_reference_url"] == OPTIQAL_REFERENCE_URL
    assert OPTIQAL_REFERENCE_URL == (
        f"{OPTIQAL_REPOSITORY_URL}/commit/{OPTIQAL_REFERENCE_COMMIT}"
    )
    assert len(OPTIQAL_REFERENCE_COMMIT) == 40
    assert set(OPTIQAL_REFERENCE_COMMIT) <= HEX_DIGITS
    assert provenance["rng_algorithm"] == RNG_ALGORITHM
    assert provenance["content_hash_algorithm"] == CONTENT_HASH_ALGORITHM == "sha256"
    assert provenance["runtime_dependency"] is False
    assert provenance["adopted"]
    assert provenance["whatnut_extensions"]
    assert "uncalibrated" in provenance["optiqal_reference_scope"]
    assert provenance["deliberate_differences"]


@pytest.mark.parametrize(
    ("field", "relative_paths"),
    [
        ("scientific_code_sha256", SCIENTIFIC_CODE_FILES),
        ("input_data_sha256", INPUT_DATA_FILES),
    ],
)
def test_content_hashes_match_exact_repository_file_bytes(field, relative_paths):
    hashes = methodology_provenance(ANALYSIS_SPEC)[field]

    assert isinstance(hashes, dict)
    expected_paths = {
        (Path("src/whatnut") / relative_path).as_posix()
        for relative_path in relative_paths
    }
    assert set(hashes) == expected_paths
    assert list(hashes) == sorted(hashes)

    for repository_path, recorded_digest in hashes.items():
        digest = _assert_sha256(recorded_digest)
        assert (
            digest
            == hashlib.sha256((PROJECT_ROOT / repository_path).read_bytes()).hexdigest()
        )


def test_analysis_fingerprint_covers_the_machine_verifiable_boundary():
    provenance = methodology_provenance(ANALYSIS_SPEC)
    boundary = {
        "analysis_spec_sha256": provenance["analysis_spec_sha256"],
        "content_hash_algorithm": provenance["content_hash_algorithm"],
        "input_data_sha256": provenance["input_data_sha256"],
        "optiqal_reference_commit": provenance["optiqal_reference_commit"],
        "provenance_schema_version": provenance["provenance_schema_version"],
        "rng_algorithm": provenance["rng_algorithm"],
        "scientific_code_sha256": provenance["scientific_code_sha256"],
        "whatnut_model_version": provenance["whatnut_model_version"],
    }
    expected = hashlib.sha256(
        json.dumps(
            boundary,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()

    assert _assert_sha256(provenance["analysis_fingerprint_sha256"]) == expected

    expected_spec_hash = hashlib.sha256(
        json.dumps(
            ANALYSIS_SPEC,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    assert provenance["analysis_spec_sha256"] == expected_spec_hash


def test_provenance_is_independent_of_current_working_directory(tmp_path, monkeypatch):
    expected = methodology_provenance(ANALYSIS_SPEC)
    monkeypatch.chdir(tmp_path)

    assert methodology_provenance(ANALYSIS_SPEC) == expected


def test_provenance_calls_return_independent_hash_mappings():
    first = methodology_provenance(ANALYSIS_SPEC)
    second = methodology_provenance(ANALYSIS_SPEC)

    first["scientific_code_sha256"].clear()
    first["input_data_sha256"].clear()

    assert second["scientific_code_sha256"]
    assert second["input_data_sha256"]
