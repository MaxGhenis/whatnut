"""Content-addressed methodology provenance for generated What Nut results.

The results artifact records both human-readable methodological context and a
machine-verifiable boundary for the code and data that determine its numerical
outputs.  File labels are repository-relative so provenance is identical in a
source checkout and an installed wheel, independent of the current directory.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from collections.abc import Mapping
from typing import Final

from whatnut.model import RNG_ALGORITHM

PROVENANCE_SCHEMA_VERSION: Final = "1.1.0"
WHATNUT_MODEL_VERSION: Final = "0.4.0"

WHATNUT_REPOSITORY_URL: Final = "https://github.com/MaxGhenis/whatnut"
OPTIQAL_REPOSITORY_URL: Final = "https://github.com/MaxGhenis/optiqal-ai"
OPTIQAL_REFERENCE_COMMIT: Final = "4d22afd53715216cb2ab2cac5bfa23f969fc2c25"
OPTIQAL_REFERENCE_URL: Final = (
    f"{OPTIQAL_REPOSITORY_URL}/commit/{OPTIQAL_REFERENCE_COMMIT}"
)

CONTENT_HASH_ALGORITHM: Final = "sha256"

_PACKAGE_DIR = Path(__file__).resolve().parent
_REPOSITORY_PACKAGE_PREFIX = Path("src/whatnut")

# Every Python module that can change the numerical analysis or its declared
# estimand.  Presentation, serialization, and provenance code are deliberately
# excluded: they cannot change a correctly materialized numerical result.
SCIENTIFIC_CODE_FILES: Final = (
    "config.py",
    "decision.py",
    "lifecycle.py",
    "model.py",
    "pipeline.py",
    "reference_case.py",
    "spec.py",
)

# Versioned inputs read by the canonical analysis.  Raw source archives are not
# included because the model reads these materialized, validated inputs; their
# own source citations and build metadata live alongside the data builders.
INPUT_DATA_FILES: Final = (
    "data/cause_fractions.yaml",
    "data/constants.yaml",
    "data/mortality.yaml",
    "data/nuts.yaml",
    "data/priors.yaml",
    "data/quality_weights.yaml",
)


def _sha256_file(path: Path) -> str:
    """Return the lowercase SHA-256 digest of a file's exact stored bytes."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _content_hashes(relative_paths: tuple[str, ...]) -> dict[str, str]:
    """Hash package files and label them with stable repository-relative paths."""
    hashes: dict[str, str] = {}
    for relative_path in sorted(relative_paths):
        package_path = _PACKAGE_DIR / relative_path
        if not package_path.is_file():
            raise FileNotFoundError(
                f"Provenance input is not a regular file: {package_path}"
            )
        repository_path = (_REPOSITORY_PACKAGE_PREFIX / relative_path).as_posix()
        hashes[repository_path] = _sha256_file(package_path)
    return hashes


def _analysis_fingerprint(
    scientific_code_sha256: dict[str, str],
    input_data_sha256: dict[str, str],
    analysis_spec_sha256: str,
) -> str:
    """Hash the complete machine-verifiable analysis boundary.

    Canonical JSON makes the aggregate independent of mapping insertion order.
    The Optiqal reference and RNG identifier are included because neither is a
    local file, yet both are part of the declared reproducibility boundary.
    """
    boundary = {
        "analysis_spec_sha256": analysis_spec_sha256,
        "content_hash_algorithm": CONTENT_HASH_ALGORITHM,
        "input_data_sha256": input_data_sha256,
        "optiqal_reference_commit": OPTIQAL_REFERENCE_COMMIT,
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "rng_algorithm": RNG_ALGORITHM,
        "scientific_code_sha256": scientific_code_sha256,
        "whatnut_model_version": WHATNUT_MODEL_VERSION,
    }
    serialized = json.dumps(
        boundary,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def methodology_provenance(
    analysis_spec: Mapping[str, object],
) -> dict[str, object]:
    """Return the reproducible boundary of What Nut's numerical analysis.

    The returned dictionaries are newly allocated on every call, allowing an
    artifact consumer to retain or mutate its copy without affecting a later
    result.  Hashes describe exact file bytes rather than Git state, so they are
    meaningful for installed packages and for results generated before commit.
    """
    scientific_code_sha256 = _content_hashes(SCIENTIFIC_CODE_FILES)
    input_data_sha256 = _content_hashes(INPUT_DATA_FILES)
    serialized_spec = json.dumps(
        analysis_spec,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    analysis_spec_sha256 = hashlib.sha256(serialized_spec).hexdigest()

    return {
        "provenance_schema_version": PROVENANCE_SCHEMA_VERSION,
        "whatnut_model_version": WHATNUT_MODEL_VERSION,
        "whatnut_repository_url": WHATNUT_REPOSITORY_URL,
        "optiqal_repository_url": OPTIQAL_REPOSITORY_URL,
        "optiqal_reference_commit": OPTIQAL_REFERENCE_COMMIT,
        "optiqal_reference_url": OPTIQAL_REFERENCE_URL,
        "optiqal_reference_scope": (
            "The commit pins the HR-centering and 3%/3% reference-case methods "
            "reviewed for this update. What Nut excludes uncalibrated per-nut "
            "mortality multipliers that are not estimable from its evidence base."
        ),
        "rng_algorithm": RNG_ALGORITHM,
        "content_hash_algorithm": CONTENT_HASH_ALGORITHM,
        "scientific_code_sha256": scientific_code_sha256,
        "input_data_sha256": input_data_sha256,
        "analysis_spec_sha256": analysis_spec_sha256,
        "analysis_fingerprint_sha256": _analysis_fingerprint(
            scientific_code_sha256,
            input_data_sha256,
            analysis_spec_sha256,
        ),
        "adopted": [
            "HR-centered uncertainty propagation",
            "US Second Panel-style 3%/3% primary reference case",
            "explicit decision specification before evidence propagation",
        ],
        "whatnut_extensions": [
            "exact single-age competing-risk lifecycle on the hazard scale",
            "half-cycle person-time and midpoint discounting",
            "named independent random-number streams",
            "explicit no-modeled-nut comparator metadata",
            "expected-net-monetary-benefit decision ranking",
            "draw-wise probability of optimality across mutually exclusive options",
        ],
        "deliberate_differences": [
            "What Nut propagates cause-specific mortality-potential estimates.",
            "Only outcome-matched nutrient coefficients enter the canonical base.",
            "Uncalibrated per-nut residuals and whole-nut multipliers are excluded.",
            "QALYs include mortality effects only, not direct morbidity or harms.",
            "The default causal prior is nutrition-specific Beta(1.5, 6.0).",
            "The gross-addition benchmark is conditional on no displacement, "
            "energy-balance, adiposity, adherence, or mixed-nut effects.",
        ],
        "runtime_dependency": False,
    }
