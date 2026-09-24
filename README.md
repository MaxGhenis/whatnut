# What nut?

How much life does eating nuts buy a US adult? The model answers three questions, by age and sex:

1. How many days of remaining life expectancy come from eating an extra Δ grams of nuts a day, for good.
2. How much the next grams add, given what the person already eats.
3. Whether the choice of nut changes the answer, and what each nut costs per life-year.

Every estimate is bracketed: a randomized floor (LDL lowering in nut trials times the statin-trial slope), the cohort dose-response at face value, and the cohort curve calibrated by the ratio of trial to cohort estimates in paired diet-intake studies (Schwingshackl et al. 2021), which puts it slightly above face value. Read the paper at [maxghenis.com/whatnut](https://www.maxghenis.com/whatnut/). The design and model spec are in [DESIGN.md](DESIGN.md).

## Regenerate

```bash
uv pip install -e ".[dev]"
python -m whatnut.pipeline        # results/results.json and paper/figures/*.png
python scripts/build_bib.py       # paper/references.bib from data/evidence.yaml
python paper/render_paper.py      # fill paper/index.qmd, render with Quarto, stage public/whatnut/web/
python -m http.server -d public   # preview at http://localhost:8000/whatnut/
```

Quarto 1.9.x must be on PATH. The render runs no code: `render_paper.py` builds a PDF too when `xelatex` is installed.

## The manuscript is generated

`paper/index.qmd` is written by `paper/fill_paper.py` from the template `paper/index.qmd.in` and `results/results.json`. Never edit it by hand. Edit the prose in the template, where every number is a `{{placeholder}}` (or a `{{table:name}}` line) that `fill_paper.py` formats from the results; it fails on any unfilled placeholder or unused value, and `paper/values.json` records each printed number beside its unrounded source. Bump `paper/VERSION` (`rN-YYYYMMDD`) for each revision; the render stamps it into the wrapper page at `public/whatnut/index.html`.

## Evidence

Each effect size the model uses is a row in `data/evidence.yaml` with its source, locator and verification (schema in DESIGN.md); model code holds no effect-size literals. Crossref records for every DOI are cached in `data/sources/crossref/`, and the other inputs (life tables, cause-of-death shares, composition, prices, dose-response curves) live in the other `data/` folders with a `MANIFEST.json` of URLs and hashes.

## Checks

```bash
python -m pytest                              # model, reproduction and paper tests
python paper/fill_paper.py --check            # committed manuscript matches template + results
python scripts/build_bib.py --check           # bibliography matches the evidence
python scripts/check_citations.py --offline   # DOIs, titles, first authors vs Crossref (drop --offline to query live)
```

CI runs all four; Vercel renders the committed `paper/index.qmd` (no Python) and serves the wrapper at `/whatnut/` with the manuscript at `/whatnut/web/`.

MIT license.
