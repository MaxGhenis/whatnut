"""Tests for the pre-rendering pipeline used by Vercel and the CI PDF build.

The render script is the contract between Python-backed results and a
pure-Markdown MyST input tree. A regression here produces a silently
broken paper (e.g. `Unexecuted inline expression` placeholders on the
live site), so every observable behavior gets a direct assertion.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"


@pytest.fixture
def render_docs():
    """Import scripts/render_docs.py as a module and install its shim.

    Every test in this file exercises behavior that depends on the
    IPython.display shim being live (the paper's code cells import it),
    so installing it in the fixture removes a source of order-dependent
    failures between tests.
    """
    sys.path.insert(0, str(SCRIPTS_DIR))
    try:
        module = importlib.import_module("render_docs")
        module = importlib.reload(module)
        module._install_ipython_shim()
        yield module
    finally:
        sys.path.remove(str(SCRIPTS_DIR))
        sys.modules.pop("render_docs", None)


@pytest.fixture
def fake_r():
    """A minimal stand-in for whatnut.results.r with dotted attrs."""
    walnut = SimpleNamespace(qaly_mean=0.10, life_years=0.15, icer_fmt="$92,106")
    return SimpleNamespace(
        confounding_alpha=1.5,
        confounding_beta=6.0,
        confounding_mean=0.2,
        target_age=40,
        n_samples=10000,
        walnut=walnut,
    )


# ---------------------------------------------------------------------------
# {eval} expression handling
# ---------------------------------------------------------------------------


class TestEvalSubstitution:
    """Every {eval}`expr` must be replaced by str(eval(expr, {"r": r})).

    The paper depends on this for Beta parameters, sample counts, formatted
    ICERs, and per-nut fields; a regression here is exactly what shipped
    the `Unexecuted inline expression for: ...` placeholders to prod.
    """

    def _run(self, render_docs, fake_r, md: str) -> str:
        ns = {"r": fake_r, "HTML": render_docs._HTML, "__name__": "__render__"}
        # EVAL_RE is run over the full text after code-cell handling; testing
        # it in isolation mirrors render_file's second pass.
        return render_docs.EVAL_RE.sub(
            lambda m: str(eval(m.group(1), ns)), md
        )

    def test_plain_attribute(self, render_docs, fake_r):
        out = self._run(render_docs, fake_r, "age: {eval}`r.target_age`.")
        assert out == "age: 40."

    def test_formatted_fstring(self, render_docs, fake_r):
        out = self._run(render_docs, fake_r, 'N={eval}`f"{r.n_samples:,}"`.')
        assert out == "N=10,000."

    def test_nested_dot_access(self, render_docs, fake_r):
        out = self._run(render_docs, fake_r, "walnut {eval}`r.walnut.icer_fmt`.")
        assert out == "walnut $92,106."

    def test_float_precision(self, render_docs, fake_r):
        out = self._run(
            render_docs, fake_r, '{eval}`f"{r.confounding_alpha:.1f}"`'
        )
        assert out == "1.5"

    def test_multiple_in_one_line(self, render_docs, fake_r):
        out = self._run(
            render_docs,
            fake_r,
            "Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`)",
        )
        assert out == "Beta(1.5, 6.0)"


# ---------------------------------------------------------------------------
# {code-cell} handling
# ---------------------------------------------------------------------------


class TestCodeCellHandling:
    """`{code-cell}` blocks must be rewritten by tag.

    - `remove-cell` → dropped entirely (setup import cell becomes invisible).
    - `remove-input` → replaced with the evaluated cell's HTML output only.
    - untagged → shown as a regular fenced python block (no output needed
      because the cells that need output in the paper always use one of
      the two MyST tags).
    """

    def _render(self, render_docs, fake_r, md: str) -> str:
        ns = {"r": fake_r, "HTML": render_docs._HTML, "__name__": "__render__"}
        return render_docs.CODE_CELL_RE.sub(
            lambda m: render_docs._render_cell(m, ns), md
        )

    def test_remove_cell_is_dropped(self, render_docs, fake_r):
        md = (
            "before\n\n"
            "```{code-cell} python\n"
            ":tags: [remove-cell]\n"
            "\n"
            "from whatnut.results import r\n"
            "```\n"
            "\nafter"
        )
        out = self._render(render_docs, fake_r, md)
        assert "from whatnut.results import r" not in out
        assert "code-cell" not in out
        assert "before" in out and "after" in out

    def test_remove_input_emits_html_only(self, render_docs, fake_r):
        md = (
            "```{code-cell} python\n"
            ":tags: [remove-input]\n"
            "\n"
            "from IPython.display import HTML\n"
            "HTML('<table><tr><td>Walnut</td></tr></table>')\n"
            "```\n"
        )
        out = self._render(render_docs, fake_r, md)
        assert "<table><tr><td>Walnut</td></tr></table>" in out
        assert "from IPython.display" not in out
        assert "code-cell" not in out

    def test_untagged_cell_preserved_as_python_block(self, render_docs, fake_r):
        md = "```{code-cell} python\n\nx = 1\nx\n```\n"
        out = self._render(render_docs, fake_r, md)
        assert "```python" in out
        # The exec output (1) should also be present
        assert "1" in out

    def test_html_repr_invoked_for_ipython_shim(self, render_docs, fake_r):
        """HTML(...) should surface via _repr_html_, not str()."""
        md = (
            "```{code-cell} python\n"
            ":tags: [remove-input]\n"
            "\n"
            "from IPython.display import HTML\n"
            "HTML('<em>rendered</em>')\n"
            "```\n"
        )
        out = self._render(render_docs, fake_r, md)
        # A bare `str(HTML_obj)` would expose the instance repr, which must not
        # leak.
        assert "_HTML object at" not in out
        assert "<em>rendered</em>" in out


# ---------------------------------------------------------------------------
# IPython shim
# ---------------------------------------------------------------------------


class TestIPythonShim:
    """The shim must make `from IPython.display import HTML` work."""

    def test_shim_exposes_html(self, render_docs):
        # The render_docs fixture installs the shim; just confirm the import
        # path works and the stub's _repr_html_ round-trips.
        try:
            from IPython.display import HTML  # noqa: E402
        except ImportError as e:  # pragma: no cover — shim failure
            pytest.fail(f"shim failed: {e}")
        obj = HTML("<p>ok</p>")
        assert obj._repr_html_() == "<p>ok</p>"


# ---------------------------------------------------------------------------
# End-to-end render_file
# ---------------------------------------------------------------------------


class TestRenderFileEndToEnd:
    """render_file should rewrite a real .md in place with all paths covered."""

    def test_rewrite_in_place_removes_all_execution_markers(
        self, render_docs, fake_r, tmp_path
    ):
        src = (
            "---\n"
            "title: Test\n"
            "---\n\n"
            "```{code-cell} python\n"
            ":tags: [remove-cell]\n"
            "\n"
            "setup = True\n"
            "```\n\n"
            "The target age is {eval}`r.target_age` and "
            "Beta({eval}`r.confounding_alpha`, {eval}`r.confounding_beta`).\n\n"
            "```{code-cell} python\n"
            ":tags: [remove-input]\n"
            "\n"
            "from IPython.display import HTML\n"
            "HTML('<b>table</b>')\n"
            "```\n"
        )
        f = tmp_path / "doc.md"
        f.write_text(src)
        ns = {"r": fake_r, "HTML": render_docs._HTML, "__name__": "__render__"}
        render_docs.render_file(f, ns)
        out = f.read_text()

        assert "{eval}" not in out
        assert "code-cell" not in out
        assert "Unexecuted inline expression" not in out
        assert "The target age is 40 and Beta(1.5, 6.0)." in out
        assert "<b>table</b>" in out

    def test_live_paper_files_render_without_placeholders(self, render_docs, tmp_path):
        """Rendering the actual docs against the real r must leave no placeholder.

        This is the regression anchor for the prod bug: if the docs gain a
        new `{eval}` expression that the pipeline can't evaluate, this test
        fires rather than a live site shipping `Unexecuted inline...`
        placeholders.
        """
        from whatnut.results import r as real_r

        ns = {
            "r": real_r,
            "HTML": render_docs._HTML,
            "__name__": "__render__",
        }
        render_docs._install_ipython_shim()
        for fname in ("index.md", "appendix.md"):
            src = (REPO_ROOT / "docs" / fname).read_text()
            scratch = tmp_path / fname
            scratch.write_text(src)
            render_docs.render_file(scratch, ns)
            rendered = scratch.read_text()
            assert "{eval}" not in rendered, f"{fname} left {{eval}} unhandled"
            assert "code-cell" not in rendered, f"{fname} left code-cell unhandled"
            assert "Unexecuted inline expression" not in rendered
