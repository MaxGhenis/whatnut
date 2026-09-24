"""Fetch and parse the United States life tables (NVSR), 2023 and 2021.

Editions
--------
2023 (baseline; DESIGN.md decision 1), written to data/life_tables/:
  Arias E, Xu JQ, Kochanek K. United States life tables, 2023. National Vital
  Statistics Reports; vol 74 no 6. Hyattsville, MD: National Center for Health
  Statistics. July 15, 2025. doi:10.15620/cdc/174591

2021 (archived sensitivity; a COVID-19 peak year), written to
data/life_tables/2021/:
  Arias E, Xu JQ, Kochanek KD. United States life tables, 2021. National Vital
  Statistics Reports; vol 72 no 12. Hyattsville, MD: National Center for Health
  Statistics. November 7, 2023. doi:10.15620/cdc:132418

For each edition the script downloads, into <edition dir>/raw/:
  Table01.xlsx   Life table for the total population: United States, <year>
  Table02.xlsx   Life table for males: United States, <year>
  Table03.xlsx   Life table for females: United States, <year>
  nvsr<vol>-<no>.pdf  the report itself (used only to check the parsed values
                 against the rounded values printed in Tables 1-3 and Table A)

and writes <edition dir>/{total,male,female}.csv with columns
age, qx, lx, dx, Lx, Tx, ex for ages 0-100 (100 = "100 and older"), holding
the spreadsheet cell values unchanged (full stored precision), and
<edition dir>/MANIFEST.json with url, sha256, fetched_at and bytes for every
raw file plus sha256 for every derived CSV. Paths in a manifest are relative
to the folder that holds it.

Checks (the script exits non-zero if any fails):
  * 101 rows per table, ages 0..100 consecutive, q(100) = 1.
  * The spreadsheet title names the edition's year.
  * Each CSV round-trips to exactly the spreadsheet values.
  * Every row of the PDF's printed Tables 1-3 equals the spreadsheet values
    rounded half-up to the printed precision (qx 6 dp; lx, dx, Lx, Tx
    integers; ex 1 dp). The reports round exact .5 values up, so Python's
    round-half-even would disagree on some cells.
  * e(0) for males, females and total equals the printed Table A value.
  * Internal identities: e(x) = T(x)/l(x); l(x+1) = l(x) - d(x).

Rerunnable: a raw file already on disk whose sha256 matches the manifest is
reused (its fetched_at is kept); pass --refresh to download everything again.

Usage: .venv/bin/python scripts/fetch_life_tables.py [--year 2023|2021|all] [--refresh]
       (default --year all; both editions are small)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import re
import sys
from pathlib import Path

import openpyxl
import requests
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT / "data" / "life_tables"

FTP = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Publications/NVSR"
EDITIONS = {
    2023: {
        "out_dir": BASE_DIR,
        "nvsr": "74-06",
        "pdf_url": "https://www.cdc.gov/nchs/data/nvsr/nvsr74/nvsr74-06.pdf",
        "citation": (
            "Arias E, Xu JQ, Kochanek K. United States life tables, 2023. "
            "National Vital Statistics Reports; vol 74 no 6. Hyattsville, MD: "
            "National Center for Health Statistics. July 15, 2025. "
            "doi:10.15620/cdc/174591"
        ),
        "role": "baseline (DESIGN.md decision 1)",
    },
    2021: {
        "out_dir": BASE_DIR / "2021",
        "nvsr": "72-12",
        "pdf_url": "https://www.cdc.gov/nchs/data/nvsr/nvsr72/nvsr72-12.pdf",
        "citation": (
            "Arias E, Xu JQ, Kochanek KD. United States life tables, 2021. "
            "National Vital Statistics Reports; vol 72 no 12. Hyattsville, MD: "
            "National Center for Health Statistics. 2023. "
            "doi:10.15620/cdc:132418"
        ),
        "role": (
            "archived sensitivity; 2021 was a COVID-19 peak year, so the 2023 "
            "tables in data/life_tables/ are the baseline"
        ),
    },
}
SEXES = {
    # sex label -> (raw xlsx, expected title stem, PDF table title prefix)
    "total": (
        "raw/Table01.xlsx",
        "Table 1. Life table for the total population: United States, {year}",
        "Table 1. Life table for the total population",
    ),
    "male": (
        "raw/Table02.xlsx",
        "Table 2. Life table for males: United States, {year}",
        "Table 2. Life table for males:",
    ),
    "female": (
        "raw/Table03.xlsx",
        "Table 3. Life table for females: United States, {year}",
        "Table 3. Life table for females:",
    ),
}
COLUMNS = ["age", "qx", "lx", "dx", "Lx", "Tx", "ex"]
USER_AGENT = "whatnut-paper data fetcher (https://github.com/MaxGhenis/whatnut)"


def pdf_rel(edition: dict) -> str:
    return f"raw/nvsr{edition['nvsr']}.pdf"


def raw_files(edition: dict) -> dict[str, str]:
    vol_no = edition["nvsr"]
    files = {f"raw/Table0{i}.xlsx": f"{FTP}/{vol_no}/Table0{i}.xlsx" for i in (1, 2, 3)}
    files[pdf_rel(edition)] = edition["pdf_url"]
    return files


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {}


def fetch(out_dir: Path, rel: str, url: str, old: dict, refresh: bool) -> dict:
    """Download url to out_dir/rel unless an identical copy is already there."""
    path = out_dir / rel
    prev = old.get("files", {}).get(rel)
    if not refresh and path.exists() and prev and prev.get("sha256") == sha256(path):
        print(f"  reuse {rel} (sha256 matches manifest)")
        return prev
    path.parent.mkdir(parents=True, exist_ok=True)
    r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=120)
    r.raise_for_status()
    body = r.content
    last_modified = r.headers.get("Last-Modified")
    path.write_bytes(body)
    print(f"  fetched {rel} ({len(body):,} bytes)")
    return {
        "url": url,
        "sha256": sha256(path),
        "bytes": len(body),
        "fetched_at": dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "last_modified": last_modified,
    }


def age_of(label: str) -> int:
    m = re.fullmatch(r"(\d+)\s*[–-]\s*(\d+)", label.strip())
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        assert hi == lo + 1, label
        return lo
    m = re.fullmatch(r"(\d+) and older", label.strip())
    if m:
        return int(m.group(1))
    raise ValueError(f"unrecognised age label {label!r}")


def parse_xlsx(path: Path, title: str) -> list[dict]:
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    if rows[0][0] != title:
        raise ValueError(f"{path.name}: title {rows[0][0]!r} != {title!r}")
    if tuple(rows[2][1:7]) != ("qx", "lx", "dx", "Lx", "Tx", "ex"):
        raise ValueError(f"{path.name}: unexpected column symbols {rows[2]}")
    out = []
    for r in rows[3:]:
        label = r[0]
        if not isinstance(label, str) or not re.match(r"^\d", label):
            continue
        rec = {"age": age_of(label)}
        for name, v in zip(COLUMNS[1:], r[1:7]):
            if not isinstance(v, (int, float)):
                raise ValueError(f"{path.name} age {label}: {name}={v!r}")
            rec[name] = v
        out.append(rec)
    return out


def fmt(v) -> str:
    # repr() of a Python float is the shortest string that round-trips to the
    # same double, so the CSV holds the spreadsheet value exactly.
    return str(v) if isinstance(v, int) else repr(float(v))


def write_csv(path: Path, table: list[dict]) -> None:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(COLUMNS)
    for rec in table:
        w.writerow([rec["age"]] + [fmt(rec[c]) for c in COLUMNS[1:]])
    path.write_text(buf.getvalue())


PDF_ROW = re.compile(
    r"^(\d+)(?:–\d+| and older)[\s.]*?\s"
    r"(\d\.\d{6})\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(\d+\.\d)\s*$"
)


def parse_pdf_tables(pdf: Path) -> dict[str, dict[int, tuple]]:
    """Rows printed in the report's Tables 1-3: age -> (qx, lx, dx, Lx, Tx, ex)."""
    reader = PdfReader(pdf)
    out: dict[str, dict[int, tuple]] = {k: {} for k in SEXES}
    table_a = None
    for page in reader.pages:
        text = page.extract_text()
        if "Table A. Expectation of life, by age" in text and table_a is None:
            m = re.search(r"^0[\s.]+(\d+\.\d) (\d+\.\d) (\d+\.\d) ", text, re.M)
            if m:
                table_a = {
                    "total": m.group(1),
                    "male": m.group(2),
                    "female": m.group(3),
                }
        for sex, (_, _, pdf_title) in SEXES.items():
            if pdf_title not in text:
                continue
            for line in text.split("\n"):
                m = PDF_ROW.match(line.strip())
                if m:
                    age = int(m.group(1))
                    vals = (
                        m.group(2),
                        *(int(g.replace(",", "")) for g in m.group(3, 4, 5, 6)),
                        m.group(7),
                    )
                    out[sex][age] = vals
    out["_table_a_e0"] = table_a
    return out


def half_up(x: float, nd: int) -> float:
    q = 10**nd
    return math.floor(x * q + 0.5) / q


def check_against_pdf(
    sex: str, table: list[dict], printed: dict[int, tuple]
) -> list[str]:
    errs = []
    if sorted(printed) != list(range(101)):
        errs.append(
            f"{sex}: PDF rows parsed for ages {sorted(printed)[:3]}..; expected 0..100"
        )
    for rec in table:
        p = printed.get(rec["age"])
        if p is None:
            continue
        qx_p, lx_p, dx_p, Lx_p, Tx_p, ex_p = p
        checks = [
            ("qx", f"{rec['qx']:.6f}", qx_p),
            ("lx", int(half_up(rec["lx"], 0)), lx_p),
            ("dx", int(half_up(rec["dx"], 0)), dx_p),
            ("Lx", int(half_up(rec["Lx"], 0)), Lx_p),
            ("Tx", int(half_up(rec["Tx"], 0)), Tx_p),
            ("ex", f"{half_up(rec['ex'], 1):.1f}", ex_p),
        ]
        for name, mine, theirs in checks:
            if str(mine) != str(theirs):
                errs.append(
                    f"{sex} age {rec['age']} {name}: xlsx rounds to {mine}, PDF prints "
                    f"{theirs}"
                )
    return errs


def check_identities(sex: str, table: list[dict]) -> list[str]:
    errs = []
    ages = [r["age"] for r in table]
    if ages != list(range(101)):
        errs.append(f"{sex}: ages {ages[:3]}..{ages[-3:]} not 0..100")
    if table[-1]["qx"] != 1:
        errs.append(f"{sex}: q(100) = {table[-1]['qx']} != 1")
    for a, b in zip(table, table[1:]):
        if not math.isclose(a["lx"] - a["dx"], b["lx"], rel_tol=1e-5):
            errs.append(f"{sex} age {a['age']}: l - d != next l")
    for r in table:
        if not math.isclose(r["Tx"] / r["lx"], r["ex"], rel_tol=1e-5):
            errs.append(f"{sex} age {r['age']}: T/l != e")
    return errs


def build(year: int, refresh: bool) -> tuple[list[str], dict]:
    """Fetch, parse, check and write one edition. Returns (errors, summary)."""
    edition = EDITIONS[year]
    out_dir: Path = edition["out_dir"]
    manifest_path = out_dir / "MANIFEST.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    old = load_manifest(manifest_path)
    files: dict[str, dict] = {}
    print(f"== {year} (NVSR {edition['nvsr']}) -> {out_dir.relative_to(ROOT)}/")
    print("Raw files:")
    for rel, url in raw_files(edition).items():
        files[rel] = fetch(out_dir, rel, url, old, refresh)

    printed = parse_pdf_tables(out_dir / pdf_rel(edition))
    errors: list[str] = []
    e0 = {}
    print("Parsed tables:")
    for sex, (rel, title, _) in SEXES.items():
        table = parse_xlsx(out_dir / rel, title.format(year=year))
        errors += check_identities(sex, table)
        errors += check_against_pdf(sex, table, printed[sex])
        out = out_dir / f"{sex}.csv"
        write_csv(out, table)
        with out.open() as f:
            back = list(csv.DictReader(f))
        for rec, row in zip(table, back):
            for c in COLUMNS[1:]:
                if float(row[c]) != float(rec[c]):
                    errors.append(
                        f"{sex} age {rec['age']} {c}: CSV does not round-trip"
                    )
        e0[sex] = table[0]["ex"]
        files[f"{sex}.csv"] = {
            "sha256": sha256(out),
            "bytes": out.stat().st_size,
            "derived_from": [rel],
            "generated_by": "scripts/fetch_life_tables.py",
        }
        print(
            f"  {sex:6s} {len(table)} rows; e(0) = {table[0]['ex']!r}; "
            f"PDF rows matched: {len(printed[sex])}"
        )

    table_a = printed.get("_table_a_e0")
    if not table_a:
        errors.append(f"{year}: could not parse Table A e(0) row from the PDF")
    else:
        for sex, v in table_a.items():
            if f"{half_up(e0[sex], 1):.1f}" != v:
                errors.append(
                    f"{year} Table A e(0) {sex}: printed {v}, xlsx {e0[sex]!r}"
                )
        print(f"  Table A e(0) printed: {table_a}")

    manifest = {
        "source": edition["citation"],
        "year": year,
        "role": edition["role"],
        "generated_by": "scripts/fetch_life_tables.py",
        "columns": {
            "age": "exact age x at start of interval; 100 = '100 and older'",
            "qx": "probability of dying between ages x and x + 1",
            "lx": "number surviving to age x (radix 100,000)",
            "dx": "number dying between ages x and x + 1",
            "Lx": "person-years lived between ages x and x + 1",
            "Tx": "total person-years lived above age x",
            "ex": "expectation of life at age x",
        },
        "notes": (
            "CSV values are the spreadsheet cell values unchanged (the report "
            "prints them rounded). Every printed row of Tables 1-3 was checked "
            "against these values rounded to the printed precision, and e(0) "
            "against Table A."
        ),
        "files": dict(sorted(files.items())),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return errors, {"e0_xlsx": e0, "e0_table_a": table_a}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--year", choices=["2023", "2021", "all"], default="all")
    ap.add_argument(
        "--refresh", action="store_true", help="download every raw file again"
    )
    args = ap.parse_args(argv)
    years = sorted(EDITIONS, reverse=True) if args.year == "all" else [int(args.year)]
    errors: list[str] = []
    for year in years:
        errs, summary = build(year, args.refresh)
        errors += errs
        print(f"  {year}: {len(errs)} failed check(s)\n")
    if errors:
        print(f"{len(errors)} check(s) FAILED:")
        for e in errors[:50]:
            print("  " + e)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
