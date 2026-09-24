"""The /whatnut/ wrapper stays consistent with the manuscript it frames.

Pattern (paper-embed, from PolicyBench's /paper): /whatnut/ is a shelled
wrapper (site header, paper header, actions, one versioned sandboxed iframe of
the raw manuscript at /whatnut/web/, footer). The version string lives once in
paper/VERSION; every manuscript link in the wrapper carries it.
"""

from __future__ import annotations

import json
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "public" / "whatnut" / "index.html"
VERSION = (ROOT / "paper" / "VERSION").read_text(encoding="utf-8").strip()
MANUSCRIPT = f"web/index.html?v={VERSION}"
CANONICAL = "https://www.maxghenis.com/whatnut/"

# Absolute URLs the wrapper may use: site shell, repository, fonts, canonical URL.
ALLOWED_ABSOLUTE = (
    "https://www.maxghenis.com",
    "https://github.com/MaxGhenis/whatnut",
    "https://fonts.googleapis.com",
    "https://fonts.gstatic.com",
)


class _Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text: dict[str, list[str]] = {}
        self._stack: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, {k: v or "" for k, v in attrs}))
        self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._stack:
            self.text.setdefault(self._stack[-1], []).append(data)


@pytest.fixture(scope="module")
def html() -> str:
    return WRAPPER.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc(html) -> _Collect:
    parser = _Collect()
    parser.feed(html)
    return parser


def _attr_urls(doc: _Collect) -> list[tuple[str, str, str]]:
    return [
        (tag, name, attrs[name])
        for tag, attrs in doc.tags
        for name in ("href", "src")
        if name in attrs
    ]


def test_version_file_format():
    assert re.fullmatch(r"r\d+-\d{8}", VERSION), (
        f"paper/VERSION is {VERSION!r}; expected rN-YYYYMMDD"
    )


def test_every_version_param_equals_paper_version(html):
    params = re.findall(r"\?v=([^\"'&#\s]+)", html)
    assert params, "the wrapper carries no ?v= links"
    assert set(params) == {VERSION}, (
        f"?v= values {sorted(set(params))} differ from paper/VERSION {VERSION}"
    )


def test_no_stray_version_strings(html):
    """No other rN-YYYYMMDD string can hide in the wrapper (a half-bumped revision)."""
    assert set(re.findall(r"\br\d+-\d{8}\b", html)) == {VERSION}


def test_one_iframe_with_the_embed_contract(doc):
    iframes = [attrs for tag, attrs in doc.tags if tag == "iframe"]
    assert len(iframes) == 1, "exactly one embedded manuscript"
    frame = iframes[0]
    assert frame["src"] == MANUSCRIPT
    assert frame["loading"] == "lazy"
    assert (
        frame["sandbox"]
        == "allow-same-origin allow-popups allow-popups-to-escape-sandbox"
    )
    assert frame["referrerpolicy"] == "same-origin"
    assert "manuscript" in frame["title"].lower()


def test_iframe_css(html):
    rule = re.search(r"\.paper-frame-card iframe\s*\{([^}]*)\}", html)
    assert rule, "iframe style rule missing"
    css = " ".join(rule.group(1).split())
    assert "height: calc(100vh - 16rem)" in css
    assert "min-height: 720px" in css
    assert "background: #fff" in css


def test_standalone_links_match_iframe(doc):
    links = [
        attrs["href"]
        for tag, attrs in doc.tags
        if tag == "a" and attrs.get("href", "").startswith("web/")
    ]
    assert len(links) >= 2, "an 'Open standalone HTML' action and a footer link"
    assert set(links) == {MANUSCRIPT}


def test_actions_and_footer(html):
    assert re.search(
        rf'<a class="primary" href="{re.escape(MANUSCRIPT)}">Open standalone HTML</a>',
        html,
    )
    assert '<a href="https://github.com/MaxGhenis/whatnut">Code and data</a>' in html
    assert '<a href="#top">↑ Back to top</a>' in html
    assert '<body id="top">' in html


def test_site_shell(html):
    assert '<a class="wordmark" href="https://www.maxghenis.com">Max Ghenis</a>' in html
    assert re.search(
        r'<a [^>]*href="https://www\.maxghenis\.com/projects">Projects</a>', html
    )


def test_paper_header(html):
    assert '<p class="kicker">Working paper</p>' in html
    m = re.search(r"Revision (\d+) · (\d{4})-(\d{2})-(\d{2}) · Max Ghenis", html)
    assert m, "revision pill missing"
    rev, y, mo, d = m.groups()
    assert f"r{rev}-{y}{mo}{d}" == VERSION, "the pill disagrees with paper/VERSION"
    assert len(re.findall(r'<p class="paper-desc">', html)) == 1


def test_urls_are_relative_or_allowlisted(doc):
    for tag, name, url in _attr_urls(doc):
        if url.startswith(("#", "data:")):
            continue
        parts = urlsplit(url)
        if parts.scheme or parts.netloc:
            assert url.startswith(ALLOWED_ABSOLUTE), (
                f"<{tag} {name}={url!r}> is an absolute URL outside the allowlist"
            )
        else:
            assert not url.startswith("/"), (
                f"<{tag} {name}={url!r}> is root-relative; use a relative URL"
            )


def test_manuscript_links_are_relative(doc):
    for tag, name, url in _attr_urls(doc):
        assert "web/index" not in url or url.startswith("web/"), (
            f"<{tag} {name}={url!r}> must be relative"
        )


def test_og_and_canonical(doc):
    meta = {
        attrs.get("property") or attrs.get("name"): attrs.get("content")
        for tag, attrs in doc.tags
        if tag == "meta"
    }
    assert meta["og:type"] == "article"
    assert meta["og:url"] == CANONICAL
    assert meta.get("og:title") and meta.get("og:description")
    canon = [
        attrs["href"]
        for tag, attrs in doc.tags
        if tag == "link" and attrs.get("rel") == "canonical"
    ]
    assert canon == [CANONICAL]


def test_title_matches_manuscript(doc):
    """The wrapper's h1, <title> and og:title name the manuscript's title."""
    template = (ROOT / "paper" / "index.qmd.in").read_text(encoding="utf-8")
    m = re.search(r'^title:\s*"?(.*?)"?\s*$', template, re.M)
    assert m, "no title in the template front matter"
    title = m.group(1)
    h1 = "".join(doc.text.get("h1", [])).strip()
    assert h1 == title
    assert title in "".join(doc.text.get("title", []))
    og = next(
        attrs["content"]
        for tag, attrs in doc.tags
        if tag == "meta" and attrs.get("property") == "og:title"
    )
    assert og == title


def test_themes_via_tokens(html):
    assert re.search(r":root\s*\{[^}]*--bg:", html)
    assert "@media (prefers-color-scheme: dark)" in html
    assert re.search(r"body\s*\{[^}]*background-color:\s*var\(--bg\)", html)


def test_render_step_stamps_the_wrapper():
    """render_paper.stamp_wrapper is idempotent on the committed wrapper."""
    import sys

    sys.path.insert(0, str(ROOT / "paper"))
    import render_paper

    version, revision, date = render_paper.read_version()
    html = WRAPPER.read_text(encoding="utf-8")
    assert render_paper.stamp_wrapper(html, version, revision, date) == html
    bumped = render_paper.stamp_wrapper(html, "r2-20261001", 2, "2026-10-01")
    assert "?v=r1-" not in bumped and bumped.count("?v=r2-20261001") == html.count(
        f"?v={VERSION}"
    )
    assert "Revision 2 · 2026-10-01 · Max Ghenis" in bumped


def test_wrapper_is_tracked_and_render_is_not():
    def ignored(path: str) -> bool:
        return (
            subprocess.run(["git", "check-ignore", "-q", path], cwd=ROOT).returncode
            == 0
        )

    assert not ignored("public/whatnut/index.html"), ".gitignore hides the wrapper"
    assert ignored("public/whatnut/web/index.html"), (
        "the render under web/ should be rebuilt, not committed"
    )


def test_vercel_config():
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    assert cfg["outputDirectory"] == "public"
    assert "install_quarto.sh" in cfg["installCommand"]
    build = cfg["buildCommand"]
    assert "quarto render paper" in build and "public/whatnut/web" in build
    assert "python" not in build, (
        "the Vercel build renders the committed index.qmd; no Python"
    )
    assert {"source": "/", "destination": "/whatnut/", "permanent": False} in cfg[
        "redirects"
    ]
    # cleanUrls rewrites /whatnut/web/index.html?v=... to /whatnut/web?v=... (a 308
    # observed on the live deployment), and the manuscript's relative assets then
    # resolve against /whatnut/ and 404. Keep it off.
    assert cfg.get("cleanUrls") is not True
    for cmd in (build, cfg["installCommand"]):
        assert len(cmd) <= 256, (
            "Vercel caps build and install commands at 256 characters"
        )


def test_wrapper_numbers_match_the_paper():
    """Every number in the wrapper's description is a data-value span whose text
    equals paper/values.json, so the page cannot drift from the manuscript."""
    import json
    import re

    html = (ROOT / "public" / "whatnut" / "index.html").read_text(encoding="utf-8")
    values = json.loads((ROOT / "paper" / "values.json").read_text(encoding="utf-8"))
    spans = re.findall(r'<span data-value="([a-z][a-z0-9_]*)">(.*?)</span>', html, re.S)
    assert spans, "the wrapper description carries no data-value numbers"
    for name, shown in spans:
        assert name in values, f"{name} is not in paper/values.json"
        assert shown == values[name]["text"], (
            f"{name}: wrapper {shown!r} vs paper {values[name]['text']!r}"
        )
    desc = re.search(r'<p class="paper-desc">(.*?)</p>', html, re.S).group(1)
    bare = re.sub(r'<span data-value="[a-z0-9_]+">.*?</span>', "", desc, flags=re.S)
    # The reference case's inputs (the age and the amount) are the question,
    # not results, and the manuscript states them in plain text too.
    revision = re.search(r"revision \d+", bare).group(0)
    for fixed in ("40-year-old", "15 grams", revision):
        bare = bare.replace(fixed, "")
    assert not re.findall(r"\d", bare), "untagged digit in the description"
