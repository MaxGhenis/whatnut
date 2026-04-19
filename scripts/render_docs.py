"""Pre-render MyST docs so the build doesn't need a Jupyter kernel.

The paper uses MyST's `{eval}` role and `{code-cell} python` blocks that
pull values and rendered HTML tables from `whatnut.results.r`. Running
`myst build --execute` on Vercel fails to start a Jupyter server, so
every inline expression renders as the literal placeholder
``Unexecuted inline expression for: ...`` and every code-cell output is
omitted. This script evaluates every `{eval}` expression and every
`{code-cell}` block in the host Python process (where `r` is importable
directly from `results.json`) and rewrites each source doc to plain MyST
Markdown. After this, `myst build --html` has nothing to execute.

Intended use at build time (Vercel and CI):

    python scripts/render_docs.py
    cd docs && myst build --html   # no --execute

Source `.md` files under `docs/` are rewritten in place; the Vercel
build container is ephemeral so there is no worry about persisting
changes. Do not commit the rewritten output.
"""

from __future__ import annotations

import re
import sys
import types
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs"
SRC_DIR = REPO_ROOT / "src"
FILES = ("index.md", "appendix.md")

EVAL_RE = re.compile(r"\{eval\}`([^`]+)`")
CODE_CELL_RE = re.compile(
    r"^```\{code-cell\} python\n"
    r"(?:(:tags:\s*\[(?P<tags>[^\]]*)\])\n)?"
    r"\n?"
    r"(?P<src>.*?)"
    r"^```\n",
    flags=re.DOTALL | re.MULTILINE,
)


class _HTML:
    """Minimal stand-in for IPython.display.HTML during pre-render."""

    def __init__(self, content: str) -> None:
        self.content = content

    def _repr_html_(self) -> str:
        return self.content


def _exec_cell(src: str, ns: dict) -> object:
    """Execute a code-cell body and return the value of the final expression."""
    lines = src.strip("\n").splitlines()
    if not lines:
        return None
    expr_src = lines[-1].strip()
    body_src = "\n".join(lines[:-1])
    if body_src:
        exec(compile(body_src, "<cell>", "exec"), ns)
    try:
        return eval(compile(expr_src, "<cell>", "eval"), ns)
    except SyntaxError:
        exec(compile(expr_src, "<cell>", "exec"), ns)
        return None


def _render_cell(match: re.Match[str], ns: dict) -> str:
    tags_raw = match.group("tags") or ""
    tags = {t.strip() for t in tags_raw.split(",") if t.strip()}
    src = match.group("src")

    if "remove-cell" in tags:
        return ""

    result = _exec_cell(src, ns)
    if hasattr(result, "_repr_html_"):
        output = result._repr_html_()
    elif result is None:
        output = ""
    else:
        output = str(result)

    if "remove-input" in tags:
        return output + "\n" if output else ""
    return f"```python\n{src.rstrip()}\n```\n\n{output}\n" if output else f"```python\n{src.rstrip()}\n```\n"


def render_file(path: Path, ns: dict) -> None:
    text = path.read_text()
    text = CODE_CELL_RE.sub(lambda m: _render_cell(m, ns), text)
    text = EVAL_RE.sub(lambda m: str(eval(m.group(1), ns)), text)
    path.write_text(text)
    try:
        display_path = path.relative_to(REPO_ROOT)
    except ValueError:
        display_path = path
    print(f"[render_docs] wrote {display_path}")


def _install_ipython_shim() -> None:
    """Expose `from IPython.display import HTML` without installing IPython.

    The paper's code cells write `from IPython.display import HTML` for an
    interactive Jupyter experience. At Vercel build time we just need the
    same API surface without pulling in the full IPython stack.
    """
    ipython = types.ModuleType("IPython")
    display = types.ModuleType("IPython.display")
    display.HTML = _HTML
    ipython.display = display
    sys.modules["IPython"] = ipython
    sys.modules["IPython.display"] = display


def main() -> None:
    sys.path.insert(0, str(SRC_DIR))
    _install_ipython_shim()
    from whatnut.results import r  # noqa: E402

    ns: dict = {"r": r, "HTML": _HTML, "__name__": "__render_docs__"}
    for fname in FILES:
        render_file(DOCS_DIR / fname, ns)


if __name__ == "__main__":
    main()
