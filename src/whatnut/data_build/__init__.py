"""Data rebuild pipeline for whatnut.

Every yaml file under `whatnut/data/` is regenerated from a raw artifact
stored in `whatnut/data/raw/`. Each fetcher is a module in this package
that (a) hits a primary source, (b) writes a raw artifact to `data/raw/`,
and (c) produces a generator function that can write the corresponding
yaml. Running `python -m whatnut.data_build` re-executes all fetchers in
order and rewrites the yaml files in place.

This exists because an author-provenanced `@misc` bib entry is not a
defensible substitute for an auditable raw artifact. A reviewer (human
or otherwise) must be able to open `data/raw/` and trace every number in
the paper to a specific source file, with the retrieval timestamp and
source URL attached.
"""

from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
