"""The committed results/results.json and the accessor the paper reads it through."""

from __future__ import annotations

import json

import pytest

from tests.helpers import ROOT
from whatnut import data
from whatnut.results import Results, ResultsError, r

COMMITTED = ROOT / "results" / "results.json"


def test_committed_results_verify():
    r.verify()
    assert r.meta["n"] >= 10_000
    assert isinstance(r.meta["seed"], int)


def test_committed_results_are_current_with_data():
    """Every data file results.json was computed from still has the same bytes;
    otherwise rerun python -m whatnut.pipeline."""
    stale = [
        rel
        for rel, digest in r.meta["data_files"].items()
        if not (ROOT / rel).exists() or data.sha256(ROOT / rel) != digest
    ]
    assert not stale, f"results.json is stale for {stale}"


def test_le_gain_interface():
    v = r.le_gain("male", 40, 28, 0, "calibrated", "mean")
    assert isinstance(v, float) and v > 0
    assert r.le_gain("male", 40, 28.0, 0.0, "calibrated") == v
    assert r.le_gain_days("male", 40, 28, 0, "calibrated") == v * 365.25
    for member in (
        "floor_low",
        "floor_high",
        "calibrated",
        "calibrated_all_cause",
        "face_value",
        "cvd_only",
        "c_0.1",
        "c_0.33",
        "c_1",
    ):
        for stat in ("mean", "p10", "p90", "p2_5", "p97_5"):
            assert isinstance(r.le_gain("female", 30, 5, 10, member, stat), float)
    with pytest.raises(ResultsError):
        r.le_gain("male", 45, 28, 0, "calibrated", "mean")
    with pytest.raises(ResultsError):
        r.le_gain("male", 40, 28, 0, "no_such_member", "mean")


def test_verify_catches_tampering(tmp_path):
    obj = json.loads(COMMITTED.read_text(encoding="utf-8"))
    obj["reference"]["bracket"]["male"]["calibrated"]["mean"] *= 1.01
    bad = tmp_path / "results.json"
    bad.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ResultsError, match="reference.bracket.male.calibrated.mean"):
        Results(bad).verify()


def test_verify_catches_headline_drift(tmp_path):
    obj = json.loads(COMMITTED.read_text(encoding="utf-8"))
    obj["grid"]["female"]["40"]["28"]["0"]["calibrated"]["mean"] += 0.001
    obj["reference"]["bracket"]["female"]["calibrated"]["mean"] += 0.001
    bad = tmp_path / "results.json"
    bad.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ResultsError, match="headline_days.female_calibrated"):
        Results(bad).verify()


def test_missing_file_message(tmp_path):
    with pytest.raises(ResultsError, match="whatnut.pipeline"):
        Results(tmp_path / "nope.json").meta
