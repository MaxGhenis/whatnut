# What nut?

How much life does eating nuts buy a US adult? The model answers three questions, by age and sex:

1. How many days of remaining life expectancy come from eating an extra Δ grams of nuts a day, for good.
2. How much the next grams add, given what the person already eats.
3. Whether the choice of nut changes the answer, and what each nut costs per life-year.

Every estimate comes as a set of scenarios: the LDL pathway (LDL lowering in randomized nut trials times the statin-trial slopes), the cohort dose-response restricted to cardiovascular deaths, the cohort curve calibrated by how trial estimates have compared with cohort estimates across 71 nutrition questions (Schwingshackl et al. 2021), and the cohort dose-response at face value. Read the paper at [maxghenis.com/whatnut](https://www.maxghenis.com/whatnut/). The design and model spec are in [DESIGN.md](DESIGN.md).

## Regenerate

```bash
uv sync --locked --extra dev                # the environment in uv.lock
uv run python -m whatnut.pipeline           # results/results.json and paper/figures/*.png
uv run python scripts/build_bib.py          # paper/references.bib from data/evidence.yaml
uv run python paper/render_paper.py         # fill paper/index.qmd, render HTML and PDF, stage public/whatnut/web/
uv run python -m http.server -d public      # preview at http://localhost:8000/whatnut/
```

`results/results.json` regenerates byte for byte across platforms and Python versions (a test checks it); the PNGs match byte for byte only with the locked matplotlib on the same operating system and CPU architecture.

Quarto 1.9.x must be on PATH, and nothing else: the PDF is typeset with Typst, which ships inside Quarto. The render runs no code.

## The manuscript is generated

`paper/index.qmd` is written by `paper/fill_paper.py` from the template `paper/index.qmd.in` and `results/results.json`. Never edit it by hand. Edit the prose in the template, where every number is a `{{placeholder}}` (or a `{{table:name}}` line) that `fill_paper.py` formats from the results; it fails on any unfilled placeholder or unused value, and `paper/values.json` records each printed number beside its unrounded source. Bump `paper/VERSION` (`rN-YYYYMMDD`) for each revision; it is the manuscript's date, and the render stamps it into the wrapper page at `public/whatnut/index.html`. The manuscript links its code at `tree/<version>`: on each push to master, `.github/workflows/tag.yml` creates that tag at the pushed commit if it does not exist (an existing tag is never moved).

## Evidence

Each effect size the model uses is a row in `data/evidence.yaml` with its source, locator and verification (schema in DESIGN.md); model code holds no effect-size literals. Crossref records for every DOI are cached in `data/sources/crossref/`, and the other inputs (life tables, cause-of-death shares, composition, prices, dose-response curves) live in the other `data/` folders with a `MANIFEST.json` of URLs and hashes.

## Checks

```bash
uv run python -m pytest                              # model, reproduction and paper tests
uv run python paper/fill_paper.py --check            # committed manuscript matches template + results
uv run python scripts/build_bib.py --check           # bibliography matches the evidence
uv run python scripts/check_citations.py --offline   # DOIs, titles, first authors vs Crossref (drop --offline to query live)
```

CI runs all four, with the tests on Python 3.10, 3.12 and 3.14, then renders the paper and checks the render. Vercel renders the committed `paper/index.qmd` to HTML and PDF with Quarto alone (no Python) and serves the wrapper at `/whatnut/`, the manuscript at `/whatnut/web/` and the PDF at `/whatnut/web/index.pdf`.

MIT license.
