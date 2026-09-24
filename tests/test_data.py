"""Data loaders verify every file against its manifest."""

from __future__ import annotations

import pytest

from whatnut import data


def test_loaders_check_manifest_hashes():
    data.READS.clear()
    data.life_table("male")
    data.cause_shares("female")
    assert set(data.READS) >= {
        "data/life_tables/male.csv",
        "data/causes/cause_shares.csv",
    }


def test_hash_mismatch_raises(monkeypatch):
    monkeypatch.setattr(data, "sha256", lambda path: "0" * 64)
    with pytest.raises(data.DataIntegrityError, match="does not match the manifest"):
        data.life_table("female")


def test_manifest_check_on_a_synthetic_tree(tmp_path, monkeypatch):
    import hashlib
    import json

    monkeypatch.setattr(data, "ROOT", tmp_path)
    monkeypatch.setattr(data, "DATA", tmp_path / "data")
    monkeypatch.setattr(data, "EVIDENCE", tmp_path / "data" / "evidence.yaml")
    folder = tmp_path / "data" / "things"
    folder.mkdir(parents=True)
    good, stray = folder / "good.csv", folder / "stray.csv"
    good.write_text("a,b\n1,2\n")
    stray.write_text("a,b\n")
    digest = hashlib.sha256(good.read_bytes()).hexdigest()
    (folder / "MANIFEST.json").write_text(
        json.dumps({"files": {"good.csv": {"sha256": digest}}})
    )
    assert data.checked_path(good) == good.resolve()
    assert data.READS["data/things/good.csv"] == digest
    with pytest.raises(data.DataIntegrityError, match="not listed"):
        data.checked_path(stray)
    good.write_text("a,b\n1,3\n")
    with pytest.raises(data.DataIntegrityError, match="does not match"):
        data.checked_path(good)


def test_life_table_shape():
    for sex in data.SEXES:
        lt = data.life_table(sex)
        assert lt.age == tuple(range(lt.omega + 1))
        assert lt.qx[-1] == 1
        assert all(0 <= q < 1 for q in lt.qx[:-1])


def test_cause_shares_consistent():
    for sex in data.SEXES:
        cs = data.cause_shares(sex)
        assert all(0 < chd < cvd < 1 for chd, cvd in zip(cs.chd, cs.cvd))
        assert list(cs.start) == sorted(cs.start)
        # ages below the first group take the first group's share
        assert cs.at_ages([0, cs.start[0], 200], "cvd") == [
            cs.cvd[0],
            cs.cvd[0],
            cs.cvd[-1],
        ]


def test_evidence_row_helpers():
    row = data.row("aune2016_allcause_per28g")
    assert row.per_grams() == 28
    assert data.row("delgobbo2015_ldl_per28g").per_grams() == 28.4
    with pytest.raises(data.DataIntegrityError):
        data.row("no_such_row")
    assert "aune2016_allcause_per28g" in data.ROWS_USED
