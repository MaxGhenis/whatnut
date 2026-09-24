#!/usr/bin/env python3
"""Fill, check and render the manuscript, then stage it under the wrapper.

1. fill_paper: results/results.json -> paper/index.qmd, paper/values.json
2. assert the filled qmd has no executable cell, no inline `{python}` and no
   leftover `{{`, and that every citation key is in paper/references.bib
3. stamp paper/VERSION into the wrapper (public/whatnut/index.html): every
   `web/index.html?v=` and `web/index.pdf?v=` link, the "Revision N ·
   YYYY-MM-DD" pill and the description's "revision N of the manuscript"
4. quarto render paper --to html --no-execute, then --to typst --no-execute
   (no kernel, no Jupyter, no TeX: Typst ships with Quarto). These are the two
   renders Vercel runs, so both builds stage the same files. Quarto's
   post-render script, paper/external_links.ts, writes target="_blank" into the
   HTML's external links; this step checks it did.
5. copy paper/_build/ (index.html, figures, index.pdf) to public/whatnut/web/
   (the wrapper itself is only stamped, in step 3)

python paper/render_paper.py            # HTML and PDF (what CI and Vercel produce)
python paper/render_paper.py --no-pdf   # HTML only, for quick previews; the
                                        # wrapper's "Download PDF" link then 404s
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser
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


# "This page embeds revision N of the manuscript." in the description; the
# words may wrap across lines.
REVISION_PHRASE_RE = re.compile(r"\brevision(\s+)\d+(\s+of\s+the\s+manuscript)\b")


def stamp_wrapper(html: str, version: str, revision: int, date: str) -> str:
    """Put the version on every manuscript link (HTML and PDF), in the revision
    pill and in the description's "revision N of the manuscript"."""
    out, n_html = re.subn(r"(web/index\.html)\?v=[^\"'#\s]*", rf"\1?v={version}", html)
    out, n_pdf = re.subn(r"(web/index\.pdf)\?v=[^\"'#\s]*", rf"\1?v={version}", out)
    out, n_pill = re.subn(
        r"Revision \d+ · \d{4}-\d{2}-\d{2}", f"Revision {revision} · {date}", out
    )
    out, n_phrase = REVISION_PHRASE_RE.subn(
        lambda m: f"revision{m.group(1)}{revision}{m.group(2)}", out
    )
    if n_html < 2 or n_pdf != 1 or n_pill != 1 or n_phrase != 1:
        raise RenderError(
            f"wrapper has {n_html} versioned HTML manuscript links, {n_pdf} "
            f"versioned PDF links, {n_pill} revision pills and {n_phrase} "
            "'revision N of the manuscript' phrases; expected at least 2, "
            "exactly 1, exactly 1 and exactly 1"
        )
    return out


VALUE_SPAN_RE = re.compile(
    r'(<span data-value="([a-z][a-z0-9_]*)">)(.*?)(</span>)', re.S
)


def fill_wrapper_values(html: str, values: dict) -> str:
    """Set every <span data-value="name"> in the wrapper to values.json's text,
    so the wrapper's numbers are the paper's numbers."""
    missing = sorted({m.group(2) for m in VALUE_SPAN_RE.finditer(html)} - set(values))
    if missing:
        raise RenderError(f"wrapper names values not in paper/values.json: {missing}")
    return VALUE_SPAN_RE.sub(
        lambda m: m.group(1) + values[m.group(2)]["text"] + m.group(4), html
    )


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


EXTERNAL_HREF = re.compile(r"^\s*(?:https?:|mailto:)", re.I)


class _Anchors(HTMLParser):
    """Every <a> start tag's attributes (script and style bodies are skipped)."""

    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[dict[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append({k: v or "" for k, v in attrs})


def external_links_not_in_new_tab(html: str) -> list[str]:
    """hrefs of external links (http, https, mailto) that lack target="_blank"
    or rel="noopener". Empty once paper/external_links.ts has run."""
    parser = _Anchors()
    parser.feed(html)
    return [
        a["href"]
        for a in parser.anchors
        if EXTERNAL_HREF.match(a.get("href", ""))
        and (
            a.get("target") != "_blank"
            or "noopener" not in a.get("rel", "").lower().split()
        )
    ]


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


def check_html() -> None:
    src = BUILD / "index.html"
    if not src.exists():
        raise RenderError(f"{src.relative_to(ROOT)} was not produced")
    html = src.read_text(encoding="utf-8")
    if "{{" in html:
        raise RenderError("rendered HTML contains '{{'")
    stuck = external_links_not_in_new_tab(html)
    if stuck:
        raise RenderError(
            f"{len(stuck)} external links would open inside the sandboxed iframe "
            "(did the post-render script paper/external_links.ts run?): "
            + ", ".join(stuck[:5])
        )


def check_pdf() -> None:
    pdf = BUILD / "index.pdf"
    if not pdf.exists():
        raise RenderError(f"{pdf.relative_to(ROOT)} was not produced")
    if not pdf.read_bytes().startswith(b"%PDF-"):
        raise RenderError(f"{pdf.relative_to(ROOT)} is not a PDF")


def stage() -> None:
    """public/whatnut/web/ becomes a copy of paper/_build/, as on Vercel
    (`cp -R paper/_build/. public/whatnut/web/`)."""
    if WEB.exists():
        shutil.rmtree(WEB)
    shutil.copytree(BUILD, WEB)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--no-pdf",
        action="store_true",
        help="skip the Typst PDF (quick previews; CI and Vercel build it)",
    )
    args = ap.parse_args(argv)
    try:
        fill_paper.write()
        assert_clean_qmd(fill_paper.OUT_QMD)

        version, revision, date = read_version()
        wrapper = WRAPPER.read_text(encoding="utf-8")
        stamped = stamp_wrapper(wrapper, version, revision, date)
        values = json.loads(fill_paper.OUT_VALUES.read_text(encoding="utf-8"))
        stamped = fill_wrapper_values(stamped, values)
        if stamped != wrapper:
            WRAPPER.write_text(stamped, encoding="utf-8")
            print(f"stamped {version} into {WRAPPER.relative_to(ROOT)}")

        if BUILD.exists():
            shutil.rmtree(BUILD)
        quarto("html")
        check_html()
        if not args.no_pdf:
            quarto("typst")
            check_pdf()
            check_html()  # the second render left the HTML in place
        stage()
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
