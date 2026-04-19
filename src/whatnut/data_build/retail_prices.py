"""Maintain per-nut retail prices from an auditable CSV.

Prices live in `data/raw/retail_prices/retail_prices.csv`. Each row
records: nut, retailer, product_name, product_url, retrieval_date,
package_size_g, package_price_usd, price_per_kg_usd, note.

This module reads that CSV, validates per-row math (price × 1000 / size
should equal the recorded per-kg price within rounding), derives a
per-nut price (median across rows for a given nut, or the single row if
there is only one), and writes the cost_per_kg_usd field in nuts.yaml.

The CSV is the audit artifact. To refresh prices, update rows in-place
with a new `retrieval_date` and revised values; the previous state is
preserved in git history. The current snapshot reflects specialty-
retail pricing at https://nuts.com (consistent, programmatically
accessible, and dated). Big-box bulk pricing (Costco, Sam's Club) runs
approximately 2-3x lower, so the ICER values in the paper are
conservative upper bounds on what a price-conscious consumer pays; see
the Limitations section for the implied sensitivity.

Run via: `python -m whatnut.data_build.retail_prices`
(add `--apply` to overwrite cost_per_kg_usd in nuts.yaml).
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import yaml

from whatnut.data_build import DATA_DIR, RAW_DIR

PRICES_CSV = RAW_DIR / "retail_prices" / "retail_prices.csv"


def load_prices() -> dict[str, list[dict]]:
    """Read retail_prices.csv into a dict keyed by nut."""
    by_nut: dict[str, list[dict]] = defaultdict(list)
    with open(PRICES_CSV, newline="") as f:
        for row in csv.DictReader(f):
            row["package_size_g"] = float(row["package_size_g"])
            row["package_price_usd"] = float(row["package_price_usd"])
            row["price_per_kg_usd"] = float(row["price_per_kg_usd"])
            by_nut[row["nut"].strip()].append(row)
    return dict(by_nut)


def validate_row(row: dict) -> str | None:
    """Return None if the math checks, else an error string."""
    derived = row["package_price_usd"] * 1000.0 / row["package_size_g"]
    if abs(derived - row["price_per_kg_usd"]) > 0.25:
        return (
            f"{row['nut']} ({row['retailer']}): price_per_kg_usd "
            f"{row['price_per_kg_usd']} disagrees with "
            f"{row['package_price_usd']} × 1000 / {row['package_size_g']} "
            f"= {derived:.2f}"
        )
    return None


def per_nut_price(rows: list[dict]) -> float:
    """Median per-kg price across rows for one nut."""
    return statistics.median(r["price_per_kg_usd"] for r in rows)


def apply_to_nuts_yaml(prices: dict[str, float]) -> None:
    """Rewrite cost_per_kg_usd in nuts.yaml for each nut, preserving
    nutrients/pathway_adjustments/evidence fields."""
    nuts_path = DATA_DIR / "nuts.yaml"
    with open(nuts_path) as f:
        data = yaml.safe_load(f)

    for nut_id, new_price in prices.items():
        if nut_id not in data:
            continue
        data[nut_id]["cost_per_kg_usd"] = round(new_price, 2)

    # Read current header (preserve the USDA-provenance docstring written
    # by the usda_fdc applier).
    header_lines: list[str] = []
    with open(nuts_path) as f:
        for line in f:
            if line.strip().startswith("#") or not line.strip():
                header_lines.append(line)
            else:
                break
    header = "".join(header_lines)
    body = yaml.safe_dump(data, sort_keys=False, default_flow_style=False)
    nuts_path.write_text(header + body)


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    if not PRICES_CSV.exists():
        raise FileNotFoundError(
            f"Retail price CSV not found at {PRICES_CSV}. "
            "Populate it with per-row retailer, URL, size, and price data."
        )
    by_nut = load_prices()

    errors = [e for rows in by_nut.values() for r in rows if (e := validate_row(r))]
    if errors:
        print("Row-math validation errors:")
        for e in errors:
            print(f"  - {e}")
        return 1

    prices = {nut: per_nut_price(rows) for nut, rows in by_nut.items()}
    print("Per-nut median price (USD/kg) from", PRICES_CSV)
    for nut, p in sorted(prices.items()):
        n_rows = len(by_nut[nut])
        print(f"  {nut:<10}  ${p:.2f}/kg  (n={n_rows})")

    if "--apply" in argv:
        apply_to_nuts_yaml(prices)
        print(f"\nApplied to {DATA_DIR / 'nuts.yaml'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
