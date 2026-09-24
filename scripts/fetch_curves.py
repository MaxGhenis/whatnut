#!/usr/bin/env python
"""Fetch and parse the dose-response curves and reproduction targets in data/curves/.

Sources (all fetched from the publisher, Europe PMC or the IHME API):

* Aune et al. 2016, BMC Medicine 14:207 (doi 10.1186/s12916-016-0730-3, PMC5137221):
  full-text XML and Additional file 1 (supplementary tables and figures).
  -> curves/aune2016_nonlinear.csv (every numeric nonlinear dose-response point,
     parsed from Supplementary Tables 14 and 15) and
     curves/aune2016_nonlinear_notes.yaml.
* IHME Burden of Proof, "Diet low in nuts and seeds" (rei 114) -> ischemic heart
  disease (cause 493): raw API JSON -> curves/ihme_bop_nuts_seeds_ihd.csv.
* Fadnes et al. 2022, PLOS Medicine 19(2):e1003889 (doi 10.1371/journal.pmed.1003889,
  PMC8824353), its correction (PMC8956181), supporting files S3 Text, S1-S3 Tables and
  the US forest plots (S6-S13 Figs), plus Johansson et al. 2020 (PMC7360045), which
  Fadnes cites for the life-table method -> curves/fadnes2022_targets.yaml.

Every value written is parsed from the downloaded file by this script, except the
forest-plot values for ages 40 and 80, which exist only as text drawn inside PNG
images; those were transcribed by reading the images and are flagged as such.

Rerunnable: files already recorded in MANIFEST.json with a matching sha256 are reused;
a file on disk without a manifest entry is re-downloaded and compared. Pass --refresh to
re-download everything. Pass --offline to reuse files on disk without any network call.

Usage:  .venv/bin/python scripts/fetch_curves.py [--refresh | --offline]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import re
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "curves"
RAW = OUT / "raw"
MANIFEST = OUT / "MANIFEST.json"
GENERATED_BY = "scripts/fetch_curves.py"
TODAY = dt.date.today().isoformat()

EPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
PLOS_SUPP = (
    "https://journals.plos.org/plosmedicine/article/file"
    "?type=supplementary&id=10.1371/journal.pmed.1003889.{}"
)
BOP = "https://vizhub.healthdata.org/burden-of-proof/api/v1/"
BOP_RISK, BOP_CAUSE = 114, 493

# (relative path under data/curves, url, short description)
DOWNLOADS: list[tuple[str, str, str]] = [
    (
        "raw/aune2016_PMC5137221.xml",
        EPMC.format("PMC5137221"),
        "Aune 2016 full text, JATS XML",
    ),
    (
        "raw/aune2016_MOESM1_ESM.pdf",
        "https://static-content.springer.com/esm/art%3A10.1186%2Fs12916-016-0730-3/"
        "MediaObjects/12916_2016_730_MOESM1_ESM.pdf",
        "Aune 2016 Additional file 1 (supplementary figures and tables)",
    ),
    (
        "raw/fadnes2022_PMC8824353.xml",
        EPMC.format("PMC8824353"),
        "Fadnes 2022 full text, JATS XML",
    ),
    (
        "raw/fadnes2022_correction_PMC8956181.xml",
        EPMC.format("PMC8956181"),
        "Fadnes 2022 correction notice (funding statement only)",
    ),
    (
        "raw/fadnes2022_s003.pdf",
        PLOS_SUPP.format("s003"),
        "Fadnes S3 Text: US and Norway intakes",
    ),
    (
        "raw/fadnes2022_s004.pdf",
        PLOS_SUPP.format("s004"),
        "Fadnes S1 Table: hazard ratios by food group",
    ),
    (
        "raw/fadnes2022_s005.pdf",
        PLOS_SUPP.format("s005"),
        "Fadnes S2 Table: LE gain by food group, US, ages 20 and 60",
    ),
    (
        "raw/fadnes2022_s006.pdf",
        PLOS_SUPP.format("s006"),
        "Fadnes S3 Table: time-to-full-effect sensitivity",
    ),
    (
        "raw/fadnes2022_s012.png",
        PLOS_SUPP.format("s012"),
        "Fadnes S6 Fig: US females age 20 forest plot",
    ),
    (
        "raw/fadnes2022_s013.png",
        PLOS_SUPP.format("s013"),
        "Fadnes S7 Fig: US males age 20 forest plot",
    ),
    (
        "raw/fadnes2022_s014.png",
        PLOS_SUPP.format("s014"),
        "Fadnes S8 Fig: US females age 40 forest plot",
    ),
    (
        "raw/fadnes2022_s015.png",
        PLOS_SUPP.format("s015"),
        "Fadnes S9 Fig: US males age 40 forest plot",
    ),
    (
        "raw/fadnes2022_s016.png",
        PLOS_SUPP.format("s016"),
        "Fadnes S10 Fig: US females age 60 forest plot",
    ),
    (
        "raw/fadnes2022_s017.png",
        PLOS_SUPP.format("s017"),
        "Fadnes S11 Fig: US males age 60 forest plot",
    ),
    (
        "raw/fadnes2022_s018.png",
        PLOS_SUPP.format("s018"),
        "Fadnes S12 Fig: US females age 80 forest plot",
    ),
    (
        "raw/fadnes2022_s019.png",
        PLOS_SUPP.format("s019"),
        "Fadnes S13 Fig: US males age 80 forest plot",
    ),
    (
        "raw/johansson2020_PMC7360045.xml",
        EPMC.format("PMC7360045"),
        "Johansson 2020 HAAD (life-table method cited by Fadnes as ref 13), JATS XML",
    ),
]
_q = f"risk={BOP_RISK}&cause={BOP_CAUSE}"
DOWNLOADS += [
    (
        f"raw/ihme_bop/risk_cause_metadata_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}risk_cause_metadata?{_q}",
        "BoP pair metadata",
    ),
    (
        f"raw/ihme_bop/output_data_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}output_data?{_q}",
        "BoP risk curve, fixed & random effects UI",
    ),
    (
        f"raw/ihme_bop/fixed_effect_data_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}fixed_effect_data?{_q}",
        "BoP risk curve, fixed effects UI",
    ),
    (
        f"raw/ihme_bop/study_data_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}study_data?{_q}&evidence_data_type_id=1",
        "BoP input study data",
    ),
    (
        f"raw/ihme_bop/study_citations_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}study_citations?{_q}",
        "BoP study citations",
    ),
    (
        f"raw/ihme_bop/study_data_range_r{BOP_RISK}_c{BOP_CAUSE}.json",
        f"{BOP}study_data_range?{_q}",
        "BoP study data range",
    ),
    (
        "raw/ihme_bop/comparison.json",
        f"{BOP}comparison",
        "BoP comparison table (names, star ratings, scores)",
    ),
    ("raw/ihme_bop/metadata_risk.json", f"{BOP}metadata/risk", "BoP risk hierarchy"),
    ("raw/ihme_bop/metadata_cause.json", f"{BOP}metadata/cause", "BoP cause hierarchy"),
    (
        "raw/ihme_bop/metadata_data_type.json",
        f"{BOP}metadata/data_type",
        "BoP evidence data types",
    ),
]


# --------------------------------------------------------------------------- utils


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text())
    return {"files": {}}


def http_get(url: str) -> bytes:
    last = None
    for attempt in range(4):
        try:
            r = requests.get(
                url, timeout=120, headers={"User-Agent": "whatnut-paper data fetcher"}
            )
            r.raise_for_status()
            return r.content
        except requests.RequestException as e:  # pragma: no cover - network
            last = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"failed to fetch {url}: {last}")


def fetch_all(manifest: dict, refresh: bool, offline: bool) -> None:
    files = manifest.setdefault("files", {})
    for rel, url, desc in DOWNLOADS:
        path = OUT / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = files.get(rel)
        if (
            path.exists()
            and entry
            and entry.get("sha256") == sha256(path)
            and not refresh
        ):
            print(f"reuse   {rel}")
            continue
        if offline:
            if not path.exists():
                raise SystemExit(f"--offline but {rel} is missing")
            print(
                f"offline {rel} (not in manifest; recording current hash, fetched_at "
                "unknown)"
            )
            files[rel] = {
                "url": url,
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
                "fetched_at": None,
                "description": desc,
            }
            continue
        data = http_get(url)
        if url.startswith(BOP):  # sanity: the API returns JSON
            json.loads(data)
        old = sha256(path) if path.exists() else None
        path.write_bytes(data)
        new = sha256(path)
        status = "same" if old == new else ("new" if old is None else "CHANGED")
        print(f"fetch   {rel} [{status}]")
        files[rel] = {
            "url": url,
            "sha256": new,
            "bytes": len(data),
            "fetched_at": now_utc(),
            "description": desc,
        }
        if old is not None and old != new:
            files[rel]["replaced_sha256"] = old


def record_derived(manifest: dict, rel: str, derived_from: list[str]) -> None:
    path = OUT / rel
    manifest["files"][rel] = {
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
        "derived_from": derived_from,
        "generated_by": GENERATED_BY,
    }


def parse_xml(path: Path) -> ET.Element:
    s = path.read_text(encoding="utf-8")
    s = re.sub(r"<!DOCTYPE[^>]*>", "", s, count=1)
    return ET.fromstring(s)


def norm(s: str) -> str:
    return " ".join(s.split())


TEXT_TAGS = {"article-title", "title", "p", "label", "td", "th", "caption"}


def flatten_xml(root: ET.Element) -> str:
    """One line per text block, prefixed by its element path (e.g. [/body/sec/p])."""
    lines: list[str] = []

    def walk(el: ET.Element, path: list[str]) -> None:
        tag = el.tag.split("}")[-1]
        here = path + [tag]
        if tag in TEXT_TAGS:
            t = norm("".join(el.itertext()))
            if t:
                lines.append(f"[/{'/'.join(here[1:])}] {t}")
            return
        for ch in el:
            walk(ch, here)

    walk(root, [])
    return "\n".join(lines) + "\n"


def pdf_text(path: Path, layout: bool = True) -> str:
    r = PdfReader(str(path))
    out = []
    for i, p in enumerate(r.pages, start=1):
        t = p.extract_text(extraction_mode="layout") if layout else p.extract_text()
        out.append(f"=== PAGE {i} ===\n{t}")
    return "\n".join(out) + "\n"


def need(pattern: str, text: str, flags: int = 0, what: str = "") -> re.Match:
    m = re.search(pattern, text, flags)
    if not m:
        raise SystemExit(f"pattern not found ({what or pattern!r}); source changed?")
    return m


def article_id(root: ET.Element, kind: str) -> str | None:
    meta = root.find("front/article-meta")
    for a in meta.findall("article-id"):
        if a.get("pub-id-type") == kind:
            return a.text
    return None


def body_paragraphs(root: ET.Element) -> list[str]:
    """Running-text paragraphs of the body, excluding tables, figures and boxed text."""
    out: list[str] = []

    def walk(el: ET.Element) -> None:
        for ch in el:
            if ch.tag in ("table-wrap", "fig", "boxed-text", "supplementary-material"):
                continue
            if ch.tag == "p":
                out.append(norm("".join(ch.itertext())))
            else:
                walk(ch)

    walk(root.find("body"))
    return out


def abstract_text(root: ET.Element) -> str:
    front = root.find("front")
    ab = front.find(".//abstract")
    return norm(" ".join(ab.itertext()))


# --------------------------------------------------------------------------- Aune 2016

AUNE_S14_COLS = [
    ("chd_incidence_or_mortality", "Coronary heart disease, incidence/mortality"),
    ("chd_incidence", "Coronary heart disease, incidence"),
    ("chd_mortality", "Coronary heart disease, mortality"),
    ("stroke_incidence_or_mortality", "Stroke, incidence/mortality"),
    ("stroke_incidence", "Stroke, incidence"),
    ("stroke_mortality", "Stroke, mortality"),
    ("cvd_incidence_or_mortality", "Cardiovascular disease, incidence/mortality"),
    ("cvd_incidence", "Cardiovascular disease, incidence"),
    ("cvd_mortality", "Cardiovascular disease, mortality"),
]
AUNE_S15_COLS = [
    ("total_cancer", "Total cancer"),
    ("all_cause_mortality", "All-cause mortality"),
    ("respiratory_disease_mortality", "Respiratory disease mortality"),
    ("diabetes_mortality", "Diabetes mortality"),
    ("neurodegenerative_disease_mortality", "Neurodegenerative disease mortality"),
]
CELL = re.compile(r"^(\d\.\d\d)(?:\s*\((\d\.\d\d)-(\d\.\d\d)\))?$")


def parse_layout_table(block: str, n_cols: int) -> tuple[list[dict], list[str]]:
    """Parse a layout-mode text block whose data rows start with g/d.

    Column start offsets are taken from the 'RR (95% CI)' header line, so blank cells
    (printed as empty space in the PDF) are detected by position rather than by order.
    """
    lines = block.splitlines()
    hdr = next(
        ln for ln in lines if ln.strip().startswith("g/d") and "RR (95% CI)" in ln
    )
    starts = [m.start() for m in re.finditer(r"RR \(95% CI\)", hdr)]
    if len(starts) != n_cols:
        raise SystemExit(f"expected {n_cols} columns, header has {len(starts)}")
    bounds = starts + [10_000]
    rows, pvals = [], []
    for ln in lines:
        s = ln.strip()
        m = re.match(r"^(\d+)\s", s)
        if s.startswith("pnonlinearity"):
            pvals = [
                ln[bounds[i] - 2 : bounds[i + 1] - 2].strip() for i in range(n_cols)
            ]
            continue
        if not m or ln.find(m.group(1)) >= starts[0]:
            continue
        g = int(m.group(1))
        cells = [ln[bounds[i] - 2 : bounds[i + 1] - 2].strip() for i in range(n_cols)]
        rows.append({"g": g, "cells": cells})
    return rows, pvals


def shape_warning(rows: list[dict]) -> dict:
    """Where each model-relevant curve bottoms out and what it does after (computed
    from the csv rows)."""
    out = {}
    for key in ("all_cause_mortality", "cvd_mortality", "cvd_incidence_or_mortality"):
        pts = sorted(
            (r["intake_g_per_day"], r["rr"]) for r in rows if r["outcome"] == key
        )
        rr_min = min(rr for _, rr in pts)
        out[key] = {
            "min_rr": rr_min,
            "min_at_g_per_day": [g for g, rr in pts if rr == rr_min],
            "last_point": {"g_per_day": pts[-1][0], "rr": pts[-1][1]},
            "monotone_nonincreasing": all(b[1] <= a[1] for a, b in zip(pts, pts[1:])),
        }
    out["note"] = (
        "The published curves are not monotone: RR bottoms out between 15 and 20 g/day "
        "and rises "
        "toward 28 g/day, the last tabulated intake."
    )
    return out


def build_aune(manifest: dict) -> None:
    xml_path = RAW / "aune2016_PMC5137221.xml"
    pdf_path = RAW / "aune2016_MOESM1_ESM.pdf"
    root = parse_xml(xml_path)
    (RAW / "aune2016_PMC5137221.txt").write_text(flatten_xml(root), encoding="utf-8")
    record_derived(
        manifest, "raw/aune2016_PMC5137221.txt", ["raw/aune2016_PMC5137221.xml"]
    )
    # plain extraction keeps figure axis labels and p-values that layout mode drops
    supp = pdf_text(pdf_path, layout=False)
    (RAW / "aune2016_MOESM1_ESM.txt").write_text(supp, encoding="utf-8")
    record_derived(
        manifest, "raw/aune2016_MOESM1_ESM.txt", ["raw/aune2016_MOESM1_ESM.pdf"]
    )

    reader = PdfReader(str(pdf_path))
    page_no = next(
        i
        for i, p in enumerate(reader.pages, start=1)
        if "Supplementary Table 14." in (p.extract_text() or "")
    )
    page = reader.pages[page_no - 1].extract_text(extraction_mode="layout")
    i14 = page.index("Supplementary Table 14.")
    i15 = page.index("Supplementary Table 15.")
    t14_title = norm(page[i14 : page.index("g/d", i14)].split("\n\n")[0])
    t15_title = norm(page[i15 : page.index("g/d", i15)].split("\n\n")[0])
    rows14, p14 = parse_layout_table(page[i14:i15], len(AUNE_S14_COLS))
    rows15, p15 = parse_layout_table(page[i15:], len(AUNE_S15_COLS))

    out_rows, blanks = [], []
    for table, rows, cols, pvals in (
        ("14", rows14, AUNE_S14_COLS, p14),
        ("15", rows15, AUNE_S15_COLS, p15),
    ):
        if [r["g"] for r in rows] != [0, 5, 10, 15, 20, 25, 28]:
            raise SystemExit(
                f"Table S{table}: unexpected intake rows {[r['g'] for r in rows]}"
            )
        for r in rows:
            for (key, _label), cell in zip(cols, r["cells"]):
                loc = (
                    f"Additional file 1, Supplementary Table {table} (PDF p. "
                    f"{page_no}), row {r['g']} g/d"
                )
                if cell in ("", "-"):
                    blanks.append(
                        f"{key} at {r['g']} g/d (Table S{table}: "
                        f"{'blank' if cell == '' else '-'})"
                    )
                    continue
                m = CELL.match(cell)
                if not m:
                    raise SystemExit(f"unparsed cell {cell!r} in Table S{table}")
                rr, lo, hi = m.groups()
                if r["g"] == 0 and (rr != "1.00" or lo):
                    raise SystemExit("reference row should be 1.00 without CI")
                out_rows.append(
                    {
                        "outcome": key,
                        "intake_g_per_day": r["g"],
                        "rr": float(rr),
                        "ci_low": float(lo) if lo else None,
                        "ci_high": float(hi) if hi else None,
                        "locator": loc
                        + (" (reference category)" if r["g"] == 0 else ""),
                    }
                )
    csv_path = OUT / "aune2016_nonlinear.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "outcome",
                "intake_g_per_day",
                "rr",
                "ci_low",
                "ci_high",
                "locator",
            ],
        )
        w.writeheader()
        for r in out_rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})
    record_derived(manifest, "aune2016_nonlinear.csv", ["raw/aune2016_MOESM1_ESM.pdf"])

    # ---- text statements from the main article (checked against the XML here)
    paras = body_paragraphs(root)
    abstract = abstract_text(root)

    def para_with(*needles: str) -> str:
        for p in paras:
            if all(n in p for n in needles):
                return p
        raise SystemExit(f"paragraph with {needles} not found")

    allcause = para_with("Fifteen cohort studies", "85,870 deaths")
    cvd = para_with("cardiovascular disease risk", "18,655 cases")
    chd = para_with("coronary heart disease risk", "12,331 cases")
    stroke = para_with("risk of stroke", "9272 cases")
    cancer = para_with("Nine cohort studies", "18,490 cancer cases")
    methods = para_with("restricted cubic splines")
    paf = para_with("Miettinen")
    discussion = para_with("5–6 servings per week")

    need(
        r"all-cause mortality, 0\.78 \(95% CI: 0\.72–0\.84",
        abstract,
        what="Aune all-cause per 28 g",
    )
    need(
        r"cardiovascular disease, 0\.79 \(95% CI: 0\.70–0\.88",
        abstract,
        what="Aune CVD per 28 g",
    )
    need(
        (
            r"P nonlinearity < 0\.0001\), with a steeper reduction in risk at lower "
            r"intakes"
        ),
        allcause,
    )
    need(
        (
            r"no further reduction in risk above 15–20 grams per day \(Fig\. 4b, "
            r"Additional file 1: Table S15\)"
        ),
        allcause,
    )
    need(
        (
            r"P nonlinearity = 0\.001\), with a reduction in risk observed up to an "
            r"intake of approximately 15 g/d"
        ),
        cvd,
    )
    need(
        (
            r"but no further reductions with higher intakes \(Fig\. 3b, Additional "
            r"file 1: Table S14\)"
        ),
        cvd,
    )
    need(
        (
            r"P nonlinearity < 0\.0001, with only slight further reductions in risk "
            r"above 15–20 grams per day"
        ),
        chd,
    )
    need(r"slight positive association at intakes of 30 grams per day", stroke)
    need(
        (
            r"no evidence of a nonlinear association between nut intake and total "
            r"cancer \(P nonlinearity = 0\.11\)"
        ),
        cancer,
    )
    need(r"three knots at 10%, 50%, and 90% percentiles", methods)
    need(r"We used 20 grams per day as the optimal intake", paf)
    need(r"approximately 15–20 grams per day or 5–6 servings per week", discussion)

    # Supplementary figure axis ranges, used to decide what "peanuts" in the S14/S15
    # titles means
    fig41 = need(
        (
            r"Supplementary Figure 41\. Peanuts and all-cause mortality, nonlinear "
            r"dose-response analysis(.{0,400}?)Peanut consumption \(g/d\)"
        ),
        supp,
        re.S,
    )
    fig41_axis = [
        int(x) for x in re.findall(r"\b(\d+)\b", fig41.group(1).split("RR")[-1])
    ]
    fig38 = need(
        (
            r"Supplementary Figure 38\. Tree nuts and all-cause mortality, nonlinear "
            r"dose-response analysis(.{0,400}?)Tree nut consumption \(g/d\)"
        ),
        supp,
        re.S,
    )
    fig38_axis = [
        int(x) for x in re.findall(r"\b(\d+)\b", fig38.group(1).split("RR")[-1])
    ]
    peanut_p = {
        "Supplementary Figure 41 (peanuts, all-cause)": need(
            r"Supplementary Figure 41\..{0,200}?pnonlinearity\s*([<=]\s*[\d.]+)",
            supp,
            re.S,
        ).group(1),
        "Supplementary Figure 49 (peanuts, respiratory)": need(
            r"Supplementary Figure 49\..{0,200}?pnonlinearity\s*([<=]\s*[\d.]+)",
            supp,
            re.S,
        ).group(1),
        "Supplementary Figure 55 (peanuts, diabetes)": need(
            r"Supplementary Figure 55\..{0,200}?pnonlinearity\s*([<=]\s*[\d.]+)",
            supp,
            re.S,
        ).group(1),
        "Supplementary Figure 61 (peanuts, neurodegenerative)": need(
            r"Supplementary Figure 61\..{0,200}?pnonlinearity\s*([<=]\s*[\d.]+)",
            supp,
            re.S,
        ).group(1),
        "Supplementary Figure 34 (peanuts, total cancer)": need(
            r"Supplementary Figure 34\..{0,200}?pnonlinearity\s*([<=]\s*[\d.]+)",
            supp,
            re.S,
        ).group(1),
    }
    us_paf = need(
        (
            r"United States\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+"
            r"([\d.]+)\s+(\d+)\s+([\d.]+)\s+(\d+)"
        ),
        supp,
    )

    notes = {
        "source": {
            "citation": (
                "Aune D, Keum N, Giovannucci E, et al. Nut consumption and risk of "
                "cardiovascular disease, "
                "total cancer, all-cause and cause-specific mortality: a systematic "
                "review and dose-response "
                "meta-analysis of prospective studies. BMC Medicine 2016;14:207."
            ),
            "doi": "10.1186/s12916-016-0730-3",
            "pmid": article_id(root, "pmid"),
            "pmcid": article_id(root, "pmcid") or "PMC5137221",
            "files": ["raw/aune2016_PMC5137221.xml", "raw/aune2016_MOESM1_ESM.pdf"],
            "checked_on": TODAY,
        },
        "what_the_csv_holds": (
            "Every numeric point of the nonlinear (restricted cubic spline) "
            "dose-response for total nuts that "
            "the paper reports in numbers: Additional file 1, Supplementary Tables 14 "
            "and 15, RR (95% CI) at "
            "0, 5, 10, 15, 20, 25 and 28 g/day versus 0 g/day. All-cause mortality and "
            "CVD mortality are the "
            "rows the model uses; CHD, stroke, total cancer, respiratory, diabetes and "
            "neurodegenerative rows "
            "are kept because they come from the same tables. The main-text curves "
            "(Figs 2b, 2d, 3b, 3d, 4b) "
            "are images only and were not digitized."
        ),
        # opening words only (quotes stay under 15 words)
        "table_titles_as_printed": {
            "S14": " ".join(t14_title.split()[:14]) + " ...",
            "S15": " ".join(t15_title.split()[:14]) + " ...",
        },
        "table_title_discrepancy": (
            "Both table titles say 'peanuts', but the tables are the total-nut "
            "nonlinear results: (1) the "
            "main text cites Table S14 for the total-nut CHD, stroke and CVD curves "
            "and Table S15 for the "
            "total-nut all-cause curve (Results, all-cause and CVD paragraphs); (2) "
            "the tables run to 28 g/day, "
            "while the peanut all-cause spline (Supplementary Figure 41) has an x "
            f"axis of {fig41_axis} g/day "
            f"(tree nuts, Figure 38: {fig38_axis}); (3) the tables' P-nonlinearity "
            "values do not match the "
            "peanut figures (see peanut_figure_p_nonlinearity). The S14 title also "
            "lists total cancer and "
            "all-cause mortality, which are in S15. Treat the tables as total nuts; "
            "the title is a labeling error."
        ),
        "peanut_figure_p_nonlinearity": peanut_p,
        "p_nonlinearity_in_tables": {
            "S14": dict(zip([k for k, _ in AUNE_S14_COLS], p14)),
            "S15": dict(zip([k for k, _ in AUNE_S15_COLS], p15)),
        },
        "p_nonlinearity_in_main_text": {
            "all_cause_mortality": "< 0.0001 (Results, all-cause paragraph)",
            "cvd_incidence_or_mortality": (
                "0.001 (Results, CVD paragraph); Table S14 prints < 0.0001"
            ),
            "chd_incidence_or_mortality": "< 0.0001 (Results, CHD paragraph)",
            "stroke_incidence_or_mortality": "< 0.0001 (Results, stroke paragraph)",
            "total_cancer": "0.11 (Results, cancer paragraph); Table S15 prints 0.003",
        },
        "blank_cells_not_reported": blanks,
        "text_statements": [
            {
                "outcome": "all_cause_mortality",
                "statement": (
                    "Nonlinear; steeper risk reduction at lower intakes and no further "
                    "reduction above 15-20 g/day."
                ),
                "locator": (
                    "Results, 'Nuts and all-cause mortality' paragraph; Fig. 4b; "
                    "Additional file 1 Table S15"
                ),
            },
            {
                "outcome": "cvd_incidence_or_mortality",
                "statement": (
                    "Nonlinear; risk falls up to about 15 g/day with no further "
                    "reduction at higher intakes."
                ),
                "locator": (
                    "Results, cardiovascular disease paragraph; Fig. 3b; Additional "
                    "file 1 Table S14"
                ),
            },
            {
                "outcome": "chd_incidence_or_mortality",
                "statement": (
                    "Nonlinear; only slight further reductions above 15-20 g/day."
                ),
                "locator": (
                    "Results, coronary heart disease paragraph; Fig. 2b; Table S14"
                ),
            },
            {
                "outcome": "stroke_incidence_or_mortality",
                "statement": (
                    "Slight J shape: reductions up to about 10-15 g/day, slight "
                    "positive association at 30 g/day."
                ),
                "locator": "Results, stroke paragraph; Fig. 2d; Table S14",
            },
            {
                "outcome": "total_cancer",
                "statement": (
                    "No evidence of nonlinearity in the Results (P = 0.11), though the "
                    "Discussion lists cancer among nonlinear outcomes."
                ),
                "locator": (
                    "Results, total cancer paragraph; Discussion, first paragraph"
                ),
            },
            {
                "outcome": "all outcomes",
                "statement": (
                    "Most of the risk reduction occurs up to about 15-20 g/day (5-6 "
                    "servings a week)."
                ),
                "locator": "Discussion, first paragraph",
            },
            {
                "outcome": "population attributable fraction",
                "statement": (
                    "The authors took 20 g/day as the optimal intake for "
                    "attributable-death estimates, "
                    "citing little further reduction above it."
                ),
                "locator": "Methods, statistical methods, attributable-risk paragraph",
            },
        ],
        "method": (
            "Restricted cubic splines with three knots at the 10th, 50th and 90th "
            "percentiles of intake, "
            "combined by multivariate meta-analysis; nonlinearity tested by likelihood "
            "ratio (Methods, "
            "statistical methods). Reference is 0 g/day. One serving = 28 g."
        ),
        "shape_warning_for_model": shape_warning(out_rows),
        "linear_per_28g_for_context": {
            "all_cause_mortality": {
                "rr": 0.78,
                "ci": [0.72, 0.84],
                "locator": "Abstract; Results; Table 1",
            },
            "cvd": {
                "rr": 0.79,
                "ci": [0.70, 0.88],
                "locator": "Abstract; Results; Table 1",
            },
        },
        "us_attributable_fraction_below_20g": {
            "chd_pct": float(us_paf.group(1)),
            "total_cancer_pct": float(us_paf.group(3)),
            "respiratory_pct": float(us_paf.group(5)),
            "diabetes_pct": float(us_paf.group(7)),
            "all_cause_pct": float(us_paf.group(9)),
            "all_cause_deaths_2013": int(us_paf.group(10)),
            "locator": "Additional file 1, Supplementary Table 23, United States row",
        },
    }
    npath = OUT / "aune2016_nonlinear_notes.yaml"
    npath.write_text(
        yaml.safe_dump(notes, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    record_derived(
        manifest,
        "aune2016_nonlinear_notes.yaml",
        ["raw/aune2016_PMC5137221.xml", "raw/aune2016_MOESM1_ESM.pdf"],
    )
    print(
        f"wrote   aune2016_nonlinear.csv ({len(out_rows)} rows), "
        "aune2016_nonlinear_notes.yaml"
    )


# ----------------------------------------------------------------- IHME Burden of Proof


def curve_summary(rows: list[dict]) -> dict:
    rr_min = min(r["rr_mean"] for r in rows)
    flat_from = next(
        r["exposure_g_per_day"] for r in rows if r["rr_mean"] - rr_min < 1e-3
    )

    def at(g: float) -> dict:
        return min(rows, key=lambda r: abs(r["exposure_g_per_day"] - g))

    return {
        "min_rr_mean": round(rr_min, 4),
        "rr_mean_within_0.001_of_min_from_g_per_day": round(flat_from, 2),
        "rr_at_grid_point_nearest_p85": {
            k: round(at(rows[0]["exposure_p85_g_per_day"])[k], 4)
            for k in (
                "exposure_g_per_day",
                "rr_mean",
                "rr_inner_low",
                "rr_inner_high",
                "rr_outer_low",
                "rr_outer_high",
            )
        },
        "note": (
            "Computed from the csv. The mean curve falls to its floor within the first "
            "10 g/day and is flat "
            "from there to 100 g/day, well past the 85th percentile of exposure."
        ),
    }


def build_bop(manifest: dict) -> None:
    d = RAW / "ihme_bop"
    tag = f"r{BOP_RISK}_c{BOP_CAUSE}"
    meta = json.loads((d / f"risk_cause_metadata_{tag}.json").read_text())
    outer = json.loads((d / f"output_data_{tag}.json").read_text())
    inner = json.loads((d / f"fixed_effect_data_{tag}.json").read_text())
    comp = json.loads((d / "comparison.json").read_text())
    studies = json.loads((d / f"study_data_{tag}.json").read_text())
    risk_tree = json.loads((d / "metadata_risk.json").read_text())

    pair = [c for c in comp if c["rei_id"] == BOP_RISK and c["cause_id"] == BOP_CAUSE]
    if len(pair) != 1:
        raise SystemExit("risk-cause pair not found in /comparison")
    pair = pair[0]
    if (
        pair["rei_name"] != "Diet low in nuts and seeds"
        or pair["cause_name"] != "Ischemic heart disease"
    ):
        raise SystemExit(
            f"unexpected names {pair['rei_name']!r} / {pair['cause_name']!r}"
        )
    if (
        abs(pair["score"] - meta["score"]) > 1e-12
        or pair["star_rating"] != meta["star_rating"]
    ):
        raise SystemExit(
            "score/star mismatch between /comparison and /risk_cause_metadata"
        )

    def find_risk(nodes):
        for n in nodes:
            if n.get("rei_id") == BOP_RISK:
                return n
            hit = find_risk(n.get("children", []))
            if hit:
                return hit
        return None

    risk_node = find_risk(risk_tree)
    strata = {
        (r["sex_name"], r["age_group_name"], r["location_name"], r["category_id"])
        for r in outer
    }
    if len(strata) != 1:
        raise SystemExit(f"expected a single stratum, got {strata}")
    inner_by = {round(r["risk"], 9): r for r in inner}
    rows = []
    for o in outer:
        k = round(o["risk"], 9)
        i = inner_by[k]
        if abs(i["log_cause"] - o["log_cause"]) > 1e-9:
            raise SystemExit("inner and outer mean curves differ")
        rows.append(
            {
                "exposure_g_per_day": o["risk"],
                "rr_mean": o["linear_cause"],
                "rr_inner_low": min(i["linear_cause_lower"], i["linear_cause_upper"]),
                "rr_inner_high": max(i["linear_cause_lower"], i["linear_cause_upper"]),
                "rr_outer_low": min(o["linear_cause_lower"], o["linear_cause_upper"]),
                "rr_outer_high": max(o["linear_cause_lower"], o["linear_cause_upper"]),
                "log_rr_mean": o["log_cause"],
                "star_rating": meta["star_rating"],
                "ros": meta["score"],
                "exposure_p15_g_per_day": meta["risk_lower"],
                "exposure_p85_g_per_day": meta["risk_upper"],
                "risk_unit": meta["risk_unit"],
                "within_p15_p85": meta["risk_lower"] <= o["risk"] <= meta["risk_upper"],
            }
        )
    if len(rows) != len(inner):
        raise SystemExit("grid mismatch between output_data and fixed_effect_data")
    path = OUT / "ihme_bop_nuts_seeds_ihd.csv"
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    record_derived(
        manifest,
        "ihme_bop_nuts_seeds_ihd.csv",
        [
            f"raw/ihme_bop/output_data_{tag}.json",
            f"raw/ihme_bop/fixed_effect_data_{tag}.json",
            f"raw/ihme_bop/risk_cause_metadata_{tag}.json",
            "raw/ihme_bop/comparison.json",
        ],
    )

    obs = [s for s in studies]
    notes = {
        "source": (
            "IHME Burden of Proof visualization API, https://vizhub.healthdata.org/"
            "burden-of-proof/"
        ),
        "fetched": {
            k: v["fetched_at"]
            for k, v in manifest["files"].items()
            if k.startswith("raw/ihme_bop/")
        },
        "pair": {
            "rei_id": BOP_RISK,
            "rei_name": pair["rei_name"],
            "rei_name_short": pair["rei_name_short"],
            "revised_name": (risk_node or {}).get("revised_name"),
            "cause_id": BOP_CAUSE,
            "cause_name": pair["cause_name"],
        },
        "exposure_includes_seeds": True,
        "exposure_includes_seeds_basis": (
            "The risk factor is named 'Diet low in nuts and seeds' (revised name "
            "'Nuts and seeds consumption') in /comparison and /metadata/risk. The API "
            "gives no further exposure definition."
        ),
        "stratum": dict(
            zip(["sex", "age_group", "location", "category"], next(iter(strata)))
        ),
        "star_rating": meta["star_rating"],
        "ros": meta["score"],
        "star_rating_bands": (
            "Front end text (burden-of-proof main JS bundle): 1 star = negative ROS; 2 "
            "stars = "
            "ROS 0-0.14 (average excess risk 0-15%)."
        ),
        "ros_definition": (
            "Front end text: ROS is the mean log RR of the Burden of Proof risk "
            "function between the "
            "15th and 85th percentiles of exposure in the data."
        ),
        "exposure_range": {
            "p15_g_per_day": meta["risk_lower"],
            "p85_g_per_day": meta["risk_upper"],
            "basis": (
                "risk_lower/risk_upper from /risk_cause_metadata, drawn as the '15th "
                "percentile' "
                "and '85th percentile' bounds by the front end"
            ),
        },
        "ui_definitions": {
            "outer": (
                "output_data lower/upper; the front end labels this 'Fixed & random "
                "effects uncertainty' "
                "(includes between-study heterogeneity)."
            ),
            "inner": (
                "fixed_effect_data lower/upper; labeled 'Fixed effects uncertainty'. "
                "Its lower/upper fields "
                "are ordered by log value sign, so the csv takes min and max."
            ),
        },
        "grid": {
            "points": len(rows),
            "min": rows[0]["exposure_g_per_day"],
            "max": rows[-1]["exposure_g_per_day"],
        },
        "curve_summary": curve_summary(rows),
        "input_data": {
            "observations": len(obs),
            "studies": len({s["study_id"] for s in obs}),
            "outliers": sum(bool(s["is_outlier"]) for s in obs),
            "collection_methods": sorted({s["collection_method"] for s in obs}),
            "max_exposure_upper_g_per_day": max(s["risk_upper"] for s in obs),
        },
    }
    p = OUT / "ihme_bop_nuts_seeds_ihd_notes.yaml"
    p.write_text(
        yaml.safe_dump(notes, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    record_derived(
        manifest,
        "ihme_bop_nuts_seeds_ihd_notes.yaml",
        [f"raw/ihme_bop/{n}" for n in sorted(x.name for x in d.iterdir())],
    )
    print(
        f"wrote   ihme_bop_nuts_seeds_ihd.csv ({len(rows)} rows), "
        "ihme_bop_nuts_seeds_ihd_notes.yaml"
    )


# -------------------------------------------------------------------------- Fadnes 2022

UI = r"([\d.]+) \(([-\d.]+);([-\d.]+)\)"

# Forest-plot values drawn as text inside the PNG supporting figures (no
# machine-readable
# source exists). Transcribed by reading each image on 2026-09-23; flagged in the yaml.
FIGURE_TRANSCRIPTIONS = {
    # file: (sex, age, {"0->25": (est, lo, hi), "0->12.5": (est, lo, hi)})
    "raw/fadnes2022_s012.png": (
        "female",
        20,
        "S6 Fig",
        {"0->25": (1.7, 1.5, 2.0), "0->12.5": (0.8, 0.7, 0.9)},
    ),
    "raw/fadnes2022_s013.png": (
        "male",
        20,
        "S7 Fig",
        {"0->25": (2.0, 1.7, 2.3), "0->12.5": (1.0, 0.8, 1.2)},
    ),
    "raw/fadnes2022_s014.png": (
        "female",
        40,
        "S8 Fig",
        {"0->25": (1.6, 1.4, 1.8), "0->12.5": (0.8, 0.7, 0.9)},
    ),
    "raw/fadnes2022_s015.png": (
        "male",
        40,
        "S9 Fig",
        {"0->25": (1.8, 1.5, 2.0), "0->12.5": (0.8, 0.7, 0.9)},
    ),
    "raw/fadnes2022_s016.png": (
        "female",
        60,
        "S10 Fig",
        {"0->25": (1.2, 1.1, 1.4), "0->12.5": (0.6, 0.5, 0.7)},
    ),
    "raw/fadnes2022_s017.png": (
        "male",
        60,
        "S11 Fig",
        {"0->25": (1.3, 1.1, 1.5), "0->12.5": (0.6, 0.5, 0.7)},
    ),
    "raw/fadnes2022_s018.png": (
        "female",
        80,
        "S12 Fig",
        {"0->25": (0.5, 0.4, 0.6), "0->12.5": (0.3, 0.2, 0.4)},
    ),
    "raw/fadnes2022_s019.png": (
        "male",
        80,
        "S13 Fig",
        {"0->25": (0.5, 0.4, 0.6), "0->12.5": (0.2, 0.1, 0.3)},
    ),
}


def build_fadnes(manifest: dict) -> None:
    root = parse_xml(RAW / "fadnes2022_PMC8824353.xml")
    (RAW / "fadnes2022_PMC8824353.txt").write_text(flatten_xml(root), encoding="utf-8")
    record_derived(
        manifest, "raw/fadnes2022_PMC8824353.txt", ["raw/fadnes2022_PMC8824353.xml"]
    )
    abstract = abstract_text(root)
    paras = body_paragraphs(root)
    body = "\n".join(paras)

    # correction: confirm it only concerns the funding statement
    corr = parse_xml(RAW / "fadnes2022_correction_PMC8956181.xml")
    corr_body = norm("".join(corr.find("body").itertext())).split("Reference")[0]
    need(r"missing from the Funding statement", corr_body, what="correction scope")
    if re.search(r"\b(Table|Fig|hazard|years)\b", corr_body, re.I):
        raise SystemExit("correction mentions results; review it")

    # abstract: nut-specific gains
    m = need(
        (
            r"nuts \(females: ([\d.]+) \[95% UI ([\d.]+) to ([\d.]+)\]; males: "
            r"([\d.]+) \[95% UI ([\d.]+) to ([\d.]+)\]\)"
        ),
        abstract,
        what="abstract nut gains",
    )
    abs_f = [float(x) for x in m.groups()[:3]]
    abs_m = [float(x) for x in m.groups()[3:]]

    # methods: intakes, phase-in, uncertainty, mortality source
    mi = need(
        r"Nuts: TW ([\d.]+) g, FA ([\d.]+) g, and OD ([\d.]+) g \(([^)]*)\)",
        body,
        what="nut intakes",
    )
    tw, fa, od = (float(x) for x in mi.groups()[:3])
    need(
        (
            r"time to full effect was 10 years with a gradual, linear increase in "
            r"effect \(e\.g\., the effect was 20% of maximum after 2 years\)"
        ),
        body,
        what="phase-in",
    )
    need(
        r"sensitivity analyses with 5 years, 30 years, and 50 years to full effect",
        body,
    )
    need(
        (
            r"using a uniform distribution, we drew a number between the upper and "
            r"lower 95% confidence interval"
        ),
        body,
    )
    need(r"repeated 200 times \(with a fixed seed as starting point\)", body)
    need(r"2\.5 and 97\.5 percentiles", body)
    need(r"We used mortality rates extracted from GBD 2019 \(published in 2020\)", body)
    need(
        (
            r"Data on background mortality from 2019 for specific countries and "
            r"regions were obtained from the freely available GBD cause of death "
            r"database"
        ),
        body,
    )
    need(
        (
            r"total mortality rates in 5-year age groups were also available from "
            r"GBD\. These were converted to single-year age-specific mortality rates"
        ),
        body,
    )
    need(
        (
            r"mortality rates after the age when the diet is changed are multiplied "
            r"with the hazard rate corresponding to the change"
        ),
        body,
    )
    need(
        (
            r"Each of the food groups were considered as individual protective or risk "
            r"factors"
        ),
        body,
    )
    need(
        (
            r"The optimized diet \(OD\) values were set where dose–response data on "
            r"consumption indicated no additional mortality gain"
        ),
        body,
    )
    need(
        (
            r"typical Western diet” \(TW\) based on consumption data from the United "
            r"States and Europe \(S3 Text\)"
        ),
        body,
    )
    need(r"NutriGrade.{0,300}nuts \(7\)", body, re.S)
    need(r"Stata SE 17\.0", body)

    # Table 1: US life expectancy by diet
    tbl = None
    for tw_el in root.iter("table-wrap"):
        lab = tw_el.find("label")
        if lab is not None and norm("".join(lab.itertext())) == "Table 1":
            tbl = tw_el
    cells = [norm("".join(td.itertext())) for td in tbl.iter("td")]
    i_us = cells.index("United States")
    us = {}
    for k in range(
        4
    ):  # rows: [age, 10 values]; the region label appears only on the first row
        row = cells[i_us + 1 + k * 11 : i_us + 1 + (k + 1) * 11]
        age = int(row[0])
        vals = [float(x) for x in row[1:]]
        us[age] = {
            "LE_typical_male": vals[0],
            "LE_typical_female": vals[1],
            "LE_feasible_male": vals[2],
            "gain_feasible_male": vals[3],
            "LE_feasible_female": vals[4],
            "gain_feasible_female": vals[5],
            "LE_optimized_male": vals[6],
            "gain_optimized_male": vals[7],
            "LE_optimized_female": vals[8],
            "gain_optimized_female": vals[9],
        }
    if sorted(us) != [20, 40, 60, 80]:
        raise SystemExit(f"Table 1 US ages parsed as {sorted(us)}")

    # S1 Table: hazard-ratio grid for nuts (plain extraction keeps the row on one line)
    s1 = PdfReader(str(RAW / "fadnes2022_s004.pdf")).pages[0].extract_text()
    grid_hdr = (
        need(r"Grams\n([\d ]+)\n", s1, what="S1 Table grams header").group(1).split()
    )
    grid = [int(x) for x in grid_hdr]
    nut = need(
        (
            r"\nNuts ([\d, ]+?) (\d+) (\d+) Aune\. Nut consumption and risk of "
            r"cardiovascular disease"
        ),
        s1,
        what="S1 nuts row",
    )
    hr_vals = [float(x.replace(",", ".")) for x in nut.group(1).split()]
    unc_thr, noest_thr = int(nut.group(2)), int(nut.group(3))
    mid = need(
        r"BMC Med 2016.*?\n- Mid to upper/lower ([\d, ]+)\n",
        s1,
        re.S,
        what="S1 nuts half-widths",
    )
    half = [float(x.replace(",", ".")) for x in mid.group(1).split()]
    if hr_vals[0] != 1.0 or len(hr_vals) != 5 or len(half) != 4:
        raise SystemExit(f"S1 nuts row parsed as {hr_vals} / {half}")
    nut_grid = grid[: len(hr_vals)]
    hr_at = dict(zip(nut_grid, hr_vals))
    half_at = dict(zip(nut_grid[1:], half))
    pat = need(
        (
            r"BMC Med 201626 Pea nuts 2600 0,25 (\d+) (\d+) (\d+) (\d+) (\d+) (\d+) "
            r"(\d+) (\d+)"
        ),
        s1,
        what="S1 nut intakes",
    )
    s1_std, _, s1_opt, _, s1_nor, _, s1_us, _ = (int(x) for x in pat.groups())
    if s1_std != tw or s1_opt != od:
        raise SystemExit("S1 Table nut intakes disagree with Methods")

    # S2 Table: nut row, ages 20 and 60
    s2 = (
        PdfReader(str(RAW / "fadnes2022_s005.pdf"))
        .pages[0]
        .extract_text(extraction_mode="layout")
    )
    r = need(
        r"\n\s*Nuts\s+(\d+)\s+([\d.]+)\s+(\d+)\s+" + r"\s+".join([UI] * 8),
        s2,
        what="S2 nuts row",
    )
    g = r.groups()
    if (float(g[0]), float(g[1]), float(g[2])) != (tw, fa, od):
        raise SystemExit("S2 Table nut intakes disagree with Methods")
    vals = [tuple(float(x) for x in g[3 + 3 * j : 6 + 3 * j]) for j in range(8)]
    order = [
        ("female", 20, "FA"),
        ("female", 20, "OD"),
        ("male", 20, "FA"),
        ("male", 20, "OD"),
        ("female", 60, "FA"),
        ("female", 60, "OD"),
        ("male", 60, "FA"),
        ("male", 60, "OD"),
    ]
    s2_nuts = {k: v for k, v in zip(order, vals)}
    tot = need(r"\n\s*Total\s+" + r"\s+".join([UI] * 8), s2, what="S2 total row")
    tot_vals = [
        tuple(float(x) for x in tot.groups()[3 * j : 3 * j + 3]) for j in range(8)
    ]
    s2_total = {k: v for k, v in zip(order, tot_vals)}

    # S3 Table: time-to-full-effect sensitivity (whole optimized diet, not nut-specific)
    s3 = (
        PdfReader(str(RAW / "fadnes2022_s006.pdf"))
        .pages[0]
        .extract_text(extraction_mode="layout")
    )
    s3_rows = {}
    for mm in re.finditer(
        (
            r"\n\s*(20|40|60|80)\s+(Female|Male)\s+([\d.]+)\s+(-?[\d.]+)\s+(-?"
            r"[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)"
        ),
        s3,
    ):
        s3_rows[(mm.group(2).lower(), int(mm.group(1)))] = {
            "optimized_diet_gain": float(mm.group(3)),
            "abs_change_vs_10y": {
                "T=5": float(mm.group(5)),
                "T=30": float(mm.group(6)),
                "T=50": float(mm.group(7)),
            },
        }
    if len(s3_rows) != 8:
        raise SystemExit("S3 Table parse")

    # S3 Text: US estimated nut intake (not what the model used as TW)
    s3t = PdfReader(str(RAW / "fadnes2022_s003.pdf")).pages[0].extract_text()
    us_nuts = float(need(r"United States:.*?Nuts: ([\d.]+) g", s3t, re.S).group(1))

    # cross-checks between sources
    if (s2_nuts[("female", 20, "OD")] != tuple(abs_f)) or (
        s2_nuts[("male", 20, "OD")] != tuple(abs_m)
    ):
        raise SystemExit("abstract and S2 Table nut gains disagree")
    fig_vs_table = []
    for f, (sex, age, lab, v) in FIGURE_TRANSCRIPTIONS.items():
        if age not in (20, 60):
            continue
        for ch, diet in (("0->25", "OD"), ("0->12.5", "FA")):
            tab, fig = s2_nuts[(sex, age, diet)], v[ch]
            if fig[0] != tab[0]:
                raise SystemExit(
                    f"{lab} transcription disagrees with S2 Table point estimate"
                )
            if fig != tab:
                fig_vs_table.append(
                    f"{lab} {sex} {age} {ch}: figure {fig}, S2 Table {tab}"
                )

    # Johansson 2020 life-table details
    jroot = parse_xml(RAW / "johansson2020_PMC7360045.xml")
    jtext = "\n".join(
        norm("".join(e.itertext())) for e in jroot.iter() if e.tag in ("p", "td")
    )
    need(r"5-year age groups to age 95", jtext)
    need(
        (
            r"we assume that the rates \(or disability weights\) are the same for each "
            r"single-year age in the aggregate age groups"
        ),
        jtext,
    )
    need(r"we use Y = 99", jtext)
    need(r"setting the chance of surviving from age Y to Y\+1 to zero", jtext)
    need(r"q = 1 − exp\(−MAll causes\)", jtext)

    loc_s2 = "S2 Table (pmed.1003889.s005), Nuts row"
    targets = {
        "source": {
            "key": "fadnes2022food",
            "citation": (
                "Fadnes LT, Økland J-M, Haaland ØA, Johansson KA. Estimating impact of "
                "food choices on "
                "life expectancy: A modeling study. PLoS Medicine 2022;19(2):e1003889."
            ),
            "doi": "10.1371/journal.pmed.1003889",
            "pmid": article_id(root, "pmid"),
            "pmcid": "PMC8824353",
            "correction": {
                "doi": "10.1371/journal.pmed.1003962",
                "pmcid": "PMC8956181",
                "scope": "Adds a missing funding statement only; no numbers changed.",
            },
            "files": sorted(
                k for k in manifest["files"] if k.startswith("raw/fadnes2022_")
            ),
            "checked_on": TODAY,
        },
        "main_target": {
            "description": (
                "Life-expectancy gain from a sustained change in nuts alone from the "
                "typical "
                "Western intake to the optimized intake, starting at age 20, United "
                "States, 10-year "
                "linear phase-in (S2 Table reports each food-group change separately)."
            ),
            "intake_change_g_per_day": {"from": tw, "to": od},
            "male": {
                "years": s2_nuts[("male", 20, "OD")][0],
                "ui95_low": s2_nuts[("male", 20, "OD")][1],
                "ui95_high": s2_nuts[("male", 20, "OD")][2],
            },
            "female": {
                "years": s2_nuts[("female", 20, "OD")][0],
                "ui95_low": s2_nuts[("female", 20, "OD")][1],
                "ui95_high": s2_nuts[("female", 20, "OD")][2],
            },
            "locator": "Abstract (Methods and findings); "
            + loc_s2
            + ", TW->OD at age 20; S6 and S7 Figs",
            "value_checked_in": "full text and supplementary table",
        },
        "all_nut_gains_table": [
            {
                "sex": sex,
                "start_age": age,
                "change": (
                    "0->25 (optimized)" if diet == "OD" else "0->12.5 (feasibility)"
                ),
                "years": v[0],
                "ui95_low": v[1],
                "ui95_high": v[2],
                "locator": f"{loc_s2}, TW->{diet}, age {age}",
                "value_checked_in": "supplementary table (PDF text)",
            }
            for (sex, age, diet), v in s2_nuts.items()
        ]
        + [
            {
                "sex": sex,
                "start_age": age,
                "change": (
                    "0->25 (optimized)" if ch == "0->25" else "0->12.5 (feasibility)"
                ),
                "years": est,
                "ui95_low": lo,
                "ui95_high": hi,
                "locator": (
                    f"{lab} ({Path(f).name.replace('fadnes2022_', 'pmed.1003889.')}), "
                    "Nuts row"
                ),
                "value_checked_in": "figure image, read visually (text drawn in PNG)",
            }
            for f, (sex, age, lab, v) in FIGURE_TRANSCRIPTIONS.items()
            if age in (40, 80)
            for ch, (est, lo, hi) in v.items()
        ],
        "figure_vs_table_differences": fig_vs_table,
        "figure_vs_table_note": (
            "The S14/S15 Fig legends say admetan made some intervals symmetric, so the "
            "S2 "
            "Table is used where both exist; figures supply ages 40 and 80 only."
        ),
        "nut_intakes_g_per_day": {
            "typical_western": tw,
            "feasibility": fa,
            "optimized": od,
            "optimized_description": mi.group(4),
            "locator": (
                "Methods, list of TW/FA/OD intakes; S1 Table columns 'Sliders start' "
                "and 'Optimized'; S2 Table"
            ),
            "note": (
                f"S3 Text estimates US intake at {us_nuts:g} g/day (S1 Table 'US, mean "
                f"intake' {s1_us}), but the "
                "model's typical Western diet uses 0 g/day for nuts."
            ),
            "us_estimated_intake_g_per_day": us_nuts,
        },
        "relative_risk": {
            "measure": (
                "HR for all-cause mortality versus 0 g/day, read off a grid by intake"
            ),
            "grid_g_per_day": nut_grid,
            "hr": [hr_at[x] for x in nut_grid],
            "half_width_to_95ci": {str(k): v for k, v in half_at.items()},
            "hr_at_optimal_25g": hr_at[25],
            "ci95_at_25g": [
                round(hr_at[25] - half_at[25], 4),
                round(hr_at[25] + half_at[25], 4),
            ],
            "uncertain_above_g_per_day": unc_thr,
            "no_estimate_above_g_per_day": noest_thr,
            "source": (
                "Aune et al. 2016 BMC Medicine (Fadnes ref 4); S1 Table 'Publication' "
                "column"
            ),
            "applied_to": (
                "All-cause mortality (Methods: mortality rates multiplied by the "
                "hazard ratio for the change)"
            ),
            "locator": (
                "S1 Table (pmed.1003889.s004), Nuts row and the 'Mid to upper/lower' "
                "row beneath it"
            ),
            "value_checked_in": (
                "supplementary table (PDF text; column alignment confirmed on the "
                "rendered page)"
            ),
            "match_to_aune": (
                "Aune 2016 Table S15 all-cause RR at 25 g/day is 0.84 (0.82-0.85); "
                "Fadnes uses 0.84 +/- 0.02. "
                "The 50, 100 and 150 g/day HRs lie beyond Aune's 28 g/day table and "
                "are Fadnes's own "
                "extension (flagged orange, 'uncertain', in S1 Table)."
            ),
            "feasibility_hr_not_stated": (
                "The HR used for 12.5 g/day is not printed. The feasibility gains are "
                "about "
                "half the optimized gains (S2 Table). That fits interpolating the S1 "
                "Table "
                "grid between 0 and 25 g/day (HR about 0.92), not Aune's curve, which "
                "is "
                "already 0.84 at 10 g/day. Inference only; the paper does not say."
            ),
        },
        "phase_in": {
            "years_to_full_effect": 10,
            "shape": "linear; 20% of the full effect after 2 years",
            "sensitivities_years": [5, 30, 50],
            "locator": (
                "Methods, time-to-full-effect paragraph; Results, S3 Table paragraph"
            ),
            "whole_diet_sensitivity_S3_Table": {
                f"{s}_{a}": v for (s, a), v in s3_rows.items()
            },
            "note": (
                "S3 Table reports the time-to-full-effect sensitivity for the whole "
                "optimized diet only, not for nuts."
            ),
        },
        "mortality_data": {
            "source": (
                "GBD 2019 (published 2020), IHME GBD results tool / cause of death "
                "database (Fadnes ref 12)"
            ),
            "year": 2019,
            "measure": (
                "all-cause mortality rates for the United States, 5-year age groups, "
                "converted to single years"
            ),
            "baseline_assumption": (
                "GBD population mortality is treated as the typical-Western-diet "
                "mortality; Table 1 "
                "labels the GBD-based life expectancy as the typical Western diet LE."
            ),
            "locator": (
                "Methods, paragraphs on GBD mortality and background mortality; Table 1"
            ),
            "typical_diet_LE_us": {
                f"age_{a}": {
                    "male": v["LE_typical_male"],
                    "female": v["LE_typical_female"],
                }
                for a, v in us.items()
            },
            "typical_diet_LE_locator": (
                "Table 1, United States rows, Typical Western LE columns"
            ),
        },
        "life_table_method": {
            "summary": (
                "Standard life table; LE(D) - LE(D0) with age-specific mortality rates "
                "after the change age "
                "multiplied by the food group's hazard ratio."
            ),
            "locator": "Methods, LE(D) definition paragraphs",
            "details_from_cited_method": {
                "citation": (
                    "Johansson KA, Økland J-M, Skaftun EK, et al. Estimating Health "
                    "Adjusted Age at Death (HAAD). "
                    "PLoS One 2020;15(7):e0235955 (Fadnes ref 13; PMC7360045)"
                ),
                "age_groups": (
                    "GBD 5-year groups to 95+; each single year in a group gets the "
                    "group's rate"
                ),
                "q_from_rate": "q = 1 - exp(-M_all_causes)",
                "max_age": "Y = 99; survival from 99 to 100 set to zero",
                "locator": (
                    "Johansson 2020, Methods (single-year conversion; lifetable "
                    "paragraph) and Table 1"
                ),
                "caveat": (
                    "Fadnes defers to this paper for the background-LE method but does "
                    "not restate these "
                    "choices, so their use in Fadnes 2022 is inferred."
                ),
            },
            "not_stated_in_fadnes": [
                (
                    "whether the HR multiplies the rate before converting to q "
                    "(Johansson's q = 1 - exp(-M) suggests so)"
                ),
                "within-year timing of deaths (mid-year or other) for the LE sum",
                "whether the phase-in scales the HR linearly or the log HR",
                "the HR at 12.5 g/day (feasibility diet)",
                "how the 95+ group is split into single years for rates",
            ],
        },
        "uncertainty_method": {
            "draws": 200,
            "distribution": (
                "uniform between the lower and upper 95% CI of each food group's HR"
            ),
            "interval": "2.5th and 97.5th percentiles; fixed seed",
            "locator": "Methods, uncertainty paragraph",
        },
        "other_choices": {
            "food_groups_independent": (
                "Each food group treated as an independent protective or risk factor; "
                "the "
                "per-food gains are single-food changes, and the whole-diet total is "
                "smaller "
                "than their sum (S2 Table), consistent with multiplied hazard ratios."
            ),
            "optimal_intake_rule": (
                "Optimized intake set where the dose-response showed no further "
                "mortality gain."
            ),
            "nutrigrade_nuts": 7,
            "sensitivity_hr_adjustment": (
                "HRa = HR0 + (1 - HR0)(1 - m), m in 0.5-1.5, reported as "
                "sensitivity-adjusted "
                "intervals (S15 Fig)."
            ),
            "software": (
                "Web calculator built with R Shiny (food4healthylife.org); graphs and "
                "forest plots in Stata SE 17.0 (admetan)"
            ),
            "locator": "Methods",
        },
        "whole_diet_context": {
            "optimized_gain_age20": {
                "male": list(s2_total[("male", 20, "OD")]),
                "female": list(s2_total[("female", 20, "OD")]),
            },
            "feasibility_gain_age20": {
                "male": list(s2_total[("male", 20, "FA")]),
                "female": list(s2_total[("female", 20, "FA")]),
            },
            "locator": "S2 Table, Total row; Abstract; Table 1",
        },
    }
    p = OUT / "fadnes2022_targets.yaml"
    p.write_text(
        yaml.safe_dump(targets, sort_keys=False, allow_unicode=True, width=100),
        encoding="utf-8",
    )
    record_derived(
        manifest,
        "fadnes2022_targets.yaml",
        sorted(
            [
                k
                for k in manifest["files"]
                if k.startswith("raw/fadnes2022_") and not k.endswith(".txt")
            ]
            + ["raw/johansson2020_PMC7360045.xml"]
        ),
    )
    print("wrote   fadnes2022_targets.yaml")


# --------------------------------------------------------------------------- main


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--refresh", action="store_true", help="re-download every file")
    ap.add_argument("--offline", action="store_true", help="never touch the network")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    manifest["source"] = (
        "Aune 2016 (BMC Med 14:207), IHME Burden of Proof API (rei 114 x cause 493), "
        "Fadnes 2022 (PLoS Med 19:e1003889) and Johansson 2020 (PLoS One 15:e0235955)"
    )
    manifest["generated_by"] = GENERATED_BY
    fetch_all(manifest, args.refresh, args.offline)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    )  # keep fetch record even if parsing fails
    build_aune(manifest)
    build_bop(manifest)
    build_fadnes(manifest)
    manifest["files"] = {
        k: manifest["files"][k] for k in sorted(manifest["files"]) if (OUT / k).exists()
    }
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(f"wrote   MANIFEST.json ({len(manifest['files'])} files)")


if __name__ == "__main__":
    sys.exit(main())
