"""Every evidence row the model reads exists and has a verified citation, and
structural constants agree with the rows they come from."""

from __future__ import annotations

import yaml

from tests.helpers import ROOT, fresh_run
from whatnut import data
from whatnut.model import ASSUMPTIONS, DRAW_COLUMNS, EVIDENCE_IDS

ROWS = {
    r["id"]: r for r in yaml.safe_load((ROOT / "data" / "evidence.yaml").read_text())
}
# rows whose estimate enters a calculation (the rest are citations for reference data)
EFFECT_IDS = {EVIDENCE_IDS[role] for role in (*DRAW_COLUMNS, "ala_background")}


def ids_read_by_model() -> set[str]:
    return set(EVIDENCE_IDS.values()) | {ASSUMPTIONS["peanut_ldl_serving_row"]}


def test_model_rows_exist_and_citations_verified():
    for rid in sorted(ids_read_by_model()):
        assert rid in ROWS, f"{rid} is not in data/evidence.yaml"
        row, v = ROWS[rid], ROWS[rid]["verified"]
        if row["source"].get("doi"):
            assert v["title_matches"] is True, rid
            assert v["doi_resolves"] is True, rid
            assert v["first_author_matches"] is True, rid
        else:
            # no DOI (DESIGN decision 10): Crossref cannot match a title, so the
            # row must carry a URL and say where the value was checked
            assert row["source"].get("url"), rid
            assert v["title_matches"] is None and v["value_checked_in"], rid
        if rid in EFFECT_IDS:
            assert row["estimate"] is not None, rid


def test_rows_recorded_in_results_are_the_rows_read():
    res, _ = fresh_run("a")
    assert set(res["meta"]["evidence_rows"]) == ids_read_by_model()
    for rid, rec in res["meta"]["evidence_rows"].items():
        assert rec["estimate"] == ROWS[rid]["estimate"]


def test_structural_constants_match_their_rows():
    ala = ROWS[EVIDENCE_IDS["ala"]]
    lo, hi = ASSUMPTIONS["ala_support_g"]
    assert f"from {lo} to {hi} g/day" in ala["support"]
    aune = ROWS[EVIDENCE_IDS["rr28_all"]]
    assert f"above {ASSUMPTIONS['plateau_dose_g']}-20 g/day" in aune["support"]
    assert (
        ASSUMPTIONS["reference"]["delta"]
        == data.row(EVIDENCE_IDS["rr28_all"]).per_grams()
    )


def test_data_files_recorded_with_current_hashes():
    res, _ = fresh_run("a")
    files = res["meta"]["data_files"]
    for rel in (
        "data/evidence.yaml",
        "data/life_tables/male.csv",
        "data/causes/cause_shares.csv",
    ):
        assert rel in files
    for rel, digest in files.items():
        assert data.sha256(ROOT / rel) == digest, rel


def test_fadnes_targets_agree_with_evidence_rows():
    t = data.fadnes_targets()
    for sex in ("female", "male"):
        row = ROWS[EVIDENCE_IDS[f"fadnes_{sex}"]]
        main = t["main_target"][sex]
        assert (row["estimate"], row["ci_low"], row["ci_high"]) == (
            main["years"],
            main["ui95_low"],
            main["ui95_high"],
        )
    res, _ = fresh_run("a")
    heads = [r for r in res["fadnes"]["rows"] if r["start_age"] == 20]
    assert {r["target_source"] for r in heads} == {
        EVIDENCE_IDS["fadnes_female"],
        EVIDENCE_IDS["fadnes_male"],
    }
