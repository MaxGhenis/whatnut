"""Loaders for everything under data/.

Every file the model reads goes through :func:`checked_path`, which compares the
file's sha256 with the entry for it in the MANIFEST.json of its folder and records
(path, sha256) in :data:`READS`, so results.json can list exactly what was read.
``data/evidence.yaml`` has no manifest; its hash is recorded as read.

Evidence rows are read by id through :func:`row`, which records the id in
:data:`ROWS_USED` and refuses rows whose citation has not been verified.
"""

from __future__ import annotations

import csv
import functools
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
EVIDENCE = DATA / "evidence.yaml"

SEXES = ("female", "male")

# path relative to the repo root -> sha256, for every data file read in this process
READS: dict[str, str] = {}
# evidence row ids read in this process
ROWS_USED: set[str] = set()


class DataIntegrityError(RuntimeError):
    """A data file does not match its manifest, or an evidence row is unusable."""


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _manifest_entry(manifest: dict, rel: str) -> dict | None:
    """The manifest entry keyed by ``rel`` (the manifests nest entries under
    'files' or 'derived'); None if absent."""
    stack: list[Any] = [manifest]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            entry = node.get(rel)
            if isinstance(entry, dict) and isinstance(entry.get("sha256"), str):
                return entry
            stack.extend(node.values())
    return None


def checked_path(path: Path) -> Path:
    """``path`` after checking its sha256 against its folder's MANIFEST.json."""
    path = Path(path).resolve()
    digest = sha256(path)
    rel_root = path.relative_to(ROOT).as_posix()
    if path != EVIDENCE.resolve():
        folder = path.parent
        while True:
            manifest_path = folder / "MANIFEST.json"
            if manifest_path.exists():
                break
            if folder == DATA or folder == folder.parent:
                raise DataIntegrityError(f"{rel_root}: no MANIFEST.json above it")
            folder = folder.parent
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        rel = path.relative_to(folder).as_posix()
        entry = _manifest_entry(manifest, rel)
        if entry is None:
            raise DataIntegrityError(
                f"{rel_root} is not listed in {manifest_path.relative_to(ROOT)}"
            )
        if entry["sha256"] != digest:
            raise DataIntegrityError(
                f"{rel_root}: sha256 {digest} does not match the manifest "
                f"({entry['sha256']}); rerun the fetcher or update the manifest"
            )
    READS[rel_root] = digest
    return path


def manifest(folder: str) -> dict:
    """The MANIFEST.json of ``data/<folder>`` (metadata such as the source citation)."""
    return json.loads((DATA / folder / "MANIFEST.json").read_text(encoding="utf-8"))


def _read_csv(path: Path) -> list[dict[str, str]]:
    with open(checked_path(path), newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _float(s: str | None) -> float | None:
    return None if s in (None, "") else float(s)


# --------------------------------------------------------------------------
# Evidence rows
# --------------------------------------------------------------------------


def z_for(level: float) -> float:
    """Two-sided standard-normal quantile for an interval at ``level``."""
    return float(norm.ppf((1 + level) / 2))


@dataclass(frozen=True)
class EvidenceRow:
    id: str
    kind: str
    measure: str
    unit: str | None
    estimate: float | None
    ci_low: float | None
    ci_high: float | None
    ci_level: float | None
    pi_low: float | None
    pi_high: float | None
    support: str | None
    notes: str | None
    source: dict
    verified: dict
    exposure: str | None = None
    outcome: str | None = None
    population: str | None = None

    def _need(self, *names: str) -> None:
        missing = [n for n in names if getattr(self, n) is None]
        if missing:
            raise DataIntegrityError(f"evidence row {self.id} has no {missing}")

    def log_se(self) -> float:
        """SE of ln(estimate) from a ratio's confidence interval at its ci_level."""
        self._need("ci_low", "ci_high", "ci_level")
        return (math.log(self.ci_high) - math.log(self.ci_low)) / (
            2 * z_for(self.ci_level)
        )

    def log_se_pi(self) -> float:
        """SD of ln(ratio) across settings, from the prediction interval.

        The schema has no separate level for prediction intervals; Schwingshackl
        2021 reports 95% prediction intervals, the same level as the row's CI."""
        self._need("pi_low", "pi_high", "ci_level")
        return (math.log(self.pi_high) - math.log(self.pi_low)) / (
            2 * z_for(self.ci_level)
        )

    def se(self) -> float:
        """SE of a difference from its confidence interval at its ci_level."""
        self._need("ci_low", "ci_high", "ci_level")
        return (self.ci_high - self.ci_low) / (2 * z_for(self.ci_level))

    def se_from_p(self) -> float:
        """SE of a difference from its two-sided P value, for rows that print no CI.

        The P value is read from the row's notes (the first 'P = x')."""
        self._need("estimate")
        p = self.p_value()
        return abs(self.estimate) / float(norm.ppf(1 - p / 2))

    def p_value(self) -> float:
        m = re.search(r"\bP = (0?\.\d+)", self.notes or "")
        if not m:
            raise DataIntegrityError(f"evidence row {self.id}: no 'P = x' in notes")
        return float(m.group(1))

    def count(self) -> int:
        """The group size in ``population``, written '(n = 2,118' (the schema has
        no field for it)."""
        m = re.search(r"\(n = (\d{1,3}(?:,\d{3})*|\d+)\b", self.population or "")
        if not m:
            raise DataIntegrityError(
                f"evidence row {self.id}: no '(n = N' in population"
            )
        return int(m.group(1).replace(",", ""))

    def per_grams(self) -> float:
        """The dose the row's effect is expressed per, parsed from ``unit``
        (e.g. 'per 28 g/day', 'mg/dL per 28.4 g/day')."""
        m = re.search(r"per (\d+(?:\.\d+)?) g/day", self.unit or "")
        if not m:
            raise DataIntegrityError(
                f"evidence row {self.id}: unit {self.unit!r} names no dose"
            )
        return float(m.group(1))

    @property
    def has_doi(self) -> bool:
        return bool(self.source.get("doi"))

    def citation_verified(self) -> bool:
        """True when the citation check passed: DOI resolves and title and first
        author match Crossref. Rows without a DOI (DESIGN decision 10 allows
        source.url instead) cannot be matched on Crossref; they count as verified
        when they carry a URL and record where the value was checked."""
        v = self.verified
        if self.has_doi:
            return (
                v.get("doi_resolves") is True
                and v.get("title_matches") is True
                and v.get("first_author_matches") is True
            )
        return bool(self.source.get("url")) and bool(v.get("value_checked_in"))


@functools.lru_cache(maxsize=1)
def _evidence_cached(digest: str) -> dict[str, EvidenceRow]:
    raw = yaml.safe_load(EVIDENCE.read_text(encoding="utf-8"))
    rows: dict[str, EvidenceRow] = {}
    for item in raw:
        if item["id"] in rows:
            raise DataIntegrityError(f"duplicate evidence id {item['id']}")
        rows[item["id"]] = EvidenceRow(
            id=item["id"],
            kind=item.get("kind"),
            measure=item.get("measure"),
            unit=item.get("unit"),
            estimate=item.get("estimate"),
            ci_low=item.get("ci_low"),
            ci_high=item.get("ci_high"),
            ci_level=item.get("ci_level"),
            pi_low=item.get("pi_low"),
            pi_high=item.get("pi_high"),
            support=item.get("support"),
            notes=item.get("notes"),
            source=item.get("source") or {},
            verified=item.get("verified") or {},
            exposure=item.get("exposure"),
            outcome=item.get("outcome"),
            population=item.get("population"),
        )
    return rows


def evidence() -> dict[str, EvidenceRow]:
    """All evidence rows by id (re-read whenever evidence.yaml changes)."""
    checked_path(EVIDENCE)
    return _evidence_cached(READS[EVIDENCE.relative_to(ROOT).as_posix()])


def row(row_id: str) -> EvidenceRow:
    """One evidence row by id; records the id and requires a verified citation."""
    rows = evidence()
    if row_id not in rows:
        raise DataIntegrityError(f"evidence row {row_id!r} is not in evidence.yaml")
    r = rows[row_id]
    if not r.citation_verified():
        raise DataIntegrityError(f"evidence row {row_id}: citation not verified")
    ROWS_USED.add(row_id)
    return r


# --------------------------------------------------------------------------
# Life tables and causes of death
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class LifeTable:
    sex: str
    age: tuple[int, ...]  # 0..omega; the last row is the open interval
    qx: tuple[float, ...]
    ex: tuple[float, ...]  # published e_x

    @property
    def omega(self) -> int:
        return self.age[-1]


def _folder(name: str, vintage: str | None) -> Path:
    """data/<name>, or its archived data/<name>/<vintage>/ (e.g. '2021')."""
    return DATA / name if vintage is None else DATA / name / vintage


def life_table(sex: str, vintage: str | None = None) -> LifeTable:
    rows = _read_csv(_folder("life_tables", vintage) / f"{sex}.csv")
    ages = tuple(int(r["age"]) for r in rows)
    if ages != tuple(range(len(ages))):
        raise DataIntegrityError(f"life_tables/{sex}.csv ages are not 0..omega")
    return LifeTable(
        sex=sex,
        age=ages,
        qx=tuple(float(r["qx"]) for r in rows),
        ex=tuple(float(r["ex"]) for r in rows),
    )


def life_table_source(vintage: str | None = None) -> str:
    path = _folder("life_tables", vintage) / "MANIFEST.json"
    return json.loads(path.read_text(encoding="utf-8"))["source"]


@dataclass(frozen=True)
class CauseShares:
    """Share of all deaths by cause, by age group (start ages; last group open)."""

    sex: str
    year: int
    start: tuple[int, ...]
    cvd: tuple[float, ...]
    chd: tuple[float, ...]
    external: tuple[float, ...]

    def at_ages(self, ages, cause: str) -> list[float]:
        """Share for each single age: the group containing it. Ages below the
        first group take the first group's share."""
        shares = getattr(self, cause)
        out = []
        for a in ages:
            i = max((j for j, s in enumerate(self.start) if s <= a), default=0)
            out.append(shares[i])
        return out


def cause_shares(sex: str, vintage: str | None = None) -> CauseShares:
    rows = [
        r
        for r in _read_csv(_folder("causes", vintage) / "cause_shares.csv")
        if r["sex"] == sex and r["age_group_start"] != ""
    ]
    rows.sort(key=lambda r: int(r["age_group_start"]))
    years = {int(r["year"]) for r in rows}
    if len(years) != 1:
        raise DataIntegrityError(f"cause_shares.csv mixes years {sorted(years)}")
    return CauseShares(
        sex=sex,
        year=years.pop(),
        start=tuple(int(r["age_group_start"]) for r in rows),
        cvd=tuple(float(r["cvd_share"]) for r in rows),
        chd=tuple(float(r["chd_share"]) for r in rows),
        external=tuple(float(r["external_share"]) for r in rows),
    )


# --------------------------------------------------------------------------
# Dose-response points, reproduction targets, composition, prices
# --------------------------------------------------------------------------


def aune_curve(outcome: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """(g/day, RR) points of Aune 2016's nonlinear curve for ``outcome``
    (Additional file 1 Tables S14 and S15), sorted by intake."""
    pts = sorted(
        (float(r["intake_g_per_day"]), float(r["rr"]))
        for r in _read_csv(DATA / "curves" / "aune2016_nonlinear.csv")
        if r["outcome"] == outcome and r["rr"] != ""
    )
    if not pts:
        raise DataIntegrityError(f"aune2016_nonlinear.csv has no {outcome!r} points")
    g, rr = zip(*pts)
    return tuple(g), tuple(rr)


def aune_points(outcome: str) -> list[dict[str, float | None]]:
    """Aune 2016's printed nonlinear points for ``outcome`` with their 95% CIs
    (the reference category has none)."""
    return [
        {
            "g": float(r["intake_g_per_day"]),
            "rr": float(r["rr"]),
            "lo": _float(r["ci_low"]),
            "hi": _float(r["ci_high"]),
        }
        for r in sorted(
            _read_csv(DATA / "curves" / "aune2016_nonlinear.csv"),
            key=lambda r: float(r["intake_g_per_day"]),
        )
        if r["outcome"] == outcome and r["rr"] != ""
    ]


def bop_curve() -> list[dict[str, float]]:
    """IHME Burden of Proof mean RR and outer (fixed plus random effects)
    uncertainty interval for a diet low in nuts and seeds and ischemic heart
    disease, on the API's exposure grid."""
    return [
        {
            "g": float(r["exposure_g_per_day"]),
            "rr": float(r["rr_mean"]),
            "lo": float(r["rr_outer_low"]),
            "hi": float(r["rr_outer_high"]),
        }
        for r in _read_csv(DATA / "curves" / "ihme_bop_nuts_seeds_ihd.csv")
    ]


def intake_pairs() -> list[dict[str, float | str]]:
    """Schwingshackl 2021's 23 intake-v-intake pairs, read from Supplementary
    Figure 9 and Table 5 (data/calibration/schwingshackl2021_intake_pairs.csv), in
    the figure's order: topic, outcome, ratio of risk ratios with its 95% CI, and
    the cohort and trial relative risks."""
    numeric = ("rrr", "ci_low", "ci_high", "cohort_rr", "rct_rr")
    return [
        {k: (float(v) if k in numeric else v) for k, v in r.items()}
        for r in _read_csv(DATA / "calibration" / "schwingshackl2021_intake_pairs.csv")
    ]


def fadnes_targets() -> dict:
    path = checked_path(DATA / "curves" / "fadnes2022_targets.yaml")
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def composition() -> dict[str, dict[str, float | str | None]]:
    """Per-100 g composition by food key."""
    out = {}
    for r in _read_csv(DATA / "composition" / "composition.csv"):
        out[r["key"]] = {
            k: (_float(v) if k.endswith(("_g", "_mg", "_ug", "_kcal")) else v)
            for k, v in r.items()
        }
    return out


def composition_basis_g() -> float:
    """Grams the composition values are expressed per ('per 100 g edible portion')."""
    basis = manifest("composition")["columns"]["composition.csv"]["basis"]
    m = re.search(r"per (\d+) g", basis)
    if not m:
        raise DataIntegrityError(f"composition basis {basis!r} names no grams")
    return float(m.group(1))


def prices_by_nut() -> dict[str, dict[str, float | str]]:
    out = {}
    for r in _read_csv(DATA / "prices" / "prices_by_nut.csv"):
        out[r["nut"]] = {
            "n_retailers": int(r["n_retailers"]),
            "retailers": r["retailers"],
            "min_usd_per_kg": float(r["min_usd_per_kg"]),
            "median_usd_per_kg": float(r["median_usd_per_kg"]),
            "max_usd_per_kg": float(r["max_usd_per_kg"]),
        }
    return out


def price_dates() -> dict[str, tuple[str, str]]:
    """(earliest, latest) retrieval date of the primary price rows, by nut."""
    dates: dict[str, list[str]] = {}
    for r in _read_csv(DATA / "prices" / "prices.csv"):
        if r["primary"] == "true":
            dates.setdefault(r["nut"], []).append(r["retrieval_date"])
    return {nut: (min(d), max(d)) for nut, d in dates.items()}
