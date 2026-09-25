"""The /whatnut/ wrapper stays consistent with the manuscript it frames.

Pattern (paper-embed, from PolicyBench's /paper): /whatnut/ is a shelled
wrapper (site header, paper header, actions, one versioned sandboxed iframe of
the raw manuscript at /whatnut/web/, footer). The version string lives once in
paper/VERSION; every manuscript link in the wrapper carries it.

Tests of the rendered site (paper/_build/, public/whatnut/web/) skip when no
render is on disk, unless WHATNUT_REQUIRE_RENDER=1 (CI sets it after
paper/render_paper.py), in which case a missing render fails them.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import struct
import subprocess
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "paper"
WRAPPER = ROOT / "public" / "whatnut" / "index.html"
WEB = WRAPPER.parent / "web"
VERSION = (ROOT / "paper" / "VERSION").read_text(encoding="utf-8").strip()
MANUSCRIPT = f"web/index.html?v={VERSION}"
PDF = f"web/index.pdf?v={VERSION}"
CANONICAL = "https://www.maxghenis.com/whatnut/"
SOCIAL_IMAGE = CANONICAL + "web/figures/days_by_dose.png"
REQUIRE_RENDER = os.environ.get("WHATNUT_REQUIRE_RENDER") == "1"

sys.path.insert(0, str(PAPER))
import render_paper  # noqa: E402

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
    """Every web/ link is the iframe's manuscript URL, except the one PDF link,
    which carries the same version."""
    links = [
        attrs["href"]
        for tag, attrs in doc.tags
        if tag == "a" and attrs.get("href", "").startswith("web/")
    ]
    html_links = [link for link in links if link != PDF]
    assert len(html_links) >= 2, "an 'Open standalone HTML' action and a footer link"
    assert set(html_links) == {MANUSCRIPT}
    assert links.count(PDF) == 1, "one 'Download PDF' action"


def test_actions_and_footer(html):
    actions = re.search(
        r'<nav class="paper-actions" aria-label="Paper actions">(.*?)</nav>', html, re.S
    )
    assert actions, "the actions bar is missing"
    anchors = re.findall(r"<a [^>]*>[^<]*</a>", actions.group(1))
    assert anchors == [
        f'<a class="primary" href="{MANUSCRIPT}">Open standalone HTML</a>',
        f'<a href="{PDF}">Download PDF</a>',
        '<a href="https://github.com/MaxGhenis/whatnut">Code and data</a>',
    ], "primary action, then Download PDF, then the code"
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


def _meta(doc: _Collect) -> dict[str, str]:
    return {
        attrs.get("property") or attrs.get("name"): attrs.get("content")
        for tag, attrs in doc.tags
        if tag == "meta"
    }


def test_og_and_canonical(doc):
    meta = _meta(doc)
    assert meta["og:type"] == "article"
    assert meta["og:url"] == CANONICAL
    assert meta.get("og:title") and meta.get("og:description")
    canon = [
        attrs["href"]
        for tag, attrs in doc.tags
        if tag == "link" and attrs.get("rel") == "canonical"
    ]
    assert canon == [CANONICAL]


def _png_size(path: Path) -> tuple[int, int]:
    head = path.read_bytes()[:24]
    assert head[:8] == b"\x89PNG\r\n\x1a\n" and head[12:16] == b"IHDR", path
    return struct.unpack(">II", head[16:24])


def test_social_card(doc):
    """A large card with a figure the render publishes under /whatnut/web/,
    its true pixel size, and alt text that says what it shows."""
    meta = _meta(doc)
    assert meta["twitter:card"] == "summary_large_image"
    assert meta["og:image"] == SOCIAL_IMAGE
    rel = SOCIAL_IMAGE.removeprefix(CANONICAL + "web/")
    source = PAPER / rel
    assert source.exists(), f"{rel} is not in paper/"
    qmd = (PAPER / "index.qmd").read_text(encoding="utf-8")
    assert f"]({rel})" in qmd, (
        f"the manuscript does not use {rel}, so no render ships it"
    )
    width, height = _png_size(source)
    assert (meta["og:image:width"], meta["og:image:height"]) == (
        str(width),
        str(height),
    )
    assert meta["og:image:alt"] == (
        "Days of remaining life expectancy gained at age 40 by grams of nuts a day"
    )


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
    """render_paper.stamp_wrapper is idempotent on the committed wrapper, and a
    bump reaches every versioned link, the pill and the description."""
    version, revision, date = render_paper.read_version()
    html = WRAPPER.read_text(encoding="utf-8")
    assert render_paper.stamp_wrapper(html, version, revision, date) == html
    assert f"revision {revision} of the manuscript" in html
    bumped = render_paper.stamp_wrapper(html, "r12-20261001", 12, "2026-10-01")
    assert f"?v={VERSION}" not in bumped
    assert bumped.count("?v=r12-20261001") == html.count(f"?v={VERSION}")
    assert "web/index.pdf?v=r12-20261001" in bumped
    assert "Revision 12 · 2026-10-01 · Max Ghenis" in bumped
    assert f"revision {revision} of the manuscript" not in bumped
    assert "revision 12 of the manuscript" in bumped
    # Only the stamped strings change; the phrase keeps its place in the
    # description.
    desc = re.compile(r'<p class="paper-desc">(.*?)</p>', re.S)
    assert desc.search(bumped).group(1) == desc.search(html).group(1).replace(
        f"revision {revision} of the manuscript", "revision 12 of the manuscript"
    )


def test_stamp_handles_a_wrapped_phrase():
    html = WRAPPER.read_text(encoding="utf-8")
    phrase = re.search(r"revision \d+ of the manuscript", html).group(0)
    wrapped = html.replace(phrase, phrase.replace(" of the ", "\n      of the "))
    bumped = render_paper.stamp_wrapper(wrapped, "r3-20261101", 3, "2026-11-01")
    assert "revision 3\n      of the manuscript" in bumped


@pytest.mark.parametrize(
    "breakage",
    [
        "drop the description phrase",
        "repeat the description phrase",
        "drop the PDF link",
        "repeat the PDF link",
        "drop the pill",
    ],
)
def test_stamp_refuses_a_wrapper_it_cannot_fully_stamp(breakage):
    html = WRAPPER.read_text(encoding="utf-8")
    phrase = re.search(r"revision \d+ of the manuscript", html).group(0)
    pdf_link = f'<a href="{PDF}">Download PDF</a>'
    pill = re.search(r"Revision \d+ · \d{4}-\d{2}-\d{2}", html).group(0)
    broken = {
        "drop the description phrase": html.replace(phrase, "this revision"),
        "repeat the description phrase": html.replace(phrase, f"{phrase}, {phrase}"),
        "drop the PDF link": html.replace(pdf_link, ""),
        "repeat the PDF link": html.replace(pdf_link, pdf_link * 2),
        "drop the pill": html.replace(pill, "Revision"),
    }[breakage]
    assert broken != html
    with pytest.raises(render_paper.RenderError):
        render_paper.stamp_wrapper(broken, "r2-20261001", 2, "2026-10-01")


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
    assert "python" not in build, (
        "the Vercel build renders the committed index.qmd; no Python"
    )
    # The same two renders as paper/render_paper.py (Quarto 1.9 rejects
    # `--to html,typst`), then _build/ (HTML, figures, index.pdf) becomes web/.
    steps = [step.strip() for step in build.split("&&")]
    renders = [step for step in steps if step.startswith("quarto render")]
    assert renders == [
        "quarto render paper --to html --no-execute",
        "quarto render paper --to typst --no-execute",
    ]
    assert steps[-1] == "cp -R paper/_build/. public/whatnut/web/"
    assert steps[0].startswith("export PATH=/tmp/quarto/bin:"), (
        "both quarto calls need the installed Quarto on PATH"
    )
    # cleanUrls rewrites /whatnut/web/index.html?v=... to /whatnut/web?v=... (a 308
    # observed on the live deployment), and the manuscript's relative assets then
    # resolve against /whatnut/ and 404. Keep it off.
    assert cfg.get("cleanUrls") is False
    for cmd in (build, cfg["installCommand"]):
        assert len(cmd) <= 256, (
            "Vercel caps build and install commands at 256 characters"
        )


def test_vercel_redirects():
    """Old and bare URLs land on the wrapper; PDF guesses land on the PDF, with
    a temporary redirect because the PDF's place may change."""
    cfg = json.loads((ROOT / "vercel.json").read_text(encoding="utf-8"))
    redirects = {
        r["source"]: (r["destination"], r["permanent"]) for r in cfg["redirects"]
    }
    assert len(redirects) == len(cfg["redirects"]), "duplicate redirect source"
    assert redirects == {
        "/": ("/whatnut/", False),
        "/whatnut": ("/whatnut/", True),
        "/whatnut/appendix": ("/whatnut/", True),
        "/whatnut/appendix/": ("/whatnut/", True),
        "/whatnut/appendix.html": ("/whatnut/", True),
        "/whatnut/whatnut.pdf": ("/whatnut/web/index.pdf", False),
        "/whatnut/index.pdf": ("/whatnut/web/index.pdf", False),
    }
    # Vercel matches a literal source exactly (path-to-regexp, strict: true), so
    # "/whatnut" does not also match "/whatnut/". No destination may be a
    # source, which rules out loops and chains.
    for source, (destination, _) in redirects.items():
        assert not re.search(r"[:(*?]", source), f"{source} is not a literal path"
        assert destination not in redirects, f"{source} -> {destination} chains"


def test_manuscript_date_matches_version():
    """The filled manuscript's front-matter date is the date in paper/VERSION:
    the template writes {{version_date}}, which fill_paper takes from VERSION."""
    template = (PAPER / "index.qmd.in").read_text(encoding="utf-8")
    assert re.search(r"^date: \{\{version_date\}\}$", template, re.M), (
        "the template's date should be the {{version_date}} placeholder"
    )
    filled = (PAPER / "index.qmd").read_text(encoding="utf-8")
    front = filled.split("---", 2)[1]
    date = yaml.safe_load(front)["date"]
    m = re.fullmatch(r"r\d+-(\d{4})(\d{2})(\d{2})", VERSION)
    assert str(date) == "-".join(m.groups()), (
        f"index.qmd date {date} differs from paper/VERSION {VERSION}"
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


# --------------------------------------------------------------------------
# The PDF and the external links (Quarto config, post-render script, render)
# --------------------------------------------------------------------------


def _quarto_cfg() -> dict:
    return yaml.safe_load((PAPER / "_quarto.yml").read_text(encoding="utf-8"))


def test_quarto_builds_a_typst_pdf():
    """Typst ships inside Quarto, so the quarto-only Vercel build makes the PDF
    too; no TeX format remains."""
    fmt = _quarto_cfg()["format"]
    assert set(fmt) == {"html", "typst"}
    typst = fmt["typst"]
    assert typst["citeproc"] is True
    assert typst["papersize"] == "us-letter"
    assert typst["margin"] == {"x": "1in", "y": "1in"}
    assert typst["fontsize"] == "11pt"
    assert typst["toc"] is False


def test_external_links_script_is_wired():
    """Quarto's link-external-newwindow works through JavaScript, which the
    sandboxed iframe never runs; the post-render script writes the attributes."""
    cfg = _quarto_cfg()
    assert cfg["project"]["post-render"] == "external_links.ts"
    assert (PAPER / "external_links.ts").exists()
    assert cfg["format"]["html"]["link-external-newwindow"] is False


FIXTURE = """<!doctype html><html><head>
<script>var s = '<a href="https://in.script/">x</a>';</script>
<style>a[href^="https://in.style/"] { color: red; }</style>
</head><body>
<!-- <a href="https://in.comment/">x</a> -->
<a href="https://doi.org/10.1/x">doi</a>
<a class="quarto-xref" href="#tbl-a">Table 1</a>
<a href="figures/x.png">relative</a>
<A HREF="HTTP://UPPER.example/">upper</A>
<a href="mailto:someone@example.com" class="email">mail</a>
<a href="https://example.com/a?b=1&amp;c=2" rel="me" target="_self">me</a>
<a title="1 > 0" href="https://example.com/gt">gt in a quoted value</a>
<a href="https://example.com/done" target="_blank" rel="noopener">done</a>
<abbr title="x">abbr</abbr>
</body></html>
"""


def _run_external_links(tmp_path: Path, html: str) -> str:
    quarto = shutil.which("quarto")
    if not quarto:
        if REQUIRE_RENDER:
            pytest.fail("quarto is not on PATH")
        pytest.skip("quarto is not on PATH")
    page = tmp_path / "page.html"
    page.write_text(html, encoding="utf-8")
    proc = subprocess.run(
        [quarto, "run", str(PAPER / "external_links.ts"), str(page)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    return page.read_text(encoding="utf-8")


def test_external_links_script(tmp_path):
    out = _run_external_links(tmp_path, FIXTURE)
    assert render_paper.external_links_not_in_new_tab(FIXTURE)
    assert render_paper.external_links_not_in_new_tab(out) == []
    for line in (
        '<a href="https://doi.org/10.1/x" target="_blank" rel="noopener">doi</a>',
        '<A HREF="HTTP://UPPER.example/" target="_blank" rel="noopener">upper</A>',
        '<a href="mailto:someone@example.com" class="email" target="_blank"'
        ' rel="noopener">mail</a>',
        '<a href="https://example.com/a?b=1&amp;c=2" rel="me noopener"'
        ' target="_blank">me</a>',
        '<a title="1 > 0" href="https://example.com/gt" target="_blank"'
        ' rel="noopener">gt in a quoted value</a>',
        '<a href="https://example.com/done" target="_blank" rel="noopener">done</a>',
        # untouched: internal links, scripts, styles, comments, other tags
        '<a class="quarto-xref" href="#tbl-a">Table 1</a>',
        '<a href="figures/x.png">relative</a>',
        "var s = '<a href=\"https://in.script/\">x</a>';",
        '<!-- <a href="https://in.comment/">x</a> -->',
        '<abbr title="x">abbr</abbr>',
    ):
        assert line in out, line
    assert _run_external_links(tmp_path, out) == out, "not idempotent"


def _rendered(path: Path) -> Path:
    if not path.exists():
        if REQUIRE_RENDER:
            pytest.fail(
                f"{path.relative_to(ROOT)} is missing; run paper/render_paper.py"
            )
        pytest.skip(f"no render at {path.relative_to(ROOT)}")
    return path


@pytest.mark.parametrize("site", [PAPER / "_build", WEB], ids=["_build", "web"])
def test_rendered_external_links_open_in_a_new_tab(site):
    html = _rendered(site / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<a [^>]*href="https://doi\.org/', html), "no DOI links rendered"
    assert render_paper.external_links_not_in_new_tab(html) == []


@pytest.mark.parametrize("site", [PAPER / "_build", WEB], ids=["_build", "web"])
def test_rendered_site_has_the_pdf_and_social_image(site):
    _rendered(site / "index.html")
    pdf = _rendered(site / "index.pdf")
    assert pdf.read_bytes().startswith(b"%PDF-")
    image = site / SOCIAL_IMAGE.removeprefix(CANONICAL + "web/")
    assert image.read_bytes() == (PAPER / "figures" / image.name).read_bytes()


def test_rendered_tables_scroll_in_their_own_box():
    """paper/styles.css makes each table's wrapper scroll sideways; the selector
    has to match the markup Quarto renders."""
    css = (PAPER / "styles.css").read_text(encoding="utf-8")
    assert re.search(
        r"figure\.quarto-float-tbl > div\s*\{\s*overflow-x:\s*auto;\s*\}", css
    )
    html = _rendered(PAPER / "_build" / "index.html").read_text(encoding="utf-8")
    floats = re.findall(
        r'<figure class="[^"]*\bquarto-float-tbl\b[^"]*">\s*<figcaption.*?</figcaption>'
        r"\s*<div[^>]*>\s*<table",
        html,
        re.S,
    )
    assert len(floats) == html.count("<table"), "a table outside figure > div"


def test_release_workflow_tags_the_paper_version():
    """The manuscript's code link is tree/<paper/VERSION>. A workflow creates that
    tag on each push to master when it is missing, so the link resolves on
    deploy; it reads the version from paper/VERSION and never moves a tag."""
    path = ROOT / ".github" / "workflows" / "tag.yml"
    assert path.exists(), "the tagging workflow is missing"
    wf = yaml.safe_load(path.read_text(encoding="utf-8"))
    on = wf.get("on", wf.get(True))  # YAML 1.1 reads the key `on` as true
    assert on == {"push": {"branches": ["master"]}}
    assert wf["permissions"] == {"contents": "write"}
    steps = [step for job in wf["jobs"].values() for step in job["steps"]]
    script = "\n".join(step.get("run", "") for step in steps)
    assert any(step.get("uses", "").startswith("actions/checkout@") for step in steps)
    assert "paper/VERSION" in script
    assert re.search(r"git ls-remote --exit-code --tags origin", script)
    assert 'git tag "$version" "$GITHUB_SHA"' in script
    assert 'git push origin "refs/tags/$version"' in script
    assert "--force" not in script and " -f " not in script
    # the manuscript links the same tag the workflow creates
    qmd = (PAPER / "index.qmd").read_text(encoding="utf-8")
    assert f"github.com/MaxGhenis/whatnut/tree/{VERSION})" in qmd
