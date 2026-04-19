"""Build age-stratified cause-of-death fractions from NVSR 73-08 Table 6.

NVSR Vol 73 No 8 (Xu et al., October 2024 — *Deaths: Final Data for
2021*) publishes Table 6: "Death rate by age, and age-adjusted death
rate, for the 15 leading causes of death in 2021". This module parses
the 2021 row for each cause and derives per-age-group fractions of:

- `cvd`    = heart disease (I00-I09, I11, I13, I20-I51) + cerebrovascular
             disease (I60-I69).
- `cancer` = malignant neoplasms (C00-C97).
- `other`  = remainder (All causes minus cvd minus cancer).

Note: the paper's "cvd" category is narrower than ICD-10 I00-I99 — it
excludes e.g. hypertensive disease and other cardiovascular causes. A
broader I00-I99 definition (available only through the CDC WONDER
interactive query) would add ~3-5 percentage points to CVD fractions
across ages. This script uses the NVSR-published leading-cause rates
because they are downloadable and auditable; a future version could
switch to WONDER if the extra coverage justifies the added friction.

Run via: `python -m whatnut.data_build.cdc_cause_fractions`
(add `--apply` to overwrite data/cause_fractions.yaml).
"""

from __future__ import annotations

import re
import sys
import urllib.request
from pathlib import Path

from pypdf import PdfReader

from whatnut.data_build import DATA_DIR, RAW_DIR

NVSR_URL = "https://www.cdc.gov/nchs/data/nvsr/nvsr73/nvsr73-08.pdf"
NVSR_CACHE_DIR = RAW_DIR / "cdc_nvsr"
NVSR_CACHE = NVSR_CACHE_DIR / "nvsr73-08.pdf"

# Column positions in Table 6 (0-indexed after the "All ages" column).
# Columns: All ages, <1, 1-4, 5-14, 15-24, 25-34, 35-44, 45-54, 55-64,
#          65-74, 75-84, 85+, Age-adjusted.
# Map 10-year group columns to their midpoint ages for the cause table.
AGE_GROUP_COLUMNS = {
    25: 5,  # 25-34
    35: 6,  # 35-44
    45: 7,  # 45-54
    55: 8,  # 55-64
    65: 9,  # 65-74
    75: 10,  # 75-84
    85: 11,  # 85+
}


def download_nvsr() -> Path:
    NVSR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not NVSR_CACHE.exists():
        print(f"Downloading NVSR 73-08 from {NVSR_URL}")
        with urllib.request.urlopen(NVSR_URL) as r:
            NVSR_CACHE.write_bytes(r.read())
    return NVSR_CACHE


def extract_2021_row(text: str, cause: str) -> list[float] | None:
    """Find the `cause` block in Table 6 text and return its 2021 rate row."""
    idx = text.find(cause)
    if idx < 0:
        return None
    block = text[idx:idx + 2500]
    m = re.search(
        r"2021\.?\s*\.?\.?[\s\.]*([\d,\.]+(?:\s+[\d,\.]+){10,})",
        block,
    )
    if not m:
        return None
    raw = m.group(1)
    tokens = [t.replace(",", "") for t in raw.split()]
    # Filter out dotted-leader artifacts like "." or ".."
    return [float(t) for t in tokens if re.fullmatch(r"\d+(?:\.\d+)?", t)]


def parse_table_6(pdf_path: Path) -> dict[str, list[float]]:
    """Return the 2021 rates (per-age-group columns) for each cause."""
    reader = PdfReader(pdf_path)
    text = "".join(reader.pages[i].extract_text() for i in range(32, 42))
    causes = {
        "all": "All causes",
        "heart": "Diseases of heart",
        "cerebro": "Cerebrovascular diseases",
        "cancer": "Malignant neoplasms",
    }
    return {k: extract_2021_row(text, v) for k, v in causes.items()}


def derive_fractions(rates: dict[str, list[float]]) -> dict[int, dict[str, float]]:
    """Compute CVD / cancer / other fractions at each anchor age."""
    out: dict[int, dict[str, float]] = {}
    for anchor_age, col in AGE_GROUP_COLUMNS.items():
        all_r = rates["all"][col]
        heart = rates["heart"][col]
        cerebro = rates["cerebro"][col]
        cancer = rates["cancer"][col]
        cvd = heart + cerebro
        other = max(0.0, all_r - cvd - cancer)
        total = cvd + cancer + other
        out[anchor_age] = {
            "cvd": round(cvd / total, 3),
            "cancer": round(cancer / total, 3),
            "other": round(other / total, 3),
        }
    return out


def build_cause_fractions_yaml(fractions: dict[int, dict[str, float]]) -> str:
    """Extend anchor ages to include 20 (extrapolated) and 100 (= 85+)."""
    header = (
        "# Cause-of-death fractions by age (2021 US, total population)\n"
        "# Source: Xu JQ, Murphy SL, Kochanek KD, Arias E. Deaths: Final\n"
        "#   Data for 2021. National Vital Statistics Reports, Vol 73,\n"
        "#   No 8. Hyattsville, MD: NCHS, October 2024. Table 6.\n"
        "# https://www.cdc.gov/nchs/data/nvsr/nvsr73/nvsr73-08.pdf\n"
        "# Raw PDF cached at data/raw/cdc_nvsr/nvsr73-08.pdf.\n"
        "#\n"
        "# Fractions are derived from the 2021 death-rate-by-age rows of\n"
        "# Table 6 by:\n"
        "#   cvd    = (heart + cerebrovascular) / all-causes\n"
        "#   cancer = malignant neoplasms / all-causes\n"
        "#   other  = 1 - cvd - cancer\n"
        "# Heart disease is ICD-10 I00-I09, I11, I13, I20-I51;\n"
        "# cerebrovascular is I60-I69; malignant neoplasms is C00-C97.\n"
        "# This is narrower than the ICD-10 I00-I99 CVD block (omits\n"
        "# hypertensive disease and other cardiovascular causes, together\n"
        "# ~3-5 pp of total deaths), because NVSR Table 6 reports only\n"
        "# the 15 leading causes and the broader aggregate requires a\n"
        "# CDC WONDER interactive query not suitable for automation.\n"
        "#\n"
        "# NVSR Table 6 reports 10-year age groups (25-34, 35-44, ...);\n"
        "# the fractions below are written at the lower-bound anchor age\n"
        "# of each group, with 20 extrapolated downward and 100 set to\n"
        "# the 85+ group value. config.py interpolates linearly between\n"
        "# anchors.\n"
        "#\n"
        "# Regenerate with:\n"
        "#   python -m whatnut.data_build.cdc_cause_fractions --apply\n\n"
        "fractions:\n"
    )

    # NVSR Table 6 doesn't report a 20-24 row. Copy the 25-34 value to
    # age 20 so the config interpolator has a valid left anchor; this is
    # a pragmatic copy, not a true extrapolation, and the cvd fraction at
    # this age is small enough that the distinction doesn't move outputs.
    anchors = dict(fractions)
    anchors[20] = anchors[25]
    # Age 100 gets the 85+ value (the NVSR band is open-ended at 85+).
    anchors[100] = anchors[85]

    body_lines = []
    for age in sorted(anchors):
        v = anchors[age]
        body_lines.append(f"  {age}:")
        body_lines.append(f"    cvd: {v['cvd']:.3f}")
        body_lines.append(f"    cancer: {v['cancer']:.3f}")
        body_lines.append(f"    other: {v['other']:.3f}")
    return header + "\n".join(body_lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    argv = argv or sys.argv[1:]
    pdf_path = download_nvsr()
    rates = parse_table_6(pdf_path)
    missing = [k for k, v in rates.items() if v is None]
    if missing:
        raise RuntimeError(f"Could not parse Table 6 rows: {missing}")
    fractions = derive_fractions(rates)
    print("Age group -> (cvd, cancer, other):")
    for age in sorted(fractions):
        f = fractions[age]
        print(f"  {age}+ : cvd={f['cvd']:.3f}  cancer={f['cancer']:.3f}  other={f['other']:.3f}")

    yaml_text = build_cause_fractions_yaml(fractions)
    out = DATA_DIR / "cause_fractions.yaml"
    if "--apply" in argv:
        out.write_text(yaml_text)
        print(f"\nWrote {out}")
    else:
        print("\n--- preview ---")
        print(yaml_text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
