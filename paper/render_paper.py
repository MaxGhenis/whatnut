#!/usr/bin/env python3
"""Fill, check and render the manuscript, then stage it under the wrapper.

1. fill_paper: results/results.json -> paper/index.qmd, paper/values.json
2. assert the filled qmd has no executable cell, no inline `{python}` and no
   leftover `{{`, and that every citation key is in paper/references.bib
3. stamp paper/VERSION into the wrapper (public/whatnut/index.html): every
   `web/index.html?v=` link and the "Revision N · YYYY-MM-DD" pill
4. quarto render paper --to html --no-execute (no kernel, no Jupyter), and
   --to pdf as well when a TeX engine is installed
5. copy the render to public/whatnut/web/ (the wrapper itself is untouched)

python paper/render_paper.py            # HTML, plus PDF when TeX is available
python paper/render_paper.py --no-pdf   # HTML only (what CI and Vercel produce)
python paper/render_paper.py --pdf      # require the PDF
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

PAPER = Path(__file__).resolve().parent
ROOT = PAPER.parent
sys.path.insert(0, str(PAPER))

import fill_paper  # noqa: E402

BUILD = PAPER / "_build"
WRAPPER = ROOT / "public" / "whatnut" / "index.html"
WEB = WRAPPER.parent / "web"
VERSION_FILE = PAPER / "VERSION"
VERSION_RE = re.compile(r"^r(\d+)-(\d{4})(\d{2})(\d{2})$")
BIB = PAPER / "references.bib"

# Quarto/Pandoc messages that mean the render silently lost content.
BAD_RENDER_OUTPUT = re.compile(
    r"(citation .* not found|unable to resolve crossref"
    r"|WARN.*(crossref|citeproc|citation))",
    re.I,
)


class RenderError(RuntimeError):
    pass


def read_version() -> tuple[str, int, str]:
    """(version, revision number, ISO date) from paper/VERSION, e.g. r1-20260923."""
    version = VERSION_FILE.read_text(encoding="utf-8").strip()
    m = VERSION_RE.match(version)
    if not m:
        raise RenderError(f"paper/VERSION is {version!r}; expected rN-YYYYMMDD")
    return version, int(m.group(1)), f"{m.group(2)}-{m.group(3)}-{m.group(4)}"


def stamp_wrapper(html: str, version: str, revision: int, date: str) -> str:
    """Put the version on every manuscript link and in the revision pill."""
    out, n_links = re.subn(r"(web/index\.html)\?v=[^\"'#\s]*", rf"\1?v={version}", html)
    out, n_pill = re.subn(
        r"Revision \d+ · \d{4}-\d{2}-\d{2}", f"Revision {revision} · {date}", out
    )
    if n_links < 2 or n_pill != 1:
        raise RenderError(
            f"wrapper has {n_links} versioned manuscript links and {n_pill} "
            "revision pills; expected at least 2 and exactly 1"
        )
    return out


def assert_clean_qmd(qmd_path: Path) -> None:
    text = qmd_path.read_text(encoding="utf-8")
    problems = fill_paper.problems_in_filled(text)
    if (
        "```{python" in text or "`{python}" in text
    ):  # belt and braces: the explicit contract
        problems.append("python engine cell or inline expression")
    bib_keys = (
        set(re.findall(r"^@\w+\{([^,\s]+),", BIB.read_text(encoding="utf-8"), re.M))
        if BIB.exists()
        else set()
    )
    missing = sorted(fill_paper.citation_keys(text) - bib_keys)
    if missing:
        problems.append(
            f"cited keys missing from paper/references.bib: {', '.join(missing)}"
        )
    if problems:
        raise RenderError(
            f"{qmd_path.relative_to(ROOT)} is not clean:\n  " + "\n  ".join(problems)
        )


def tex_available() -> bool:
    if shutil.which("xelatex"):
        return True
    home = Path.home()
    return any(
        p.exists()
        for p in [
            *home.glob("Library/TinyTeX/bin/*/xelatex"),
            *home.glob(".TinyTeX/bin/*/xelatex"),
        ]
    )


def quarto(to: str) -> None:
    quarto_bin = shutil.which("quarto")
    if not quarto_bin:
        raise RenderError(
            "quarto is not on PATH (https://quarto.org/docs/get-started/; "
            "CI and Vercel use 1.9.x)"
        )
    cmd = [quarto_bin, "render", str(PAPER), "--to", to, "--no-execute"]
    print("$", " ".join(cmd[1:]), flush=True)
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    log = proc.stdout + proc.stderr
    if proc.returncode != 0:
        raise RenderError(f"quarto render --to {to} failed:\n{log}")
    bad = [line for line in log.splitlines() if BAD_RENDER_OUTPUT.search(line)]
    if bad:
        raise RenderError(
            f"quarto render --to {to} dropped content:\n  " + "\n  ".join(bad)
        )


def copy_html() -> None:
    src = BUILD / "index.html"
    if not src.exists():
        raise RenderError(f"{src.relative_to(ROOT)} was not produced")
    html = src.read_text(encoding="utf-8")
    if "{{" in html:
        raise RenderError("rendered HTML contains '{{'")
    if WEB.exists():
        shutil.rmtree(WEB)
    shutil.copytree(
        BUILD, WEB, ignore=shutil.ignore_patterns("*.pdf", "*.tex", "*.log")
    )


def copy_pdf() -> None:
    pdfs = sorted(BUILD.glob("*.pdf"))
    if not pdfs:
        raise RenderError("PDF render produced no .pdf")
    WEB.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdfs[0], WEB / "index.pdf")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    group = ap.add_mutually_exclusive_group()
    group.add_argument(
        "--pdf", action="store_true", help="also render the PDF; fail if no TeX engine"
    )
    group.add_argument("--no-pdf", action="store_true", help="HTML only")
    args = ap.parse_args(argv)
    try:
        fill_paper.write()
        assert_clean_qmd(fill_paper.OUT_QMD)

        version, revision, date = read_version()
        wrapper = WRAPPER.read_text(encoding="utf-8")
        stamped = stamp_wrapper(wrapper, version, revision, date)
        if stamped != wrapper:
            WRAPPER.write_text(stamped, encoding="utf-8")
            print(f"stamped {version} into {WRAPPER.relative_to(ROOT)}")

        if BUILD.exists():
            shutil.rmtree(BUILD)
        quarto("html")
        copy_html()
        want_pdf = args.pdf or (not args.no_pdf and tex_available())
        if args.pdf and not tex_available():
            raise RenderError(
                "--pdf needs xelatex on PATH (or TinyTeX: quarto install tinytex)"
            )
        if want_pdf:
            quarto("pdf")
            copy_pdf()
    except (fill_paper.FillError, RenderError) as exc:
        print(f"render_paper: {exc}", file=sys.stderr)
        return 1
    built = sorted(p.name for p in WEB.iterdir())
    print(f"staged {WEB.relative_to(ROOT)}/: {', '.join(built)}")
    print(
        "preview: python -m http.server -d public 8000  ->  http://localhost:8000/whatnut/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
