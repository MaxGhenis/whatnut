"""Fetch the primary sources behind the supporting evidence rows, and Crossref records.

Builder A1b ("supporting rows" in data/evidence.yaml). This script only downloads
and caches; the rows themselves are written by hand from what the sources say, and
each row's `locator` points into a file cached here.

Writes:
  data/sources/crossref/<doi with / replaced by _>.json
      Crossref /works/<doi> message
  data/sources/crossref/primary/<name>
      PubMed XML, PMC/Europe PMC full-text XML, publisher PDFs, agency pages and
      data tables
  data/sources/crossref/MANIFEST.json
      url, sha256, bytes, fetched_at for every file above

Rerun:
  .venv/bin/python scripts/fetch_supporting_evidence.py             fetch missing files
  .venv/bin/python scripts/fetch_supporting_evidence.py --refetch   refetch everything
  .venv/bin/python scripts/fetch_supporting_evidence.py --offline   verify sha256 only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "sources" / "crossref"
PRIMARY = OUT / "primary"
MANIFEST = OUT / "MANIFEST.json"

UA = {"User-Agent": "whatnut-paper/0.1 (https://github.com/MaxGhenis/whatnut)"}
# pmc.ncbi.nlm.nih.gov article pages and some agency sites return a stub to non-browser
# agents
BROWSER_UA = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
}
CROSSREF = "https://api.crossref.org/works/{doi}"
PUBMED = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={pmid}&"
    "retmode=xml"
)
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

# Every DOI cited by a supporting row. Crossref JSON is cached for each.
DOIS: list[str] = [
    "10.1093/ije/dyv365",  # Eslamparast 2017 Golestan
    "10.1016/j.jacc.2017.09.035",  # Guasch-Ferre 2017 JACC
    "10.3390/nu13082699",  # Liu 2021 walnut life expectancy
    "10.1093/ije/dyv039",  # van den Brandt 2015 NLCS
    "10.1001/jamainternmed.2014.8347",  # Luu 2015 SCCS/SWHS/SMHS
    "10.1038/s41598-024-85070-z",  # Wang 2025 MR
    "10.1093/ajcn/nqy091",  # Guasch-Ferre 2018 walnut lipids
    "10.1093/advances/nmz043",  # Lee-Bravatti 2019 almond
    "10.1080/10408398.2021.2018569",  # Hadi 2023 pistachio
    "10.1186/s13098-026-02212-1",  # Zhang 2026 pecan
    "10.3390/nu8120747",  # Perna 2016 hazelnut
    "10.1093/jn/138.4.761",  # Griel 2008 macadamia
    "10.1017/jns.2023.39",  # Jones 2023 macadamia
    "10.1016/j.ctim.2020.102387",  # Jalali 2020 cashew
    "10.1080/10408398.2018.1558395",  # Jafari Azad 2020 peanut
    "10.1089/acm.2011.0443",  # Nieman 2012 chia
    "10.1007/s11746-000-0038-0",  # Malcolmson 2000 milled flax storage
    "10.1016/j.foodchem.2015.02.017",  # Schlormann 2015 roasting
    "10.7326/0003-4819-147-4-200708210-00175",  # Stranges 2007 NPC diabetes
    "10.2903/j.efsa.2023.7704",  # EFSA 2023 selenium UL
    "10.17226/9810",  # IOM 2000 DRI vitamin C, E, selenium, carotenoids
]

# name -> url. PubMed records for every PMID, open full text where it exists,
# and the non-journal primary sources (agency pages, data tables, PDFs).
PMIDS = {
    "eslamparast2017": "26946539",
    "guaschferre2017": "29145952",
    "liu2021": "34444859",
    "vandenbrandt2015": "26066329",
    "luu2015": "25730101",
    "wang2025": "39755742",
    "guaschferre2018": "29931130",
    "leebravatti2019": "31243439",
    "hadi2023": "34933637",
    "zhang2026": "42298717",
    "perna2016": "27897978",
    "griel2008": "18356332",
    "jones2023": "37180485",
    "jalali2020": "32444052",
    "jafariazad2020": "30638042",
    "nieman2012": "22830971",
    "schlormann2015": "25766804",
    "stranges2007": "17620655",
}
# Open full text. Europe PMC serves JATS XML for the open-access subset; for
# author manuscripts and publisher-restricted PMC records it returns HTTP 500, so
# those come from NCBI efetch (db=pmc) when it includes the <body>, else the PMC
# article HTML page.
PMC_ARTICLE = "https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
NCBI_PMC = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id={num}"
PMCIDS = {  # name -> (pmcid, route) ; route in {"europepmc", "ncbi", "html"}
    "eslamparast2017": ("PMC5837191", "html"),
    "guaschferre2017": ("PMC5762129", "ncbi"),
    "liu2021": ("PMC8401409", "europepmc"),
    "luu2015": ("PMC4474488", "ncbi"),
    "wang2025": ("PMC11700201", "europepmc"),
    "guaschferre2018": ("PMC6862936", "html"),
    "leebravatti2019": ("PMC6855931", "html"),
    "zhang2026": ("PMC13501812", "europepmc"),
    "perna2016": ("PMC5188407", "europepmc"),
    "jones2023": ("PMC10173088", "europepmc"),
}
ARS = "https://www.ars.usda.gov/ARSUserFiles/80400530/pdf"
OTHER: dict[str, str] = {
    # Vidrih et al. 2012, Food Technol Biotechnol 50(4):454-460 (publisher PDF).
    # Crossref has
    # no DOI for it: the journal's Crossref deposits start in 2014.
    "vidrih2012_ftb_50_4_454.pdf": (
        "https://www.ftb.com.hr/images/pdfarticles/2012/October-December/"
        "ftb%204-2012%20-%20454-460.pdf"
    ),
    "ftb_2012_50_4_toc.pdf": (
        "https://www.ftb.com.hr/images/pdfarticles/2012/October-December/"
        "ftb%204-2012%20-%20toc%20vol%2050.pdf"
    ),
    # Jalali et al. 2020 (cashew), authors' accepted manuscript, University of Sussex
    # deposit on figshare
    # (figshare article 23307119); the Elsevier version is paywalled.
    "jalali2020_cashew_accepted_manuscript.pdf": (
        "https://ndownloader.figshare.com/files/41092598"
    ),
    # IOM 2000 DRI report (doi 10.17226/9810), chapter 7 "Selenium", NAP online reader
    # page
    "nap_9810_chapter9_selenium.html": (
        "https://nap.nationalacademies.org/read/9810/chapter/9"
    ),
    # USDA ARS What We Eat in America, NHANES 2017-March 2020 Prepandemic, day 1, Table
    # 1s.
    # These PDFs are owner-password encrypted; read them with `pdftotext -layout`.
    "wweia_1720_table1_nutrients.pdf": f"{ARS}/1720/Table_1_NIN_GEN_1720.pdf",
    "fped_1720_table1_food_patterns.pdf": f"{ARS}/fped/Table_1_FPED_GEN_1720.pdf",
    # FPED 2017-2018 Methodology and User Guide (defines 1 oz-eq of nuts = 1/2 oz =
    # 14.175 g);
    # the 2017-March 2020 FPED documentation is an addendum to it.
    "fped_1718_methodology.pdf": f"{ARS}/fped/FPED_1718.pdf",
    "fped_1720_documentation_addendum.pdf": (
        f"{ARS}/fped/FPED%20for%20Use%20with%20WWEIA%20NHANES%202017-March%202020%20Pre"
        "pandemic%20Documentation.pdf"
    ),
    # FDA Compliance Policy Guides on aflatoxins (June 2021 revisions)
    "fda_cpg_570_375_peanuts.pdf": "https://www.fda.gov/media/72073/download",
    "fda_cpg_570_200_brazil_nuts.pdf": "https://www.fda.gov/media/72053/download",
    "fda_cpg_570_500_pistachios.pdf": "https://www.fda.gov/media/72084/download",
    "fda_cpg_555_400_human_food.pdf": "https://www.fda.gov/media/149666/download",
}
# The Brazil nut selenium row reads data/composition/raw/fdc_170569.json, which
# scripts/fetch_composition.py downloads and hashes; it is not duplicated here.


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def doi_file(doi: str) -> str:
    return doi.replace("/", "_") + ".json"


def targets() -> dict[str, str]:
    """relative path (under OUT) -> url"""
    t: dict[str, str] = {}
    for doi in DOIS:
        t[doi_file(doi)] = CROSSREF.format(doi=doi)
    for name, pmid in PMIDS.items():
        t[f"primary/pubmed_{pmid}_{name}.xml"] = PUBMED.format(pmid=pmid)
    for name, (pmcid, route) in PMCIDS.items():
        if route == "europepmc":
            t[f"primary/{pmcid}_{name}.xml"] = EUROPEPMC.format(pmcid=pmcid)
        elif route == "ncbi":
            t[f"primary/{pmcid}_{name}.xml"] = NCBI_PMC.format(num=pmcid[3:])
        else:
            t[f"primary/{pmcid}_{name}.html"] = PMC_ARTICLE.format(pmcid=pmcid)
    for fname, url in OTHER.items():
        t[f"primary/{fname}"] = url
    return t


def fetch(url: str) -> bytes:
    """API hosts via requests; other hosts via curl, because pmc.ncbi.nlm.nih.gov
    (and some agency sites) answer 403 to the requests TLS/HTTP client."""
    # figshare's downloader answers a browser user agent with an empty HTTP 202
    # challenge
    api = any(
        h in url
        for h in ("api.crossref.org", "eutils.ncbi", "europepmc", "figshare.com")
    )
    err = ""
    for attempt in range(4):
        try:
            if api:
                r = requests.get(url, headers=UA, timeout=90)
                if r.status_code == 200 and r.content:
                    return r.content
                err = f"HTTP {r.status_code}"
            else:
                cp = subprocess.run(
                    [
                        "curl",
                        "-sL",
                        "--fail",
                        "--max-time",
                        "120",
                        "-A",
                        BROWSER_UA["User-Agent"],
                        url,
                    ],
                    capture_output=True,
                )
                if cp.returncode == 0 and cp.stdout:
                    return cp.stdout
                err = f"curl exit {cp.returncode}"
        except requests.RequestException as e:  # pragma: no cover - network
            err = str(e)
        time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{url}: {err}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--offline", action="store_true", help="verify sha256 of cached files only"
    )
    ap.add_argument(
        "--refetch", action="store_true", help="refetch files already cached"
    )
    args = ap.parse_args()

    PRIMARY.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
    files = manifest.setdefault("files", {})
    updated: dict[
        str, dict
    ] = {}  # entries this run wrote; merged into the shared manifest at the end
    bad = 0
    for rel, url in targets().items():
        p = OUT / rel
        entry = files.get(rel)
        if args.offline or (p.exists() and entry and not args.refetch):
            if not p.exists() or not entry:
                print(f"MISSING {rel}")
                bad += 1
            elif sha256(p) != entry["sha256"]:
                print(f"SHA MISMATCH {rel}")
                bad += 1
            continue
        try:
            data = fetch(url)
        except RuntimeError as e:
            print(f"FAIL {e}")
            bad += 1
            continue
        if rel.endswith(".json") and not rel.startswith("primary/"):
            # store the Crossref message only, pretty-printed, so diffs are readable
            data = (
                json.dumps(json.loads(data)["message"], indent=1, sort_keys=True) + "\n"
            ).encode()
        p.write_bytes(data)
        updated[rel] = {
            "url": url,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
            "fetched_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        print(f"ok {rel} ({len(data)} bytes)")
        time.sleep(0.4)
    if updated:
        # The manifest is shared with scripts/fetch_evidence_sources.py: re-read it and
        # update only the entries written here, so concurrent runs do not drop each
        # other's rows.
        latest = (
            json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {"files": {}}
        )
        latest.setdefault("files", {}).update(updated)
        latest.setdefault(
            "note",
            (
                "Crossref records (<doi>.json, the API 'message' object re-serialized "
                "with sorted keys) "
                "and primary sources (primary/) for rows in data/evidence.yaml. sha256 "
                "is of the stored bytes."
            ),
        )
        MANIFEST.write_text(json.dumps(latest, indent=1, sort_keys=True) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
