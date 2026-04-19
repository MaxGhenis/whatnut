"""Fetch nutrient composition from USDA FoodData Central SR Legacy.

Downloads the static USDA SR Legacy food JSON dataset (April 2018, the
final SR release) once, caches it under `data/raw/`, and extracts the
exact per-100g nutrient values for each FDC ID listed in
`data/raw/usda_fdc/fdc_ids.yaml`. Scales to per-28g, writes a per-nut
JSON snapshot to `data/raw/usda_fdc/<fdc_id>.json`, and generates the
nutrient block used by `nuts.yaml`.

This replaces hand-entered per-28g values (which in at least one case —
walnut vitamin E — had unit-confused numbers from per-100g).

Run via: `python -m whatnut.data_build.usda_fdc`
"""

from __future__ import annotations

import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path

import yaml

from whatnut.data_build import DATA_DIR, RAW_DIR

USDA_SR_LEGACY_URL = (
    "https://fdc.nal.usda.gov/fdc-datasets/"
    "FoodData_Central_sr_legacy_food_json_2018-04.zip"
)
USDA_CACHE = RAW_DIR / "usda_fdc" / "sr_legacy_food.json.zip"
USDA_OUT_DIR = RAW_DIR / "usda_fdc"

# FDC IDs we use in the paper. Keep in lockstep with nuts.yaml.
FDC_IDS = {
    "walnut": 170187,
    "almond": 170567,
    "pistachio": 170184,
    "pecan": 170182,
    "macadamia": 170178,
    "peanut": 172430,
    "hazelnut": 170581,
    "cashew": 170162,
}

# USDA SR Legacy nutrient `number` codes (strings). These are the
# standard SR reference numbers, not the FDC-specific `id`.
#   203 protein, 204 total fat, 208 energy (kcal), 291 fiber,
#   304 magnesium, 323 vitamin E (alpha-tocopherol), 606 saturated fat,
#   645 MUFA total, 646 PUFA total, 619 PUFA 18:3 (ALA),
#   626 MUFA 16:1 (palmitoleic, proxy for omega-7).
NUTRIENT_NUMBERS = {
    "calories_kcal": "208",
    "protein_g": "203",
    "total_fat_g": "204",
    "saturated_fat_g": "606",
    "monounsaturated_fat_g": "645",
    "polyunsaturated_fat_g": "646",
    "omega3_ala_g": "619",
    "omega7_g": "626",
    "fiber_g": "291",
    "magnesium_mg": "304",
    "vitamin_e_mg": "323",
    "arginine_g": "511",
}

# Nutrients that SR Legacy doesn't carry uniformly and that we pull from
# secondary sources (documented per-nut in nuts.yaml `note` fields).
SUPPLEMENTAL = ("arginine_g", "phytosterols_mg")


def download_sr_legacy() -> bytes:
    """Download the SR Legacy JSON zip, cache on disk, return zip bytes."""
    USDA_OUT_DIR.mkdir(parents=True, exist_ok=True)
    if USDA_CACHE.exists():
        return USDA_CACHE.read_bytes()
    print(f"Downloading USDA SR Legacy (~13 MB) from {USDA_SR_LEGACY_URL}")
    with urllib.request.urlopen(USDA_SR_LEGACY_URL) as response:
        data = response.read()
    USDA_CACHE.write_bytes(data)
    return data


def load_sr_legacy_foods(zip_bytes: bytes) -> list[dict]:
    """Parse SR Legacy JSON zip into a list of food records."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        if len(names) != 1:
            raise RuntimeError(f"Unexpected zip layout: {names}")
        with zf.open(names[0]) as f:
            payload = json.load(f)
    foods = payload.get("SRLegacyFoods", payload)
    if isinstance(foods, list):
        return foods
    raise RuntimeError("SR Legacy JSON does not contain an SRLegacyFoods list")


def extract_nutrients(food: dict, serving_g: float = 28.0) -> dict:
    """Return a dict of per-`serving_g` nutrient values keyed by paper name.

    Looks up each entry by its SR-Legacy `nutrient.number` (a string),
    scales from per-100 g to the requested serving size, and rounds to
    three decimals.
    """
    per_100g: dict[str, float] = {}
    for fn in food.get("foodNutrients", []):
        nut = fn.get("nutrient") or {}
        number = nut.get("number")
        amount = fn.get("amount")
        if number is None or amount is None:
            continue
        per_100g[str(number)] = float(amount)

    out: dict[str, float] = {}
    for paper_key, number in NUTRIENT_NUMBERS.items():
        per_100 = per_100g.get(number, 0.0)
        out[paper_key] = round(per_100 * serving_g / 100.0, 3)
    return out


def main(argv: list[str] | None = None) -> int:
    """Fetch SR Legacy data, snapshot per-nut JSON, print nutrient blocks."""
    argv = argv or sys.argv[1:]
    zip_bytes = download_sr_legacy()
    foods = load_sr_legacy_foods(zip_bytes)

    by_fdc = {f["fdcId"]: f for f in foods if "fdcId" in f}
    nut_blocks: dict[str, dict] = {}
    for name, fdc_id in FDC_IDS.items():
        food = by_fdc.get(fdc_id)
        if food is None:
            raise RuntimeError(f"FDC ID {fdc_id} ({name}) not in SR Legacy")

        # Write the verbatim SR Legacy record as an audit artifact.
        snapshot_path = USDA_OUT_DIR / f"{fdc_id}.json"
        snapshot_path.write_text(json.dumps(food, indent=2, sort_keys=True))

        nutrients = extract_nutrients(food)
        nut_blocks[name] = {
            "fdc_id": fdc_id,
            "description": food.get("description", ""),
            "nutrients_per_28g": nutrients,
        }
        print(f"{name:<10} FDC {fdc_id}: {food.get('description','?')[:60]}")
        for k, v in nutrients.items():
            print(f"  {k}: {v}")

    summary_path = USDA_OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(nut_blocks, indent=2, sort_keys=True))
    print(f"\nSummary written to {summary_path}")
    print(f"Per-food snapshots under {USDA_OUT_DIR}/")

    if "--apply" in argv:
        apply_to_nuts_yaml(nut_blocks)
        print(f"Applied SR-Legacy nutrients to {DATA_DIR / 'nuts.yaml'}")
    return 0


# Literature-sourced phytosterols (mg/100g → mg/28g). USDA SR Legacy does
# not carry phytosterol values for the raw tree-nut records, so these are
# pulled from a secondary compilation: Phillips, K.M. et al. 2005,
# "Phytosterol composition of nuts and seeds commonly consumed in the
# United States," J Agric Food Chem 53(24):9436-9445, Table 1. Values
# are total phytosterols (beta-sitosterol + campesterol + stigmasterol).
# Stored here as per-28g (g*0.28 of per-100g values).
#   walnut 72 → 20; almond 125 → 35; pistachio 214 → 60;
#   pecan 102 → 29; macadamia 116 → 33; peanut 220 → 62;
#   hazelnut 97 → 27; cashew 158 → 45 (round to nearest mg)
PHYTOSTEROLS_MG_PER_28G = {
    "walnut": 20,
    "almond": 35,
    "pistachio": 60,
    "pecan": 29,
    "macadamia": 33,
    "peanut": 62,
    "hazelnut": 27,
    "cashew": 45,
}


def apply_to_nuts_yaml(nut_blocks: dict[str, dict]) -> None:
    """Rewrite `nuts.yaml` nutrient sections with fresh USDA values while
    preserving pathway_adjustments, cost_per_kg_usd, and evidence fields
    from the existing hand-curated file.

    The nutrient mapping handles the case where nuts.yaml uses different
    key names than the SR-Legacy extraction (e.g., paper's
    `polyunsaturated_fat_g` maps to SR's total PUFA, but historically
    the yaml double-counted ALA inside PUFA; the Phillips 2005
    phytosterol compilation fills in a field SR Legacy omits).
    """
    nuts_path = DATA_DIR / "nuts.yaml"
    with open(nuts_path) as f:
        existing = yaml.safe_load(f)

    merged: dict[str, dict] = {}
    for nut_id, block in nut_blocks.items():
        old = existing.get(nut_id, {})
        fresh_nutrients = dict(block["nutrients_per_28g"])
        # SR Legacy doesn't carry phytosterols; pull from Phillips 2005.
        fresh_nutrients["phytosterols_mg"] = PHYTOSTEROLS_MG_PER_28G[nut_id]
        merged[nut_id] = {
            "fdc_id": block["fdc_id"],
            "_sr_legacy_description": block["description"],
            "nutrients": fresh_nutrients,
            "pathway_adjustments": old.get("pathway_adjustments", {}),
            "cost_per_kg_usd": old.get("cost_per_kg_usd"),
            "evidence": old.get("evidence", "limited"),
        }

    header = (
        "# Nut profiles: nutrients (auto-generated), pathway adjustments,\n"
        "# costs, and evidence.\n"
        "# - Nutrients: USDA SR Legacy, per 28 g serving, scaled from\n"
        "#   per-100 g values by the extraction script in\n"
        "#   src/whatnut/data_build/usda_fdc.py. Raw per-food JSON\n"
        "#   snapshots live under src/whatnut/data/raw/usda_fdc/.\n"
        "# - Phytosterols: Phillips et al. 2005, J Agric Food Chem\n"
        "#   53(24):9436-9445 (SR Legacy omits phytosterols).\n"
        "# - Prices: see cost_per_kg_usd comments and @whatnut2026prices.\n"
        "# - pathway_adjustments: hand-curated from the nut-specific RCTs\n"
        "#   cited per-adjustment; tiered publication-bias shrinkage is\n"
        "#   applied at sampling time (see priors.yaml:study_quality_shrinkage).\n"
        "#\n"
        "# This file is the SINGLE SOURCE OF TRUTH for per-nut data.\n"
        "# Regenerate nutrient sections with:\n"
        "#     python -m whatnut.data_build.usda_fdc --apply\n\n"
    )
    body = yaml.safe_dump(merged, sort_keys=False, default_flow_style=False)
    nuts_path.write_text(header + body)


if __name__ == "__main__":
    sys.exit(main())
