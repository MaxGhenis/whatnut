"""The committed results/results.json and the accessor the paper reads it through."""

from __future__ import annotations

import json

import pytest

from tests.helpers import ROOT, fresh_run
from whatnut import data
from whatnut.results import Results, ResultsError, r

COMMITTED = ROOT / "results" / "results.json"


def _leaf_diffs(a, b, path="") -> list[str]:
    """Paths where two parsed JSON trees differ, for a readable failure."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = [f"{path}.{k}: only one side" for k in sorted(set(a) ^ set(b))]
        for k in sorted(set(a) & set(b)):
            out += _leaf_diffs(a[k], b[k], f"{path}.{k}")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [
            d
            for i, (x, y) in enumerate(zip(a, b))
            for d in _leaf_diffs(x, y, f"{path}[{i}]")
        ]
    return [] if a == b else [f"{path}: committed {a!r}, fresh {b!r}"]


def test_committed_results_regenerate_byte_identically():
    """A fresh pipeline run reproduces results/results.json byte for byte (the
    figures are not compared: PNG bytes depend on matplotlib and the CPU)."""
    _, out = fresh_run("a")
    fresh = (out / "results.json").read_bytes()
    committed = COMMITTED.read_bytes()
    if fresh != committed:
        diffs = _leaf_diffs(json.loads(committed), json.loads(fresh))
        pytest.fail(
            f"results.json differs from a fresh run in {len(diffs)} places "
            "(rerun python -m whatnut.pipeline if the change is intended):\n  "
            + "\n  ".join(diffs[:10] or ["formatting only"])
        )


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
    v = r.le_gain("male", 40, 15, 0, "calibrated", "mean")
    assert isinstance(v, float) and v > 0
    assert r.le_gain("male", 40, 15.0, 0.0, "calibrated") == v
    assert r.le_gain_days("male", 40, 15, 0, "calibrated") == v * 365.25
    for member in (
        "ldl_chd",
        "ldl_all",
        "calibrated",
        "calibrated_mortality",
        "calibrated_protective",
        "calibrated_analog",
        "calibrated_diet",
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
    obj["reference"]["scenarios"]["male"]["calibrated"]["mean"] *= 1.01
    bad = tmp_path / "results.json"
    bad.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ResultsError, match="reference.scenarios.male.calibrated.mean"):
        Results(bad).verify()


def test_verify_catches_headline_drift(tmp_path):
    obj = json.loads(COMMITTED.read_text(encoding="utf-8"))
    obj["grid"]["female"]["40"]["15"]["0"]["calibrated"]["mean"] += 0.001
    obj["reference"]["scenarios"]["female"]["calibrated"]["mean"] += 0.001
    bad = tmp_path / "results.json"
    bad.write_text(json.dumps(obj), encoding="utf-8")
    with pytest.raises(ResultsError, match="headline_days.female_calibrated"):
        Results(bad).verify()


def test_missing_file_message(tmp_path):
    with pytest.raises(ResultsError, match="whatnut.pipeline"):
        Results(tmp_path / "nope.json").meta
