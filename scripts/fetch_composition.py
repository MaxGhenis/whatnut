"""Fetch nut and seed composition from USDA FoodData Central and parse it.

Downloads the FoodData Central portal JSON for each food listed in FOODS
(https://fdc.nal.usda.gov/portal-data/external/<fdc_id>), stores the raw
bytes under data/composition/raw/, records url, sha256 and fetched_at in
data/composition/MANIFEST.json, and writes:

  data/composition/composition.csv       one row per food, per 100 g edible portion
  data/composition/composition_long.csv  every nutrient row of every food (audit trail)
  data/composition/gram_weights.csv      every foodMeasure (household measure -> grams)

Rerun:
  .venv/bin/python scripts/fetch_composition.py            (refetch everything)
  .venv/bin/python scripts/fetch_composition.py --offline  (reparse cached raw files)

Nutrient choices (USDA nutrient numbers):
  energy_kcal 208; fat_g 204; sfa_g 606; mufa_g 645; pufa_g 646; fiber_g 291;
  protein_g 203; magnesium_mg 304; vitamin_e_mg 323 (alpha-tocopherol);
  selenium_ug 317.
  ala_g: 851 (18:3 n-3 c,c,c, i.e. alpha-linolenic acid) when the record has it,
         otherwise 619 (PUFA 18:3, all isomers). ala_basis says which.
  la_g:  675 (18:2 n-6 c,c, i.e. linoleic acid) when the record has it,
         otherwise 618 (PUFA 18:2, all isomers). la_basis says which.
  fa_18_3_total_g / fa_18_3_n3_ccc_g / fa_18_2_total_g / fa_18_2_n6_cc_g carry the raw
  619 / 851 / 618 / 675 values (blank when the record lacks them).
A value missing from the record is left blank (never imputed).

MANIFEST.json also records sha256 for the derived CSVs, column definitions, and a
cross-check against the FDC API copies cached on origin/master
(src/whatnut/data/raw/usda_fdc/<id>.json, different JSON format): every nutrient
value is compared by nutrient number.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "composition"
RAW = OUT / "raw"
MANIFEST = OUT / "MANIFEST.json"
URL = "https://fdc.nal.usda.gov/portal-data/external/{fdc_id}"

# key -> (fdc_id, role). role "composition" rows go to composition.csv;
# "gram_weights" rows (FNDDS survey food) contribute gram weights only.
FOODS: dict[str, tuple[int, str]] = {
    "walnut": (170187, "composition"),
    "almond": (170567, "composition"),
    "almond_blanched": (170568, "composition"),
    "pistachio": (170184, "composition"),
    "pecan": (170182, "composition"),
    "macadamia": (170178, "composition"),
    "hazelnut": (170581, "composition"),
    "cashew": (170162, "composition"),
    "peanut": (172430, "composition"),
    "brazil_nut": (170569, "composition"),
    "flaxseed": (169414, "composition"),
    "chia": (170554, "composition"),
    "chia_fndds": (2707590, "gram_weights"),
}

SIMPLE = {
    "energy_kcal": ("208",),
    "fat_g": ("204",),
    "sfa_g": ("606",),
    "mufa_g": ("645",),
    "pufa_g": ("646",),
    "fiber_g": ("291",),
    "protein_g": ("203",),
    "magnesium_mg": ("304",),
    "vitamin_e_mg": ("323",),
    "selenium_ug": ("317",),
}
EXPECTED_UNITS = {
    "208": "kcal",
    "204": "g",
    "606": "g",
    "645": "g",
    "646": "g",
    "291": "g",
    "203": "g",
    "304": "mg",
    "323": "mg",
    "317": "µg",
    "851": "g",
    "619": "g",
    "675": "g",
    "618": "g",
}
# preferred, fallback
ALA = (
    ("851", "18:3 n-3 c,c,c (ALA), nutrient 851"),
    ("619", "18:3 undifferentiated (all isomers), nutrient 619"),
)
LA = (
    ("675", "18:2 n-6 c,c (LA), nutrient 675"),
    ("618", "18:2 undifferentiated (all isomers), nutrient 618"),
)

COLUMNS = [
    "key",
    "fdc_id",
    "description",
    "food_class",
    "ndb_number",
    "energy_kcal",
    "fat_g",
    "sfa_g",
    "mufa_g",
    "pufa_g",
    "ala_g",
    "ala_basis",
    "la_g",
    "la_basis",
    "fiber_g",
    "protein_g",
    "magnesium_mg",
    "vitamin_e_mg",
    "selenium_ug",
    "fa_18_3_total_g",
    "fa_18_3_n3_ccc_g",
    "fa_18_2_total_g",
    "fa_18_2_n6_cc_g",
    "source_url",
    "raw_sha256",
]
# Raw fatty-acid fields reported side by side so the ala/la basis choice is auditable.
RAW_FA = {
    "fa_18_3_total_g": "619",
    "fa_18_3_n3_ccc_g": "851",
    "fa_18_2_total_g": "618",
    "fa_18_2_n6_cc_g": "675",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch(fdc_id: int) -> bytes:
    url = URL.format(fdc_id=fdc_id)
    for attempt in range(4):
        r = requests.get(url, timeout=60, headers={"Accept": "application/json"})
        if r.status_code == 200:
            json.loads(r.content)  # must parse
            return r.content
        time.sleep(2**attempt)
    raise RuntimeError(f"{url}: HTTP {r.status_code}")


def nutrient_table(food: dict) -> dict[str, dict]:
    """number -> {name, unit, value, derivation, data_points}. Skips header rows with
    no value."""
    out: dict[str, dict] = {}
    for fn in food.get("foodNutrients", []):
        n = fn.get("nutrient") or {}
        number = n.get("number")
        value = fn.get("value", fn.get("amount"))
        if number is None or value is None:
            continue
        unit = (n.get("nutrientUnit") or {}).get("name") or n.get("unitName")
        deriv = fn.get("foodNutrientDerivation") or {}
        out[str(number)] = {
            "number": str(number),
            "name": n.get("name"),
            "unit": unit,
            "value": float(value),
            "derivation_code": deriv.get("code"),
            "derivation": deriv.get("description"),
            "data_points": fn.get("dataPoints"),
        }
    return out


def pick(table: dict, options) -> tuple[float | None, str | None]:
    for number, label in options:
        if number in table:
            return table[number]["value"], label
    return None, None


def measures(food: dict) -> list[dict]:
    rows = []
    for m in food.get("foodMeasures") or food.get("foodPortions") or []:
        unit = (m.get("measureUnit") or {}).get("name")
        desc = m.get("disseminationText") or " ".join(
            str(x) for x in (m.get("value"), m.get("modifier")) if x not in (None, "")
        )
        rows.append(
            {
                "measure_id": m.get("id"),
                "rank": m.get("rank"),
                "description": desc,
                "amount": m.get("value"),
                "modifier": m.get("modifier"),
                "measure_unit": unit,
                "grams": m.get("gramWeight"),
                "data_points": m.get("dataPoints"),
            }
        )
    rows.sort(
        key=lambda r: (
            r["rank"] if r["rank"] is not None else 999,
            r["measure_id"] or 0,
        )
    )
    return rows


COLUMN_DOCS = {
    "composition.csv": {
        "basis": (
            "per 100 g edible portion, as reported by FoodData Central (SR Legacy)"
        ),
        "key": "food key used across the repo",
        "fdc_id": "FoodData Central id; ndb_number is the SR Legacy NDB number",
        "energy_kcal": "nutrient 208 Energy (kcal)",
        "fat_g": "204 Total lipid (fat)",
        "sfa_g": "606 total saturated fatty acids",
        "mufa_g": "645 total monounsaturated",
        "pufa_g": "646 total polyunsaturated",
        "ala_g": (
            "851 PUFA 18:3 n-3 c,c,c (alpha-linolenic acid) if the record has it, else "
            "619 PUFA 18:3 "
            "(all isomers); ala_basis names which"
        ),
        "la_g": (
            "675 PUFA 18:2 n-6 c,c (linoleic acid) if present, else 618 PUFA 18:2 (all "
            "isomers); la_basis names which"
        ),
        "fiber_g": "291 Fiber, total dietary",
        "protein_g": "203 Protein",
        "magnesium_mg": "304 Magnesium",
        "vitamin_e_mg": "323 Vitamin E (alpha-tocopherol)",
        "selenium_ug": "317 Selenium (micrograms)",
        "fa_18_3_total_g/fa_18_3_n3_ccc_g/fa_18_2_total_g/fa_18_2_n6_cc_g": (
            "raw 619/851/618/675 values; blank when absent"
        ),
        "source_url/raw_sha256": "the FDC JSON the row was parsed from",
    },
    "composition_long.csv": (
        "every nutrient row of every record: number, name, unit, value, derivation "
        "code and "
        "description, data points (audit trail)"
    ),
    "gram_weights.csv": (
        "every foodMeasure: description is FDC's text (or amount + modifier), grams is "
        "gramWeight. "
        "For chia_fndds (FNDDS survey food) the modifier column holds the FNDDS "
        "portion code, "
        "not a description."
    ),
}


def origin_master_check(files: dict) -> dict:
    """Compare each fetched record with the FDC API copy cached on origin/master, if
    git has it."""
    out = {
        "source": (
            "git show origin/master:src/whatnut/data/raw/usda_fdc/<fdc_id>.json (FDC "
            "API format)"
        ),
        "records": {},
    }
    for rel, meta in sorted(files.items()):
        fdc_id = meta["fdc_id"]
        try:
            old = subprocess.run(
                [
                    "git",
                    "-C",
                    str(ROOT),
                    "show",
                    f"origin/master:src/whatnut/data/raw/usda_fdc/{fdc_id}.json",
                ],
                capture_output=True,
                check=True,
            ).stdout
        except (subprocess.CalledProcessError, FileNotFoundError):
            out["records"][str(fdc_id)] = "not cached on origin/master"
            continue
        new_t = {
            k: v["value"]
            for k, v in nutrient_table(json.loads((OUT / rel).read_bytes())).items()
        }
        old_t = {}
        for fn in json.loads(old).get("foodNutrients", []):
            n = fn.get("nutrient") or {}
            num, val = (
                n.get("number") or fn.get("nutrientNumber"),
                fn.get("amount", fn.get("value")),
            )
            if num is not None and val is not None:
                old_t[str(num)] = float(val)
        diffs = sorted(
            k for k in set(old_t) & set(new_t) if abs(old_t[k] - new_t[k]) > 1e-9
        )
        out["records"][str(fdc_id)] = {
            "old_sha256": sha256(old),
            "new_sha256": meta["sha256"],
            "nutrients_compared": len(set(old_t) & set(new_t)),
            "value_differences": diffs,
            "only_in_old": sorted(set(old_t) - set(new_t)),
            "only_in_new": sorted(set(new_t) - set(old_t)),
        }
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--offline",
        action="store_true",
        help="reparse cached raw files; verify sha256 against MANIFEST",
    )
    args = ap.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
    files = manifest.setdefault("files", {})

    comp_rows, long_rows, gw_rows = [], [], []
    for key, (fdc_id, role) in FOODS.items():
        rel = f"raw/fdc_{fdc_id}.json"
        path = OUT / rel
        url = URL.format(fdc_id=fdc_id)
        if args.offline:
            data = path.read_bytes()
            if files.get(rel, {}).get("sha256") != sha256(data):
                raise SystemExit(f"sha256 mismatch for {rel}")
        else:
            data = fetch(fdc_id)
            path.write_bytes(data)
            files[rel] = {
                "url": url,
                "sha256": sha256(data),
                "bytes": len(data),
                "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "food_key": key,
                "fdc_id": fdc_id,
            }
            time.sleep(0.5)
        food = json.loads(data)
        if (
            int(food.get("fdcId", food.get("id"))) != fdc_id
            and int(food.get("id", -1)) != fdc_id
        ):
            raise SystemExit(f"{rel}: record id does not match {fdc_id}")
        table = nutrient_table(food)
        desc = food.get("description")
        food_class = food.get("foodClass")

        for num, unit in EXPECTED_UNITS.items():
            if num in table and table[num]["unit"] != unit:
                raise SystemExit(
                    f"{key}: nutrient {num} unit {table[num]['unit']!r}, expected "
                    f"{unit!r}"
                )

        for t in sorted(table.values(), key=lambda t: t["number"]):
            long_rows.append({"key": key, "fdc_id": fdc_id, **t})
        for m in measures(food):
            gw_rows.append(
                {"key": key, "fdc_id": fdc_id, "food_description": desc, **m}
            )

        if role != "composition":
            continue
        row = {
            "key": key,
            "fdc_id": fdc_id,
            "description": desc,
            "food_class": food_class,
            "ndb_number": food.get("ndbNumber"),
            "source_url": url,
            "raw_sha256": sha256(data),
        }
        for col, (num,) in SIMPLE.items():
            row[col] = table[num]["value"] if num in table else None
        row["ala_g"], row["ala_basis"] = pick(table, ALA)
        row["la_g"], row["la_basis"] = pick(table, LA)
        for col, num in RAW_FA.items():
            row[col] = table[num]["value"] if num in table else None
        comp_rows.append(row)

    with open(OUT / "composition.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(comp_rows)
    long_cols = [
        "key",
        "fdc_id",
        "number",
        "name",
        "unit",
        "value",
        "derivation_code",
        "derivation",
        "data_points",
    ]
    with open(OUT / "composition_long.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=long_cols, lineterminator="\n")
        w.writeheader()
        w.writerows(long_rows)
    gw_cols = [
        "key",
        "fdc_id",
        "food_description",
        "measure_id",
        "rank",
        "description",
        "amount",
        "modifier",
        "measure_unit",
        "grams",
        "data_points",
    ]
    with open(OUT / "gram_weights.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=gw_cols, lineterminator="\n")
        w.writeheader()
        w.writerows(gw_rows)

    manifest["source"] = (
        "USDA FoodData Central portal JSON (SR Legacy foods; FNDDS survey food 2707590 "
        "for chia gram weights)"
    )
    manifest["script"] = "scripts/fetch_composition.py"
    manifest["derived"] = {
        name: {
            "sha256": sha256((OUT / name).read_bytes()),
            "bytes": (OUT / name).stat().st_size,
            "derived_from": sorted(files),
            "generated_by": "scripts/fetch_composition.py",
        }
        for name in ("composition.csv", "composition_long.csv", "gram_weights.csv")
    }
    manifest["columns"] = COLUMN_DOCS
    manifest["cross_checks"] = {"origin_master_usda_fdc": origin_master_check(files)}
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    print(
        f"composition.csv: {len(comp_rows)} foods; composition_long.csv: "
        f"{len(long_rows)} rows; "
        f"gram_weights.csv: {len(gw_rows)} measures"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
