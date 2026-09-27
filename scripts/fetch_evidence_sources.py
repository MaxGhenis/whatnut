"""Cache Crossref records (and optionally source texts) for data/evidence.yaml.

For every DOI in data/evidence.yaml (each row's source.doi) plus EXTRA_DOIS
(papers cited inside notes, such as the source of a trial's arm composition),
downloads https://api.crossref.org/works/<doi> and stores its "message" object,
re-serialized with sorted keys (the convention scripts/fetch_supporting_evidence.py
uses for the same folder), at

  data/sources/crossref/<doi with "/" replaced by "_">.json

and records url, sha256 (of the stored bytes), bytes and fetched_at per file in
data/sources/crossref/MANIFEST.json. Entries written by other fetchers are kept:
the manifest is re-read just before each write and only this script's entries change.

With --texts [DIR] (default DIR: data/sources/crossref/texts) it also downloads,
for each row's source, the PubMed record (efetch XML, abstract included) and,
when the row has a PMCID, the Europe PMC full-text XML (or, when Europe PMC has
no full text, the PMC article page), plus the EXTRA_TEXTS below (figures and
supplements that hold numbers the rows cite), into DIR with its own
MANIFEST.json (url, sha256, bytes, fetched_at). These texts are what the checker
reads to verify estimates; they are not needed by the model.

Rerun:  .venv/bin/python scripts/fetch_evidence_sources.py
        .venv/bin/python scripts/fetch_evidence_sources.py --missing-only
        .venv/bin/python scripts/fetch_evidence_sources.py --texts
        .venv/bin/python scripts/fetch_evidence_sources.py --texts /some/dir
        .venv/bin/python scripts/fetch_evidence_sources.py --check   (offline:
            compare cached Crossref title and first author with evidence.yaml)
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import subprocess
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "data" / "evidence.yaml"
CROSSREF_DIR = ROOT / "data" / "sources" / "crossref"
MANIFEST = CROSSREF_DIR / "MANIFEST.json"
CROSSREF_URL = "https://api.crossref.org/works/{doi}"
EFETCH_URL = (
    "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
    "?db=pubmed&id={pmid}&retmode=xml&tool=whatnut"
)
EPMC_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
PMC_HTML_URL = "https://pmc.ncbi.nlm.nih.gov/articles/{pmcid}/"
HEADERS = {
    "User-Agent": (
        "whatnut-paper evidence fetcher (https://github.com/MaxGhenis/whatnut)"
    )
}
# pmc.ncbi.nlm.nih.gov article pages return 403 to python-requests whatever the headers
# (observed 2026-09-23) but serve curl; the fallback below shells out to curl.
CURL_UA = "Mozilla/5.0"

# DOIs cited in notes rather than as a row's primary source.
EXTRA_DOIS = [
    # Sala-Vila et al. 2016 JAHA: PREDIMED nut-arm composition (walnut/hazelnut/almond
    # grams)
    "10.1161/JAHA.115.002543",
]

TEXTS_DIR = ROOT / "data" / "sources" / "crossref" / "texts"
EPMC_SUPP_URL = (
    "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/supplementaryFiles"
)

# Extra verification files: (saved name, kind, argument).
#   epmc_xml      Europe PMC full-text XML for a PMCID
#   pmc_figure    a figure image from a PMC article page; argument is "PMCID:filename"
#                 (the CDN path is read from the article page because it is not stable)
#   epmc_supp     one member of Europe PMC's supplementary-files zip; "PMCID:member"
EXTRA_TEXTS = [
    # PREDIMED nut-arm composition and olive-oil amount (Methods, 'Dietary Intake')
    ("salavila2016predimed_epmc_PMC4859371.xml", "epmc_xml", "PMC4859371"),
    # CTT 2010 Figure 5: cause-specific mortality per 1 mmol/L, with event counts
    ("ctt2010ldl_PMC2988224_figure5_gr5.jpg", "pmc_figure", "PMC2988224:gr5.jpg"),
    # Schwingshackl 2021 web appendix: Supplementary Figures 9 and 12 (pairs per
    # stratum)
    (
        "schwingshackl2021agreement_PMC8441535_supplement.pdf",
        "epmc_supp",
        "PMC8441535:schl063523.ww.pdf",
    ),
]


def doi_filename(doi: str) -> str:
    return doi.replace("/", "_") + ".json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_rows() -> list[dict]:
    if not EVIDENCE.exists():
        return []
    rows = yaml.safe_load(EVIDENCE.read_text()) or []
    return [r for r in rows if isinstance(r, dict)]


def row_dois(rows: list[dict]) -> list[str]:
    seen: list[str] = []
    for r in rows:
        doi = ((r.get("source") or {}).get("doi") or "").strip()
        if doi and doi not in seen:
            seen.append(doi)
    for doi in EXTRA_DOIS:
        if doi not in seen:
            seen.append(doi)
    return seen


def load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {"files": {}}


def merge_manifest(path: Path, entries: dict) -> None:
    """Re-read the manifest, update only `entries`, write it back (shared with other
    fetchers)."""
    manifest = load_manifest(path)
    manifest.setdefault("files", {}).update(entries)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n")


def get_with_curl(url: str) -> bytes:
    proc = subprocess.run(
        ["curl", "-sSfL", "--max-time", "120", "-A", CURL_UA, url],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError(
            f"{url}: curl exit {proc.returncode} {proc.stderr.decode()[:200]}"
        )
    # Under repeated requests PMC answers with a reCAPTCHA challenge page instead of the
    # article (observed 2026-09-23). Never store it over a good copy; rerun later
    # instead.
    if (
        b"recaptcha/challengepage" in proc.stdout
        or b"RecaptchaChallengePageUi" in proc.stdout
    ):
        raise RuntimeError(
            f"{url}: PMC served a reCAPTCHA challenge page; kept any existing copy, "
            "rerun later"
        )
    return proc.stdout


def get(url: str, tries: int = 4, headers: dict | None = None) -> bytes:
    last = None
    for i in range(tries):
        try:
            resp = requests.get(url, headers=headers or HEADERS, timeout=60)
            if resp.status_code == 200:
                return resp.content
            last = f"HTTP {resp.status_code}"
        except requests.RequestException as exc:  # network hiccup: retry
            last = str(exc)
        time.sleep(2 * (i + 1))
    raise RuntimeError(f"{url}: {last}")


def fetch_crossref(dois: list[str], missing_only: bool) -> None:
    CROSSREF_DIR.mkdir(parents=True, exist_ok=True)
    known = load_manifest(MANIFEST)["files"]
    entries: dict = {}
    for doi in dois:
        name = doi_filename(doi)
        path = CROSSREF_DIR / name
        if missing_only and path.exists() and name in known:
            continue
        url = CROSSREF_URL.format(doi=doi)
        msg = json.loads(get(url))["message"]
        if msg.get("DOI", "").lower() != doi.lower():
            raise RuntimeError(f"Crossref returned {msg.get('DOI')} for {doi}")
        data = (json.dumps(msg, indent=1, sort_keys=True) + "\n").encode()
        path.write_bytes(data)
        entries[name] = {
            "url": url,
            "sha256": sha256(data),
            "bytes": len(data),
            "fetched_at": now(),
        }
        print(f"crossref {doi}: {(msg.get('title') or [''])[0][:70]}")
        time.sleep(0.5)
    if entries:
        merge_manifest(MANIFEST, entries)


def fetch_texts(rows: list[dict], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    mpath = outdir / "MANIFEST.json"
    entries: dict = {}
    done: set[str] = set()

    def save(name: str, url: str, data: bytes) -> None:
        (outdir / name).write_bytes(data)
        entries[name] = {
            "url": url,
            "sha256": sha256(data),
            "bytes": len(data),
            "fetched_at": now(),
        }
        print(f"text {name} ({len(data)} bytes)")

    for r in rows:
        src = r.get("source") or {}
        key, pmid, pmcid = src.get("key"), src.get("pmid"), src.get("pmcid")
        if pmid and pmid not in done:
            done.add(pmid)
            url = EFETCH_URL.format(pmid=pmid)
            try:
                save(f"{key}_pubmed_{pmid}.xml", url, get(url))
            except RuntimeError as exc:
                print(f"skip pubmed {pmid}: {exc}", file=sys.stderr)
            time.sleep(0.4)
        if pmcid and pmcid not in done:
            done.add(pmcid)
            # Europe PMC serves JATS XML for open-access articles; for others (author
            # manuscripts, Cochrane) fall back to the PMC article page, which carries
            # the text.
            url = EPMC_URL.format(pmcid=pmcid)
            try:
                save(f"{key}_epmc_{pmcid}.xml", url, get(url, tries=1))
            except RuntimeError:
                url = PMC_HTML_URL.format(pmcid=pmcid)
                try:
                    save(f"{key}_pmc_{pmcid}.html", url, get_with_curl(url))
                except RuntimeError as exc:
                    print(f"skip {pmcid}: {exc}", file=sys.stderr)
            time.sleep(0.4)
    for name, kind, arg in EXTRA_TEXTS:
        try:
            url, data = fetch_extra(kind, arg)
        except (RuntimeError, KeyError, zipfile.BadZipFile) as exc:
            print(f"skip {name}: {exc}", file=sys.stderr)
            continue
        save(name, url, data)
        time.sleep(0.4)
    merge_manifest(mpath, entries)


def fetch_extra(kind: str, arg: str) -> tuple[str, bytes]:
    """Download one EXTRA_TEXTS item; returns (source url, bytes)."""
    if kind == "epmc_xml":
        url = EPMC_URL.format(pmcid=arg)
        return url, get(url)
    if kind == "pmc_figure":
        pmcid, fname = arg.split(":", 1)
        page = get_with_curl(PMC_HTML_URL.format(pmcid=pmcid)).decode("utf-8", "ignore")
        hits = sorted(
            set(
                re.findall(
                    r"https://cdn\.ncbi\.nlm\.nih\.gov/pmc/blobs/[^\"'\s]+/"
                    + re.escape(fname),
                    page,
                )
            )
        )
        if not hits:
            raise RuntimeError(f"{fname} not found on the {pmcid} article page")
        return hits[0], get_with_curl(hits[0])
    if kind == "epmc_supp":
        pmcid, member = arg.split(":", 1)
        url = EPMC_SUPP_URL.format(pmcid=pmcid)
        with zipfile.ZipFile(io.BytesIO(get(url))) as zf:
            return f"{url}#{member}", zf.read(member)
    raise RuntimeError(f"unknown kind {kind}")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def check(rows: list[dict]) -> int:
    """Offline comparison of each row's title / first author against its cached
    Crossref record."""
    bad = 0
    for r in rows:
        src = r.get("source") or {}
        doi = src.get("doi")
        if not doi:
            print(f"{r['id']}: no DOI")
            bad += 1
            continue
        path = CROSSREF_DIR / doi_filename(doi)
        if not path.exists():
            print(f"{r['id']}: no cached Crossref record for {doi}")
            bad += 1
            continue
        rec = json.loads(path.read_text())
        msg = rec.get(
            "message", rec
        )  # accept a raw /works response or its message object
        title_ok = _norm((msg.get("title") or [""])[0]) == _norm(src.get("title", ""))
        authors = msg.get("author") or []
        first = authors[0] if authors else {}
        cr_first = first.get("family") or first.get("name") or ""
        author_ok = _norm(src.get("first_author", "")) in _norm(cr_first) or _norm(
            cr_first
        ) in _norm(src.get("first_author", ""))
        status = "ok" if (title_ok and author_ok) else "MISMATCH"
        if status != "ok":
            bad += 1
        print(
            f"{status:8} {r['id']}: title={title_ok} first_author={author_ok} "
            f"(crossref: {cr_first!r})"
        )
    return bad


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--missing-only", action="store_true", help="skip DOIs already cached"
    )
    ap.add_argument(
        "--texts",
        type=Path,
        nargs="?",
        const=TEXTS_DIR,
        help=(
            "also download PubMed/Europe PMC texts and EXTRA_TEXTS into this "
            f"directory (default {TEXTS_DIR.relative_to(ROOT)})"
        ),
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="offline title/first-author check against the cache",
    )
    args = ap.parse_args()
    rows = load_rows()
    if args.check:
        sys.exit(1 if check(rows) else 0)
    fetch_crossref(row_dois(rows), args.missing_only)
    if args.texts:
        fetch_texts(rows, args.texts)


if __name__ == "__main__":
    main()
