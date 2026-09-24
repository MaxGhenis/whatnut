"""Shared test helpers: one fresh pipeline run per tag per test session."""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from pathlib import Path

from whatnut import pipeline

ROOT = Path(__file__).resolve().parent.parent


@functools.cache
def fresh_run(tag: str = "a") -> tuple[dict, Path]:
    """Run the full pipeline into a temporary directory; (rounded results, dir)."""
    out = Path(tempfile.mkdtemp(prefix=f"whatnut-{tag}-"))
    atexit.register(shutil.rmtree, out, True)
    res = pipeline.run(out / "results.json", out / "figures")
    return res, out
