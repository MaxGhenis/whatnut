"""Deaths by underlying cause, 10-year age group and sex: United States, 2023
(and 2021).

What this builds
----------------
For each edition, <edition dir>/cause_shares.csv holds one row per (sex,
10-year age group) for ages 25-34 through 85+, with the number of US resident
deaths in the data year from
  all causes,
  cardiovascular disease  (CVD)    ICD-10 I00-I99 (underlying cause),
  coronary heart disease  (CHD)    ICD-10 I20-I25,
  stroke                           ICD-10 I60-I69,
  cancer                           ICD-10 C00-C97,
  COVID-19                         ICD-10 U07.1 (extra column, for a sensitivity),
and each cause's share of all-cause deaths in that cell. Sex is female, male
or total (both sexes). <edition dir>/cause_shares_all_groups.csv holds the
same columns for every age group NCHS publishes (under 1 year through 85+,
"age not stated", and all ages), for reference and for checks.

Editions
--------
2023  data/causes/        the baseline (DESIGN.md decision 1; matches the
                          NVSR 74-06 life tables in data/life_tables/)
2021  data/causes/2021/   archived sensitivity (a COVID-19 peak year)

Source
------
The counts are tabulated from the NCHS Multiple Cause-of-Death public use
file for the year (the US file inside mort<year>us.zip). Field positions come
from the NCHS record layout for that year (downloaded alongside; the script
checks that the layout still gives these positions):
  20       resident status (4 = foreign resident; excluded, as NCHS does)
  69       sex (M/F)
  79-80    age recode 12 (05 = 25-34, ..., 11 = 85+, 12 = not stated)
  102-105  data year
  146-149  ICD-10 underlying cause of death

CDC WONDER was not used: its API requires accepting CDC's data-use agreement
on the user's behalf, which this pipeline does not do. The checks below tie
the microdata counts to NCHS's own published totals instead.

Checks (the script exits non-zero if any fails)
-----------------------------------------------
Both editions:
  1. Every record's data year is the edition's year.
  2. The record layout PDF gives the field positions above.
  3. For every ICD-10 code, resident deaths with that underlying cause equal
     the "underlying cause" column of the NCHS Multiple Cause of Death
     Control Total Table 1 for the year (this pins the I00-I99, I20-I25,
     I60-I69 and C00-C97 totals). Codes printed "-" (quantity zero) must be
     absent from the microdata. The 2023 table prints "*" instead of the count
     for small cells ("does not meet NCHS standards of reliability"); for those
     codes the check requires a positive microdata count below the smallest
     count the table prints, and the build log reports how many deaths the
     starred codes hold in each cause group.
2023 (Deaths: Final Data for 2023 was not yet published when this was
written: its DOI, 10.15620/cdc/252471, is registered with a publication date
of 2026-11-12 and the PDF was not online on 2026-09-23):
  4. NVSR 74-10 (Deaths: Leading causes for 2023) Table 1, "All races, all
     origins" panels, both sexes / male / female: all-cause deaths for all
     ages, 1-4, 25-34, 35-44, 45-54, 55-64, 65-74, 75-84, 85+ and 65+, and
     for 5-14 and 15-24 as the sums of the printed 5-9 + 10-14 and 15-19 +
     20-24 panels, equal the microdata; so do malignant neoplasms (C00-C97),
     cerebrovascular diseases (I60-I69), diseases of heart (I00-I09, I11,
     I13, I20-I51) and COVID-19 (U07.1) wherever a panel ranks them among its
     10 leading causes. Each parsed panel must satisfy the table's own
     identity (ranked causes + all other causes = all causes).
  5. NVSR 74-10 Table 2: all-cause infant deaths by sex equal the microdata
     "under 1 year" counts.
2021:
  4. All-cause deaths by age group and sex equal NVSR 73-08 Table 2.
  5. Deaths by age group (both sexes) for all causes, C00-C97, I20-I25,
     I60-I69, I00-I78 and U07.1 equal NVSR 73-08 Table 7.
  6. Deaths by sex (all ages) for all causes, C00-C97, I20-I25, I60-I69,
     I00-I78 and U07.1 equal NVSR 73-08 Table 9.
No NCHS publication gives the I00-I99 or I20-I25 aggregates by age and sex;
those cells come only from the microdata, and the checks above constrain
their margins.

Rerunnable: a raw file on disk whose sha256 matches MANIFEST.json is reused
(fetched_at kept). A complete raw file on disk with no manifest entry (for
example one left by an interrupted run) is adopted after its size matches
the server's Content-Length and, for the zip, its CRC-32 verifies on read. A
partial file is resumed with an HTTP Range request. --refresh re-downloads.

Requires Info-ZIP `unzip` on PATH: the NCHS zips use Deflate64, which
Python's zipfile module cannot decompress. Uses poppler's `pdftotext` when it
is on PATH (pypdf's layout mode otherwise); the checks fail loudly if a table
does not parse.

Usage: .venv/bin/python scripts/fetch_causes.py [--year 2023|2021|all] [--refresh]
       (default --year 2023; --year 2021 rebuilds the archived 2021 outputs,
       which reads the 165 MB 2021 zip)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
import zlib
from collections import Counter
from pathlib import Path

import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "causes"
USER_AGENT = "whatnut-paper data fetcher (https://github.com/MaxGhenis/whatnut)"
MORT_FTP = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/DVS/mortality"
DOC_FTP = (
    "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/DVS/mortality"
)

EDITIONS = {
    2023: {
        "out_dir": BASE_DIR,
        "zip": "raw/mort2023us.zip",
        "layout": "raw/2023-Mortality-Public-Use-File-Documentation.pdf",
        "control": "raw/Multiple-Cause-of-Death-File-Control-Total-Table-2023.pdf",
        "published": ("leading_causes", "raw/nvsr74-10.pdf"),
        "raw_files": {
            "raw/mort2023us.zip": f"{MORT_FTP}/mort2023us.zip",
            "raw/2023-Mortality-Public-Use-File-Documentation.pdf": (
                f"{DOC_FTP}/2023-Mortality-Public-Use-File-Documentation.pdf"
            ),
            "raw/Multiple-Cause-of-Death-File-Control-Total-Table-2023.pdf": (
                f"{DOC_FTP}/Multiple-Cause-of-Death-File-Control-Total-Table-2023.pdf"
            ),
            "raw/nvsr74-10.pdf": (
                "https://www.cdc.gov/nchs/data/nvsr/nvsr74/nvsr74-10.pdf"
            ),
        },
        "sources": {
            "microdata": (
                "National Center for Health Statistics. Mortality Multiple "
                "Cause-of-Death "
                "public use file, 2023 (US file). Hyattsville, MD: NCHS."
            ),
            "record_layout": (
                "NCHS. 2023 Documentation, Mortality Multiple Cause-of-Death Public "
                "Use Record."
            ),
            "control_totals": (
                "NCHS. Multiple Cause of Death Mortality File, Control Total Table 1: "
                "number "
                "of resident deaths by ICD-10 category, United States, 2023 (dated "
                "02JUN26)."
            ),
            "published_check": (
                "Tejada-Vera B, Bastian BA, Curtin SC. Deaths: Leading causes for "
                "2023. "
                "National Vital Statistics Reports; vol 74 no 10. Hyattsville, MD: "
                "National "
                "Center for Health Statistics. 2025. doi:10.15620/cdc/174607. Tables 1 "
                "and 2."
            ),
        },
        "role": "baseline (DESIGN.md decision 1); matches the NVSR 74-06 life tables",
        "notes": (
            "Year 2023 matches the NVSR 74-06 (2023) life tables in data/life_tables/. "
            "Deaths: Final Data for 2023 (NVSR vol 75 no 8, doi:10.15620/cdc/252471) "
            "was "
            "not yet online on 2026-09-23 (CDC Stacks lists a 2026-11-12 publication "
            "date), so the published-total checks use Deaths: Leading Causes for 2023 "
            "(NVSR 74-10) and the 2023 control total table. NCHS also posts 2024 "
            "public-use documentation and control totals. CDC WONDER was not queried: "
            "its API requires accepting CDC's data-use agreement on the user's behalf."
        ),
    },
    2021: {
        "out_dir": BASE_DIR / "2021",
        "zip": "raw/mort2021us.zip",
        "layout": "raw/Multiple-Cause-Record-Layout-2021.pdf",
        "control": "raw/2021-mortality-control-total-table-1.pdf",
        "published": ("final_data", "raw/nvsr73-08.pdf"),
        "raw_files": {
            "raw/mort2021us.zip": f"{MORT_FTP}/mort2021us.zip",
            "raw/Multiple-Cause-Record-Layout-2021.pdf": (
                "https://www.cdc.gov/nchs/data/dvs/"
                "Multiple-Cause-Record-Layout-2021.pdf"
            ),
            "raw/2021-mortality-control-total-table-1.pdf": (
                f"{DOC_FTP}/2021-mortality-control-total-table-1.pdf"
            ),
            "raw/nvsr73-08.pdf": (
                "https://www.cdc.gov/nchs/data/nvsr/nvsr73/nvsr73-08.pdf"
            ),
        },
        "sources": {
            "microdata": (
                "National Center for Health Statistics. Mortality Multiple "
                "Cause-of-Death "
                "public use file, 2021 (US file). Hyattsville, MD: NCHS."
            ),
            "record_layout": (
                "NCHS. 2021 Documentation, Mortality Multiple Cause-of-Death Public "
                "Use Record."
            ),
            "control_totals": (
                "NCHS. Multiple Cause of Death Public Use File, Control Total Table 1: "
                "resident deaths by ICD-10 code, United States, 2021."
            ),
            "published_check": (
                "Murphy SL, Kochanek KD, Xu JQ, Arias E. Deaths: Final data for 2021. "
                "National Vital Statistics Reports; vol 73 no 8. Hyattsville, MD: "
                "National Center for Health Statistics. 2024. Tables 2, 7 and 9."
            ),
        },
        "role": (
            "archived sensitivity; 2021 was a COVID-19 peak year, so the 2023 counts "
            "in "
            "data/causes/ are the baseline"
        ),
        "notes": (
            "Year 2021 matches the NVSR 72-12 (2021) life tables archived in "
            "data/life_tables/2021/. CDC WONDER was not queried: its API requires "
            "accepting CDC's data-use agreement on the user's behalf."
        ),
    },
}

# Age recode 12 (positions 79-80): code -> (label, start, inclusive end or None)
AGE12 = {
    "01": ("Under 1 year", 0, 0),
    "02": ("1-4", 1, 4),
    "03": ("5-14", 5, 14),
    "04": ("15-24", 15, 24),
    "05": ("25-34", 25, 34),
    "06": ("35-44", 35, 44),
    "07": ("45-54", 45, 54),
    "08": ("55-64", 55, 64),
    "09": ("65-74", 65, 74),
    "10": ("75-84", 75, 84),
    "11": ("85+", 85, None),
    "12": ("Age not stated", None, None),
}
MAIN_GROUPS = ["05", "06", "07", "08", "09", "10", "11"]
SEXES = {"F": "female", "M": "male"}

# Positions (1-based, inclusive) the tabulation reads, and the item name the
# record layout must print at each.
LAYOUT_FIELDS = [
    ("20", "1", "Resident Status"),
    ("69", "1", "Sex"),
    ("79-80", "2", "Age Recode 12"),
    ("102-105", "4", "Current Data Year"),
    ("146-149", "4", r"ICD Code \(10th Revision\)"),
]


def in_range(code: str, lo: str, hi: str) -> bool:
    """True when the ICD-10 category (letter + 2 digits) lies in [lo, hi]."""
    cat = code[:3]
    return len(cat) == 3 and cat[0] == lo[0] and cat[1:].isdigit() and lo <= cat <= hi


CAUSES = {
    # key: (label, predicate on the 4-character ICD-10 code)
    "cvd": ("ICD-10 I00-I99", lambda c: in_range(c, "I00", "I99")),
    "chd": ("ICD-10 I20-I25", lambda c: in_range(c, "I20", "I25")),
    "stroke": ("ICD-10 I60-I69", lambda c: in_range(c, "I60", "I69")),
    "cancer": ("ICD-10 C00-C97", lambda c: in_range(c, "C00", "C97")),
    # Not requested by DESIGN.md; kept for a sensitivity on shares of
    # non-COVID deaths (2021 is a pandemic year; 2023 still has COVID deaths).
    "covid": ("ICD-10 U07.1", lambda c: c == "U071"),
}


# Only used for published-table checks; not written to the CSV.
def MAJOR_CVD(c: str) -> bool:
    """NVSR "Major cardiovascular diseases" (I00-I78)."""
    return in_range(c, "I00", "I78")


def HEART(c: str) -> bool:
    """NVSR "Diseases of heart" (I00-I09, I11, I13, I20-I51)."""
    return (
        in_range(c, "I00", "I09")
        or c[:3] in ("I11", "I13")
        or in_range(c, "I20", "I51")
    )


# --------------------------------------------------------------------------
# Download
# --------------------------------------------------------------------------


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def fetch(out_dir: Path, rel: str, url: str, old: dict, refresh: bool) -> dict:
    path = out_dir / rel
    prev = old.get("files", {}).get(rel)
    if not refresh and path.exists() and prev and prev.get("sha256") == sha256(path):
        print(f"  reuse {rel} (sha256 matches manifest)")
        return prev
    path.parent.mkdir(parents=True, exist_ok=True)
    head = requests.head(
        url, headers={"User-Agent": USER_AGENT}, timeout=60, allow_redirects=True
    )
    head.raise_for_status()
    total = (
        int(head.headers["Content-Length"])
        if "Content-Length" in head.headers
        else None
    )
    last_modified = head.headers.get("Last-Modified")
    have = path.stat().st_size if path.exists() and not refresh else 0

    if have and total is not None and have == total:
        print(f"  adopt {rel} (on disk, size matches server's {total:,} bytes)")
        fetched_at = dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
        fetched_at = fetched_at.replace(microsecond=0).isoformat()
    else:
        headers = {"User-Agent": USER_AGENT}
        mode = "wb"
        if (
            have
            and total is not None
            and have < total
            and head.headers.get("Accept-Ranges") == "bytes"
        ):
            headers["Range"] = f"bytes={have}-"
            mode = "ab"
            print(f"  resume {rel} from byte {have:,} of {total:,}")
        with requests.get(url, headers=headers, timeout=600, stream=True) as r:
            r.raise_for_status()
            if mode == "ab" and r.status_code != 206:
                mode = "wb"  # server ignored the Range request
            with path.open(mode) as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        fetched_at = now()
        print(f"  fetched {rel} ({path.stat().st_size:,} bytes)")
    if total is not None and path.stat().st_size != total:
        raise RuntimeError(
            f"{rel}: {path.stat().st_size} bytes on disk, server says {total}"
        )
    return {
        "url": url,
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "fetched_at": fetched_at,
        "last_modified": last_modified,
    }


# --------------------------------------------------------------------------
# Microdata
# --------------------------------------------------------------------------


def us_member(zf: zipfile.ZipFile) -> str:
    names = [n for n in zf.namelist() if not n.endswith("/")]
    us = [n for n in names if "DUSMCPUB" in n.upper()]
    if len(us) != 1:
        raise ValueError(f"expected one US (DUSMCPUB) file in the zip, found {names}")
    return us[0]


def tabulate(zip_path: Path) -> tuple[Counter, dict]:
    """Counter keyed by (resident_status, sex, age12, icd4) over every record.

    The zip uses Deflate64 (method 9), which Python's zipfile cannot read, so
    the member is streamed through Info-ZIP `unzip -p` and its CRC-32 and
    length are checked here against the zip's central directory.
    """
    counts: Counter = Counter()
    info = {"records": 0, "years": Counter(), "record_lengths": Counter()}
    with zipfile.ZipFile(zip_path) as zf:
        member = us_member(zf)
        zinfo = zf.getinfo(member)
    info["member"] = member
    info["compress_type"] = zinfo.compress_type
    crc, nbytes = 0, 0
    proc = subprocess.Popen(
        ["unzip", "-p", str(zip_path), member], stdout=subprocess.PIPE, bufsize=1 << 20
    )
    assert proc.stdout is not None
    for line in proc.stdout:
        crc = zlib.crc32(line, crc)
        nbytes += len(line)
        rec = line.rstrip(b"\r\n")
        info["records"] += 1
        info["record_lengths"][len(rec)] += 1
        info["years"][rec[101:105].decode()] += 1
        counts[
            (
                rec[19:20].decode(),
                rec[68:69].decode(),
                rec[78:80].decode(),
                rec[145:149].decode().strip(),
            )
        ] += 1
    if proc.wait() != 0:
        raise RuntimeError(f"unzip exited with status {proc.returncode}")
    if nbytes != zinfo.file_size or crc != zinfo.CRC:
        raise RuntimeError(
            f"{member}: read {nbytes} bytes, CRC {crc:#010x}; "
            f"zip says {zinfo.file_size} bytes, CRC {zinfo.CRC:#010x}"
        )
    info["uncompressed_bytes"] = nbytes
    info["crc32"] = f"{crc:#010x}"
    info["years"] = dict(info["years"])
    info["record_lengths"] = {str(k): v for k, v in info["record_lengths"].items()}
    return counts, info


def residents(counts: Counter) -> Counter:
    """Drop foreign residents (resident status 4), as NCHS tabulations do."""
    out: Counter = Counter()
    for (res, sex, age, icd), n in counts.items():
        if res != "4":
            out[(sex, age, icd)] += n
    return out


def cell(res: Counter, sexes: set[str], ages: set[str], pred=None) -> int:
    return sum(
        n
        for (sex, age, icd), n in res.items()
        if sex in sexes and age in ages and (pred is None or pred(icd))
    )


# --------------------------------------------------------------------------
# Published NCHS tables
# --------------------------------------------------------------------------

NUM = r"(?:\d{1,3}(?:,\d{3})*|–|-|\*)"


def to_int(tok: str) -> int | None:
    """Printed count -> int; '-'/'–' (quantity zero) -> 0; '*' (suppressed) -> None."""
    if tok == "*":
        return None
    return 0 if tok in ("–", "-") else int(tok.replace(",", ""))


def layout_pages(pdf: Path) -> list[str]:
    reader = PdfReader(pdf)
    return [p.extract_text(extraction_mode="layout") for p in reader.pages]


def pdf_pages(pdf: Path) -> tuple[list[str], str]:
    """Page texts, preferring poppler's pdftotext -layout.

    pypdf's layout mode runs adjacent cells together on at least one row of
    the 2021 control table (I30.0), so pdftotext is used when it is on PATH;
    either way the parsed rows must satisfy each table's own identities.
    """
    if shutil.which("pdftotext"):
        out = subprocess.run(
            ["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True
        ).stdout.decode("utf-8", errors="replace")
        return out.split("\f"), "pdftotext -layout"
    return layout_pages(pdf), "pypdf layout mode"


def check_layout(pdf: Path) -> tuple[list[str], str]:
    """The record layout must print each field the tabulation reads at the expected
    position."""
    pages, how = pdf_pages(pdf)
    text = "\n".join(pages)
    errs = []
    for pos, size, item in LAYOUT_FIELDS:
        if not re.search(rf"^\s*{re.escape(pos)}\s+{size}\s+{item}\s*$", text, re.M):
            errs.append(f"record layout {pdf.name}: no line '{pos} {size} {item}'")
    return errs, how


def parse_control_totals(pdf: Path) -> tuple[dict[str, int | None], list[str], str]:
    """ICD-10 code (as printed, e.g. 'I21.9', 'I10') -> underlying-cause count.

    None means the table prints '*' (suppressed). Each printed row gives
    underlying cause, record-axis total mentions, record-axis secondary
    mentions and entity-axis mentions; where none is suppressed, total
    mentions must equal underlying + secondary, which catches mis-split cells.
    """
    row = re.compile(
        rf"(\*?[A-Z]\d{{2}}(?:\.\d)?)\s+({NUM})\s+({NUM})\s+({NUM})\s+({NUM})(?=\s|$)"
    )
    out: dict[str, int | None] = {}
    errs: list[str] = []
    pages, how = pdf_pages(pdf)
    for text in pages:
        if "Control Total Table 1" not in re.sub(r"\s+", " ", text):
            continue
        for line in text.split("\n"):
            for m in row.finditer(line):
                code = m.group(1)
                under, total, second, _entity = (to_int(g) for g in m.group(2, 3, 4, 5))
                if code in out:
                    errs.append(f"control table: {code} appears twice")
                if None not in (under, total, second) and total != under + second:
                    errs.append(f"control table {code}: {total} != {under} + {second}")
                out[code] = under
    return out, errs, how


def file_code_to_printed(icd4: str) -> str:
    """'I219' -> 'I21.9'; 'I10' -> 'I10'."""
    return icd4 if len(icd4) == 3 else f"{icd4[:3]}.{icd4[3:]}"


def printed_to_file_code(code: str) -> str:
    """'I21.9' -> 'I219'; '*U07.1' -> 'U071'."""
    return code.replace(".", "").lstrip("*")


def check_control_totals(pdf: Path, res: Counter) -> tuple[list[str], str, dict]:
    ctl, errs, how = parse_control_totals(pdf)
    mine: Counter = Counter()
    for (_, _, icd), n in res.items():
        mine[file_code_to_printed(icd)] += n
    missing = sorted(c for c in mine if c not in ctl)
    if missing:
        errs.append(f"codes in microdata but not in control table: {missing[:20]}")
    printed_pos = [v for v in ctl.values() if v]
    floor = min(printed_pos) if printed_pos else 0
    starred = sorted(c for c, v in ctl.items() if v is None)
    for c, v in sorted(ctl.items()):
        m = mine.get(c, 0)
        if v is None:
            if not 0 < m < floor:
                errs.append(
                    f"control total {c}: printed '*', microdata {m} (expected "
                    f"1..{floor - 1})"
                )
        elif m != v:
            errs.append(f"control total {c}: microdata {m}, table {v}")
    printed_sum = sum(v for v in ctl.values() if v)
    starred_sum = sum(mine.get(c, 0) for c in starred)
    if printed_sum + starred_sum != sum(res.values()):
        errs.append(
            f"control table printed counts {printed_sum:,} + starred codes' microdata "
            f"{starred_sum:,} != microdata total {sum(res.values()):,}"
        )
    by_cause = {}
    for k, (_, pred) in CAUSES.items():
        codes = [c for c in ctl if pred(printed_to_file_code(c))]
        by_cause[k] = {
            "printed": sum(ctl[c] or 0 for c in codes),
            "starred_codes": sum(ctl[c] is None for c in codes),
            "starred_microdata": sum(mine.get(c, 0) for c in codes if ctl[c] is None),
            "microdata": cell(res, {"F", "M"}, set(AGE12), pred),
        }
    summary = {
        "codes": len(ctl),
        "starred_codes": len(starred),
        "starred_deaths_microdata": starred_sum,
        "max_starred_microdata": max((mine.get(c, 0) for c in starred), default=0),
        "smallest_printed_count": floor,
        "printed_sum": printed_sum,
        "by_cause": by_cause,
    }
    return errs, how, summary


# ---- 2021: NVSR 73-08 (Deaths: Final data for 2021) ----------------------


# NVSR 73-08 counts: no suppression marker (a '*' there marks an unreliable rate).
NUM_FINAL = r"(?:\d{1,3}(?:,\d{3})*|–|-)"


def numbers_after(line: str, anchor: str) -> list[int]:
    tail = line[line.index(anchor) + len(anchor) :]
    tail = re.sub(
        r"^\d(?=\s)", "", tail
    )  # footnote marker glued to the label, e.g. "(U07.1)4"
    return [to_int(t) for t in re.findall(rf"(?<![\w.]){NUM_FINAL}(?![\w.])", tail)]


def parse_nvsr_final(pdf: Path) -> dict:
    pages = layout_pages(pdf)
    t2 = [p for p in pages if "Table 2. Number of deaths and death rate by age" in p]
    t7 = [p for p in pages if "Table 7. Number of deaths from 113 selected causes" in p]
    t9 = [p for p in pages if "Table 9. Number of deaths from 113 selected causes" in p]
    out: dict = {"table2": {}, "table7": {}, "table9": {}}

    # Table 2, first page: the first Total / Male / Female rows of the Number panel.
    for line in t2[0].split("\n"):
        s = line.strip()
        for label, key in (("Total", "total"), ("Male", "M"), ("Female", "F")):
            if s.startswith(label) and key not in out["table2"]:
                vals = numbers_after(s, label)
                if len(vals) >= 13:
                    out["table2"][key] = vals[:13]
        if len(out["table2"]) == 3:
            break

    anchors = {
        "all": "All causes",
        "cancer": "(C00–C97)",
        "chd": "(I20–I25)",
        "stroke": "(I60–I69)",
        "major_cvd": "(I00–I78)",
        "covid": "(U07.1)",
    }
    for key, anchor in anchors.items():
        for table, pages_ in (("table7", t7), ("table9", t9)):
            for text in pages_:
                hit = [ln for ln in text.split("\n") if anchor in ln]
                if hit:
                    vals = numbers_after(hit[0], anchor)
                    out[table][key] = vals[:13] if table == "table7" else vals[:3]
                    break
    return out


# Column order in NVSR 73-08 Tables 2 and 7: all ages, <1, 1-4, 5-14, 15-24,
# 25-34, 35-44, 45-54, 55-64, 65-74, 75-84, 85+, not stated.
NVSR_AGE_COLS = [
    "all",
    "01",
    "02",
    "03",
    "04",
    "05",
    "06",
    "07",
    "08",
    "09",
    "10",
    "11",
    "12",
]


def check_final_data_2021(pdf: Path, res: Counter) -> tuple[list[str], dict]:
    errors: list[str] = []
    checks: dict[str, str] = {}
    nv = parse_nvsr_final(pdf)
    t2 = nv["table2"]
    for key, sexes in (("total", {"F", "M"}), ("M", {"M"}), ("F", {"F"})):
        pub = t2.get(key)
        if not pub:
            errors.append(f"NVSR Table 2: row {key} not parsed")
            continue
        for col, v in zip(NVSR_AGE_COLS, pub):
            ages = set(AGE12) if col == "all" else {col}
            m = cell(res, sexes, ages)
            if m != v:
                errors.append(
                    f"NVSR Table 2 {key} age {col}: published {v}, microdata {m}"
                )
    checks["nvsr73_08_table2"] = (
        "all-cause deaths by age group x sex (13 cols x 3 rows) match"
    )

    preds = {
        "all": None,
        "cancer": CAUSES["cancer"][1],
        "chd": CAUSES["chd"][1],
        "stroke": CAUSES["stroke"][1],
        "major_cvd": MAJOR_CVD,
        "covid": CAUSES["covid"][1],
    }
    for key, pred in preds.items():
        pub = nv["table7"].get(key)
        if not pub or len(pub) != 13:
            errors.append(f"NVSR Table 7 {key}: not parsed ({pub})")
        else:
            for col, v in zip(NVSR_AGE_COLS, pub):
                ages = set(AGE12) if col == "all" else {col}
                m = cell(res, {"F", "M"}, ages, pred)
                if m != v:
                    errors.append(
                        f"NVSR Table 7 {key} age {col}: published {v}, microdata {m}"
                    )
        pub = nv["table9"].get(key)
        if not pub or len(pub) != 3:
            errors.append(f"NVSR Table 9 {key}: not parsed ({pub})")
        else:
            for sexes, v, lab in zip(
                ({"F", "M"}, {"M"}, {"F"}), pub, ("both", "male", "female")
            ):
                m = cell(res, sexes, set(AGE12), pred)
                if m != v:
                    errors.append(
                        f"NVSR Table 9 {key} {lab}: published {v}, microdata {m}"
                    )
    checks["nvsr73_08_table7"] = (
        "deaths by age group (both sexes) for all causes, C00-C97, I20-I25, I60-I69, "
        "I00-I78, U07.1 match (13 cols each)"
    )
    checks["nvsr73_08_table9"] = (
        "deaths by sex (all ages) for all causes, C00-C97, I20-I25, I60-I69, I00-I78, "
        "U07.1 match"
    )
    return errors, checks


# ---- 2023: NVSR 74-10 (Deaths: Leading causes for 2023) ------------------

LC_PANEL = re.compile(
    r"^\s{8,}(?P<group>\S.*?), (?P<sex>both sexes|male|female)"
    r"(?:, (?P<age>all ages|\d+–\d+|\d+ and older))?\d*\s*$"
)
LC_ROW = re.compile(
    r"^\s*(?P<rank>\d+|\.\.\.|…)\s+(?P<label>\S.*?)\s+(?P<n>\d{1,3}(?:,\d{3})*)"
    r"\s+(?P<pct>\d+\.\d)\s+(?P<rate>[\d,]+\.\d|\*)\s*$"
)
LC_CAUSES = {
    # key: (substring identifying the printed row, predicate on the ICD-10 code)
    "cancer": ("(C00–C97)", CAUSES["cancer"][1]),
    "stroke": ("(I60–I69)", CAUSES["stroke"][1]),
    "heart": ("(I00–I09,I11,I13,I20–I51)", HEART),
    "covid": ("(*U07.1)", CAUSES["covid"][1]),
}
LC_SEX = {"both sexes": {"F", "M"}, "male": {"M"}, "female": {"F"}}
# Table 1 age label -> age recode 12 codes; pairs of 5-year panels sum to one code.
LC_AGES = {
    "all ages": set(AGE12),
    "1–4": {"02"},
    "25–34": {"05"},
    "35–44": {"06"},
    "45–54": {"07"},
    "55–64": {"08"},
    "65–74": {"09"},
    "75–84": {"10"},
    "85 and older": {"11"},
    "65 and older": {"09", "10", "11"},
}
LC_PAIRS = {("5–9", "10–14"): {"03"}, ("15–19", "20–24"): {"04"}}
ALL_ORIGINS = "All races, all origins"
INFANTS = "Infants, all races, all origins"


def parse_leading_causes(pdf: Path) -> tuple[dict, list[str], str]:
    """(group, sex, age) -> {'all': n, 'residual': n, 'ranked': [n...], cause key: n}.

    Tables 1 and 2 only. Age is None for the infant panels of Table 2.
    """
    pages, how = pdf_pages(pdf)
    panels: dict = {}
    errs: list[str] = []
    for text in pages:
        flat = re.sub(r"\s+", " ", text)
        if not (
            "Table 1. Number of deaths, percentage of total deaths, and death rate"
            in flat
            or "Table 2. Number of infant, neonatal, and postneonatal deaths" in flat
        ):
            continue
        key = None
        for line in text.split("\n"):
            h = LC_PANEL.match(line)
            if h:
                key = (h.group("group"), h.group("sex"), h.group("age"))
                if key in panels:
                    errs.append(f"leading causes: panel {key} appears twice")
                panels[key] = {"ranked": []}
                continue
            r = LC_ROW.match(line)
            if not r or key is None:
                continue
            n = int(r.group("n").replace(",", ""))
            label = r.group("label")
            p = panels[key]
            if label.startswith("All causes"):
                p["all"] = n
            elif label.startswith("All other causes"):
                p["residual"] = n
            else:
                p["ranked"].append(n)
                for ck, (anchor, _) in LC_CAUSES.items():
                    if anchor in label:
                        p[ck] = n
    for key, p in panels.items():
        if key[0] not in (ALL_ORIGINS, INFANTS):
            continue  # race and Hispanic-origin panels are not used (some headers wrap)
        if "all" not in p or "residual" not in p:
            errs.append(f"leading causes {key}: all-causes or residual row not parsed")
        elif p["all"] != sum(p["ranked"]) + p["residual"]:
            errs.append(
                f"leading causes {key}: {len(p['ranked'])} ranked causes "
                f"{sum(p['ranked']):,} "
                f"+ residual {p['residual']:,} != all causes {p['all']:,}"
            )
    return panels, errs, how


def check_leading_causes_2023(pdf: Path, res: Counter) -> tuple[list[str], dict, dict]:
    panels, errors, how = parse_leading_causes(pdf)
    compared: Counter = Counter()
    expected = {
        (ALL_ORIGINS, s, a)
        for s in LC_SEX
        for a in list(LC_AGES) + [x for pair in LC_PAIRS for x in pair]
    }
    expected |= {(INFANTS, s, None) for s in LC_SEX}
    for k in sorted(expected - set(panels), key=str):
        errors.append(f"leading causes: panel {k} not parsed")

    def compare(label: str, pub: int, mine: int, what: str) -> None:
        compared[what] += 1
        if pub != mine:
            errors.append(
                f"NVSR 74-10 {label} {what}: published {pub:,}, microdata {mine:,}"
            )

    for sex, sexes in LC_SEX.items():
        for age, ages in LC_AGES.items():
            p = panels.get((ALL_ORIGINS, sex, age))
            if not p:
                continue
            compare(f"Table 1 {sex} {age}", p["all"], cell(res, sexes, ages), "all")
            for ck, (_, pred) in LC_CAUSES.items():
                if ck in p:
                    compare(
                        f"Table 1 {sex} {age}", p[ck], cell(res, sexes, ages, pred), ck
                    )
        for pair, ages in LC_PAIRS.items():
            ps = [panels.get((ALL_ORIGINS, sex, a)) for a in pair]
            if not all(ps):
                continue
            lab = f"Table 1 {sex} {' + '.join(pair)}"
            compare(lab, sum(p["all"] for p in ps), cell(res, sexes, ages), "all")
            for ck, (_, pred) in LC_CAUSES.items():
                if all(ck in p for p in ps):
                    compare(
                        lab, sum(p[ck] for p in ps), cell(res, sexes, ages, pred), ck
                    )
        p = panels.get((INFANTS, sex, None))
        if p:
            compare(f"Table 2 infants {sex}", p["all"], cell(res, sexes, {"01"}), "all")
    n_panels = sum(1 for k in panels if k[0] in (ALL_ORIGINS, INFANTS))
    checks = {
        "nvsr74_10_tables_1_2": (
            (
                f"{n_panels} panels parsed ({how}): 'All races, all origins' in Table "
                "1 and "
                "'Infants, all races, all origins' in Table 2; each satisfies ranked "
                "causes + "
                f"all other causes = all causes; published = microdata for "
            )
            + ", ".join(
                f"{compared[k]} {k}"
                for k in ("all", "cancer", "stroke", "heart", "covid")
            )
            + " comparisons (all-cause by sex for all ages, under 1, 1-4, 5-14, 15-24, "
            "25-34, ..., 85+ and 65+; causes wherever ranked)"
        )
    }
    headline = panels.get((ALL_ORIGINS, "both sexes", "all ages"), {})
    return (
        errors,
        checks,
        {"comparisons": dict(compared), "all_ages_both_sexes": headline},
    )


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------

COLUMNS = [
    "year",
    "sex",
    "age_group_start",
    "age_group_end",
    "age_group_label",
    "all_deaths",
    "cvd_deaths",
    "chd_deaths",
    "stroke_deaths",
    "cancer_deaths",
    "cvd_share",
    "chd_share",
    "stroke_share",
    "cancer_share",
    "covid_deaths",
    "covid_share",
]


def build_rows(
    year: int, res: Counter, groups: list[str], include_all_ages: bool
) -> list[dict]:
    rows = []
    for sex_key, sexes in (("female", {"F"}), ("male", {"M"}), ("total", {"F", "M"})):
        entries = [(g, {g}) for g in groups]
        if include_all_ages:
            entries.append(("all", set(AGE12)))
        for g, ages in entries:
            if g == "all":
                label, start, end = "All ages", None, None
            else:
                label, start, end = AGE12[g]
            n_all = cell(res, sexes, ages)
            row = {
                "year": year,
                "sex": sex_key,
                "age_group_start": "" if start is None else start,
                "age_group_end": "" if end is None else end,
                "age_group_label": label,
                "all_deaths": n_all,
            }
            for k, (_, pred) in CAUSES.items():
                n = cell(res, sexes, ages, pred)
                row[f"{k}_deaths"] = n
                row[f"{k}_share"] = f"{n / n_all:.6f}" if n_all else ""
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    path.write_text(buf.getvalue())


def build(year: int, refresh: bool) -> list[str]:
    ed = EDITIONS[year]
    out_dir: Path = ed["out_dir"]
    manifest_path = out_dir / "MANIFEST.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    old = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    files: dict[str, dict] = {}
    print(f"== {year} -> {out_dir.relative_to(ROOT)}/")
    print("Raw files:")
    for rel, url in ed["raw_files"].items():
        files[rel] = fetch(out_dir, rel, url, old, refresh)

    errors: list[str] = []
    checks: dict[str, str] = {}

    # Record layout
    lay_errs, lay_how = check_layout(out_dir / ed["layout"])
    errors += lay_errs
    checks["record_layout"] = (
        (
            f"{Path(ed['layout']).name} ({lay_how}) gives resident status at 20, sex "
            "at 69, "
            "age recode 12 at 79-80, data year at 102-105, underlying cause at 146-149"
        )
        if not lay_errs
        else "FAILED"
    )

    print("Tabulating microdata ...")
    counts, info = tabulate(out_dir / ed["zip"])
    res = residents(counts)
    n_foreign = sum(n for (r, *_), n in counts.items() if r == "4")
    print(
        f"  {info['member']}: {info['records']:,} records, "
        f"{n_foreign:,} foreign residents excluded, {sum(res.values()):,} resident "
        "deaths"
    )

    # 1. data year
    if set(info["years"]) != {str(year)}:
        errors.append(f"data years in file: {info['years']}")
    checks["data_year"] = f"all {info['records']:,} records have data year {year}"

    # 3. control totals, code by code
    ctl_errs, ctl_how, ctl = check_control_totals(out_dir / ed["control"], res)
    errors += ctl_errs
    if ctl["starred_codes"]:
        detail = (
            f"{ctl['codes']:,} ICD-10 codes parsed ({ctl_how}); every row with no "
            "suppressed "
            f"cell satisfies total mentions = underlying + secondary; the printed "
            f"underlying-cause counts equal the microdata for every code; the "
            f"{ctl['starred_codes']:,} codes printed '*' have 1 to "
            f"{ctl['max_starred_microdata']} deaths each in the microdata "
            f"({ctl['starred_deaths_microdata']:,} in all; the smallest printed count "
            "is "
            f"{ctl['smallest_printed_count']}); printed counts sum to "
            f"{ctl['printed_sum']:,}"
        )
    else:
        detail = (
            f"{ctl['codes']:,} ICD-10 codes parsed ({ctl_how}); every row satisfies "
            "total "
            "mentions = underlying + secondary; underlying-cause counts equal the "
            "microdata "
            f"for every code; they sum to {ctl['printed_sum']:,}"
        )
    checks["control_total_table_1"] = detail if not ctl_errs else "FAILED"
    for k, v in ctl["by_cause"].items():
        print(
            f"  control table {k:6s} printed {v['printed']:,} + {v['starred_codes']} "
            "starred "
            f"codes ({v['starred_microdata']:,} in microdata); microdata "
            f"{v['microdata']:,}"
        )

    # 4+. published tables
    kind, pub_rel = ed["published"]
    extra: dict = {}
    if kind == "final_data":
        pub_errs, pub_checks = check_final_data_2021(out_dir / pub_rel, res)
    else:
        pub_errs, pub_checks, extra = check_leading_causes_2023(out_dir / pub_rel, res)
        print(f"  NVSR 74-10 comparisons: {extra['comparisons']}")
    errors += pub_errs
    checks.update(pub_checks)

    # Output
    main_rows = build_rows(year, res, MAIN_GROUPS, include_all_ages=False)
    all_rows = build_rows(year, res, list(AGE12), include_all_ages=True)
    for name, rows in (
        ("cause_shares.csv", main_rows),
        ("cause_shares_all_groups.csv", all_rows),
    ):
        p = out_dir / name
        write_csv(p, rows)
        files[name] = {
            "sha256": sha256(p),
            "bytes": p.stat().st_size,
            "rows": len(rows),
            "derived_from": [ed["zip"]],
            "checked_against": [ed["control"], pub_rel],
            "generated_by": "scripts/fetch_causes.py",
        }
    print("\ncause_shares.csv:")
    print(
        f"  {'sex':6s} {'age':>6s} {'all':>9s} {'cvd':>8s} {'chd':>8s} {'stroke':>8s} "
        f"{'cancer':>8s} {'covid':>8s}"
    )
    for r in main_rows:
        print(
            f"  {r['sex']:6s} {r['age_group_label']:>6s} {r['all_deaths']:9,d} "
            f"{r['cvd_share']:>8s} "
            f"{r['chd_share']:>8s} {r['stroke_share']:>8s} {r['cancer_share']:>8s} "
            f"{r['covid_share']:>8s}"
        )
    smallest = min(min(r[f"{k}_deaths"] for k in CAUSES) for r in main_rows)
    print(f"  smallest cause cell in cause_shares.csv: {smallest:,} deaths")

    manifest = {
        "source": ed["sources"],
        "generated_by": "scripts/fetch_causes.py",
        "year": year,
        "role": ed["role"],
        "definitions": {
            "deaths": (
                f"Deaths of US residents occurring in the 50 states and DC in {year}, "
                "classified by underlying cause of death (ICD-10). Records with "
                "resident "
                "status 4 (foreign residents) are excluded, as in NCHS tabulations."
            ),
            "cvd_deaths": CAUSES["cvd"][0]
            + " (all diseases of the circulatory system)",
            "chd_deaths": CAUSES["chd"][0] + " (ischemic heart diseases)",
            "stroke_deaths": CAUSES["stroke"][0] + " (cerebrovascular diseases)",
            "cancer_deaths": CAUSES["cancer"][0] + " (malignant neoplasms)",
            "covid_deaths": (
                CAUSES["covid"][0]
                + " (COVID-19); extra column beyond DESIGN.md, kept for "
                "a sensitivity on shares of non-COVID deaths"
            ),
            "shares": "cause deaths / all-cause deaths in the same cell, 6 decimals",
            "age_group_start/end": (
                "inclusive ages in completed years from NCHS age recode 12; "
                "age_group_end is blank for the open-ended 85+ group"
            ),
            "sex": "female, male, or total (both sexes)",
            "age_not_stated": (
                "cause_shares.csv omits deaths with age not stated; "
                "cause_shares_all_groups.csv lists them"
            ),
        },
        "microdata": {
            "member": info["member"],
            "records": info["records"],
            "uncompressed_bytes": info["uncompressed_bytes"],
            "crc32_verified": info["crc32"],
            "record_lengths": info["record_lengths"],
            "foreign_residents_excluded": n_foreign,
            "resident_deaths": sum(res.values()),
        },
        "checks": checks,
        "notes": (
            ed["notes"]
            + (
                " The counts here come from the NCHS public-use microdata and are "
                "checked against NCHS's own published totals (see checks). The "
                "smallest cause "
                f"cell in cause_shares.csv has {smallest:,} deaths."
            )
        ),
        "files": dict(sorted(files.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return errors if not errors else [f"{year}: {e}" for e in errors]


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--year", choices=["2023", "2021", "all"], default="2023")
    ap.add_argument(
        "--refresh", action="store_true", help="download every raw file again"
    )
    args = ap.parse_args(argv)
    years = sorted(EDITIONS, reverse=True) if args.year == "all" else [int(args.year)]
    errors: list[str] = []
    for year in years:
        errors += build(year, args.refresh)
        print()
    if errors:
        print(f"{len(errors)} check(s) FAILED:")
        for e in errors[:60]:
            print("  " + e)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
