#!/usr/bin/env python3
"""Check every DOI the paper relies on against Crossref.

Collects each DOI in data/evidence.yaml (``source.doi``) and paper/references.bib
(``doi`` fields, which include paper/extra.bib), looks each one up on Crossref,
and compares the record with every local claim about it:

* the DOI must resolve (online) or have a cached record (``--offline``, which
  reads data/sources/crossref/, written by scripts/fetch_evidence_sources.py);
* the title must match: token-set similarity of at least 0.9 (Jaccard index of
  the two sets of words after normalizing case, punctuation, diacritics, Greek
  letters and markup), taking the better of Crossref's title with and without
  its subtitle;
* the first author must match: Crossref's first author (family name, or the
  organization name) and the local first author, normalized the same way, must
  be equal or one must contain the other's words.

Exits 1 when any check fails. Sources without a DOI are listed but not checked.

    python scripts/check_citations.py            # online (default)
    python scripts/check_citations.py --offline  # cached records only
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
EVIDENCE = ROOT / "data" / "evidence.yaml"
BIB = ROOT / "paper" / "references.bib"
CACHE = ROOT / "data" / "sources" / "crossref"
CROSSREF_URL = "https://api.crossref.org/works/{doi}"
USER_AGENT = "whatnut-paper citation checker (https://github.com/MaxGhenis/whatnut)"
TITLE_THRESHOLD = 0.9

GREEK = {
    "α": "alpha",
    "β": "beta",
    "γ": "gamma",
    "δ": "delta",
    "ε": "epsilon",
    "κ": "kappa",
    "λ": "lambda",
    "μ": "mu",
    "ω": "omega",
}


# --------------------------------------------------------------------------
# Normalization and comparison
# --------------------------------------------------------------------------


def tokens(s: str | None) -> list[str]:
    """Lowercase ASCII words: markup, entities, diacritics and punctuation removed."""
    if not s:
        return []
    s = html.unescape(re.sub(r"<[^>]+>", " ", str(s)))
    s = s.replace("{", "").replace("}", "")  # BibTeX case protection
    s = s.replace("&", " and ")
    s = "".join(GREEK.get(c, c) for c in s.lower())
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.findall(r"[a-z0-9]+", s)


def title_similarity(a: str | None, b: str | None) -> float:
    """Jaccard index of the two titles' word sets (1.0 = same words)."""
    ta, tb = set(tokens(a)), set(tokens(b))
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def authors_match(local: str | None, crossref: str | None) -> bool:
    la, cr = tokens(local), tokens(crossref)
    if not la or not cr:
        return False
    return la == cr or set(la) <= set(cr) or set(cr) <= set(la)


def crossref_titles(msg: dict) -> list[str]:
    titles = [t for t in (msg.get("title") or []) if t]
    subtitles = [s for s in (msg.get("subtitle") or []) if s]
    out = list(titles)
    for t in titles:
        out.extend(f"{t}: {s}" for s in subtitles)
    return out


def crossref_first_author(msg: dict) -> str | None:
    authors = msg.get("author") or []
    first = [a for a in authors if a.get("sequence") == "first"] or authors
    if not first:
        return None
    a = first[0]
    return a.get("family") or a.get("name") or a.get("given")


# --------------------------------------------------------------------------
# Local claims
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Claim:
    origin: str  # where the claim comes from, for the report
    doi: str
    title: str | None
    first_author: str | None


def norm_doi(doi) -> str | None:
    if not doi:
        return None
    doi = str(doi).strip()
    return re.sub(r"^(https?://(dx\.)?doi\.org/|doi:)", "", doi, flags=re.I)


def evidence_claims(path: Path = EVIDENCE) -> tuple[list[Claim], list[str]]:
    rows = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    claims, no_doi = [], []
    for row in rows:
        src = row.get("source") or {}
        doi = norm_doi(src.get("doi"))
        origin = f"evidence.yaml:{row.get('id', '?')}"
        if not doi:
            no_doi.append(f"{origin} ({src.get('key', 'no key')})")
            continue
        claims.append(Claim(origin, doi, src.get("title"), src.get("first_author")))
    return claims, no_doi


ENTRY_RE = re.compile(r"@\s*(\w+)\s*\{")


def parse_bib(text: str) -> list[tuple[str, str, dict[str, str]]]:
    """(type, key, fields) for each brace-delimited entry; values keep inner braces."""
    entries = []
    i = 0
    while m := ENTRY_RE.search(text, i):
        j, depth = m.end(), 1
        while j < len(text) and depth:
            depth += {"{": 1, "}": -1}.get(text[j], 0)
            j += 1
        body, i = text[m.end() : j - 1], j
        etype = m.group(1).lower()
        if etype in ("comment", "string", "preamble"):
            continue
        key, _, rest = body.partition(",")
        entries.append((etype, key.strip(), _parse_fields(rest)))
    return entries


def _parse_fields(s: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    i = 0
    field_re = re.compile(r"\s*,?\s*([A-Za-z][\w-]*)\s*=\s*")
    while i < len(s):
        m = field_re.match(s, i)
        if not m:
            break
        name, j = m.group(1).lower(), m.end()
        if j < len(s) and s[j] == "{":
            depth, k = 1, j + 1
            while k < len(s) and depth:
                depth += {"{": 1, "}": -1}.get(s[k], 0)
                k += 1
            value, i = s[j + 1 : k - 1], k
        elif j < len(s) and s[j] == '"':
            k = s.index('"', j + 1)
            value, i = s[j + 1 : k], k + 1
        else:
            m2 = re.compile(r"[^,\s]+").match(s, j)
            value, i = (m2.group(0), m2.end()) if m2 else ("", j)
        fields[name] = " ".join(value.split())
    return fields


def bib_first_author(author_field: str | None) -> str | None:
    """Family name (or organization) of the first name in a BibTeX author list."""
    if not author_field:
        return None
    depth, cut = 0, len(author_field)
    for m in re.finditer(r"[{}]|\s+and\s+", author_field):
        tok = m.group(0)
        if tok == "{":
            depth += 1
        elif tok == "}":
            depth -= 1
        elif depth == 0:
            cut = m.start()
            break
    first = author_field[:cut].strip()
    if first.startswith("{") and _matching_brace(first) == len(first) - 1:
        return first[1:-1]  # {Organization, possibly with commas}
    if "," in first:
        return first.split(",", 1)[0].strip().replace("{", "").replace("}", "")
    words = first.replace("{", "").replace("}", "").split()
    return words[-1] if words else None


def _matching_brace(s: str) -> int:
    depth = 0
    for i, c in enumerate(s):
        depth += {"{": 1, "}": -1}.get(c, 0)
        if depth == 0:
            return i
    return -1


def bib_claims(path: Path = BIB) -> list[Claim]:
    if not path.exists():
        return []
    claims = []
    for _etype, key, fields in parse_bib(path.read_text(encoding="utf-8")):
        doi = norm_doi(fields.get("doi"))
        if doi:
            claims.append(
                Claim(
                    f"references.bib:{key}",
                    doi,
                    fields.get("title"),
                    bib_first_author(fields.get("author")),
                )
            )
    return claims


# --------------------------------------------------------------------------
# Crossref records
# --------------------------------------------------------------------------


class Lookup:
    """DOI -> Crossref ``message`` object, from the network or the local cache."""

    def __init__(self, offline: bool, cache_dir: Path = CACHE, pause: float = 0.2):
        self.offline = offline
        self.pause = pause
        self.cache: dict[str, Path] = {}
        if offline:
            for f in sorted(cache_dir.glob("*.json")):
                if f.name == "MANIFEST.json":
                    continue
                msg = _message(json.loads(f.read_text(encoding="utf-8")))
                if msg.get("DOI"):
                    self.cache[msg["DOI"].lower()] = f

    def get(self, doi: str) -> tuple[dict | None, str | None]:
        """(record, error)."""
        if self.offline:
            path = self.cache.get(doi.lower())
            if path is None:
                return (
                    None,
                    "no cached Crossref record (run scripts/fetch_evidence_sources.py)",
                )
            return _message(json.loads(path.read_text(encoding="utf-8"))), None
        url = CROSSREF_URL.format(doi=urllib.parse.quote(doi, safe="/:;()"))
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(5):
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    time.sleep(self.pause)
                    return _message(json.load(resp)), None
            except urllib.error.HTTPError as exc:
                if exc.code == 404:
                    return None, "DOI not found on Crossref (HTTP 404)"
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 4:
                    return None, f"Crossref HTTP {exc.code}"
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt == 4:
                    return None, f"Crossref unreachable: {exc}"
            time.sleep(2**attempt)
        return None, "Crossref lookup failed"


def _message(obj: dict) -> dict:
    return obj.get("message", obj) if isinstance(obj, dict) else {}


# --------------------------------------------------------------------------
# Check
# --------------------------------------------------------------------------


def check_claim(claim: Claim, msg: dict) -> list[str]:
    problems = []
    candidates = crossref_titles(msg)
    best = max((title_similarity(claim.title, t) for t in candidates), default=0.0)
    if best < TITLE_THRESHOLD:
        shown = candidates[0] if candidates else None
        problems.append(
            f"title similarity {best:.2f} < {TITLE_THRESHOLD}: "
            f"local {claim.title!r} vs Crossref {shown!r}"
        )
    cr_first = crossref_first_author(msg)
    if not authors_match(claim.first_author, cr_first):
        problems.append(
            f"first author: local {claim.first_author!r} vs Crossref {cr_first!r}"
        )
    return problems


def run(
    offline: bool, evidence: Path = EVIDENCE, bib: Path = BIB, cache_dir: Path = CACHE
) -> int:
    claims, no_doi = evidence_claims(evidence)
    claims += bib_claims(bib)
    by_doi: dict[str, list[Claim]] = {}
    for c in claims:
        by_doi.setdefault(c.doi.lower(), []).append(c)
    lookup = Lookup(offline, cache_dir)
    failures = 0
    mode = (
        "offline (data/sources/crossref/)" if offline else "online (api.crossref.org)"
    )
    print(f"Checking {len(by_doi)} DOIs from {len(claims)} claims, {mode}")
    for key in sorted(by_doi):
        group = by_doi[key]
        doi = group[0].doi
        msg, err = lookup.get(doi)
        if err:
            failures += 1
            print(f"FAIL {doi}: {err} [{', '.join(c.origin for c in group)}]")
            continue
        bad = [(c, p) for c in group for p in check_claim(c, msg)]
        if bad:
            failures += 1
            print(f"FAIL {doi}")
            for c, p in bad:
                print(f"       {c.origin}: {p}")
        else:
            print(f"ok   {doi} ({len(group)} claims)")
    if no_doi:
        print(
            f"note {len(no_doi)} evidence rows have no DOI and were not checked: "
            f"{', '.join(no_doi)}"
        )
    print(f"{failures} DOI(s) failed" if failures else "all DOIs resolve and match")
    return 1 if failures else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--offline",
        action="store_true",
        help="compare against data/sources/crossref/ instead of the network",
    )
    args = ap.parse_args(argv)
    return run(args.offline)


if __name__ == "__main__":
    sys.exit(main())
