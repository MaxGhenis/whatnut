# What Nut, from scratch: design

This branch replaces the 30-prior nutrient model with a small, fully sourced model. The paper answers three questions for a US adult:

1. **How much life does eating nuts buy?** Change in remaining life expectancy from sustaining an intake change from background B to B + Δ grams a day of nuts (tree nuts and peanuts), by age and sex.
2. **How much more, given what you already eat?** The marginal value of the next grams, given background nut (and seed) intake.
3. **Which nut?** Whether nut type changes the answer, and what each costs per life-year.

Every number the paper prints comes from `results/results.json`, which the pipeline computes from rows in `data/`. Every effect size in the model is read from `data/evidence.yaml` by row id; model code holds no effect-size literals.

## Layout

```
data/
  evidence.yaml               verified evidence rows (schema below)
  sources/crossref/           cached Crossref records, one JSON per DOI
  life_tables/                NVSR 72-12 (US life tables, 2021) Table 2 (male), Table 3 (female): raw xlsx + parsed csv + MANIFEST.json (url, sha256, fetched_at)
  causes/                     share of deaths by cause, age, sex (CVD I00-I99, CHD I20-I25, stroke I60-I69, cancer C00-C97): raw source + parsed csv + MANIFEST.json
  composition/                USDA FoodData Central JSON per food + parsed composition.csv (per 100 g) + gram weights
  prices/prices.csv           dated retail prices with URLs
  curves/                     dose-response points and reproduction targets (Aune 2016 nonlinear, IHME Burden of Proof, Fadnes 2022)
  calibration/                Schwingshackl 2021's 23 intake-v-intake pairs, read by hand from Supplementary Figure 9 + MANIFEST.json
scripts/                      fetchers (one per data folder), check_citations.py, build_bib.py
src/whatnut/
  data.py                     loaders; verify sha256 against MANIFEST.json on load
  lifetable.py                life expectancy from qx with hazard multipliers and a phase-in ramp
  model.py                    dose curves, scenarios, calibration pooling, Monte Carlo
  pipeline.py                 writes results/results.json and paper/figures/*.png (deterministic)
  results.py                  typed accessors over results.json; verify()
paper/
  _quarto.yml
  index.qmd.in                the manuscript template (prose + {{placeholders}}); source of truth for prose
  fill_paper.py               fills the template from results.json -> index.qmd + values.json
  render_paper.py             fill, assert no engine cells, quarto render with no kernel, copy to public/whatnut/web/
  references.bib              generated from evidence.yaml by scripts/build_bib.py
  figures/                    written by the pipeline
public/whatnut/index.html     wrapper page (paper-embed pattern) embedding web/index.html?v=<version>
results/results.json
tests/
```

The old model (`src/whatnut/{config,model,lifecycle,pipeline,results,evidence,figures}.py`, `data/*.yaml`, `docs/`) is deleted on this branch. Raw artifacts under `src/whatnut/data/raw/` move to `data/` where reused.

## Model

**Baseline.** Sex-specific annual death probabilities q_s(a) from NVSR 72-12 Tables 2 and 3 (single years 0–99; q = 1 at 100). Hazard h = −ln(1 − q). Remaining life expectancy computed with the mid-year convention; a test requires the baseline to reproduce the tables' own e_x within 0.05 years at ages 0, 20, 40, 60 and 80.

**Intervention.** From age a0, intake moves from B to B + Δ g/day and stays there. The hazard at age a is multiplied by

  M(a) = exp( φ(a) · c · [ f(B + Δ) − f(B) ] )

where f(g) is the log relative risk at intake g (f(0) = 0), c is the causal multiplier for the scenario being computed, and φ(a) is a linear phase-in from 0 at a0 to 1 at a0 + T. T = 10 years in the main case (Fadnes et al. 2022's convention), with 0 and 20 as sensitivities. Output: ΔLE = e_treated(a0) − e_baseline(a0), in undiscounted years and days.

**Dose curves.**
- *All-cause, primary:* f from Aune et al. 2016's nonlinear all-cause dose-response (points extracted into `data/curves/`), interpolated monotonically in log RR, flat beyond the highest observed intake. If only the linear per-28 g estimate and a stated plateau are available, use f(g) = ln(RR28) · (1 − e^(−g/k)) / (1 − e^(−28/k)), with k set so 90% of the 28 g effect is reached at the reported plateau dose. Document which was used.
- *CVD-only carve-out:* Aune's CVD dose-response applied only to the CVD share of the hazard: h' = h · [1 − p_cvd(a,s) + p_cvd(a,s) · RR_cvd(g)].
- *LDL pathway (first draft: "randomized floor"; decision 4):* LDL change from nut trials (Del Gobbo et al. 2015, linear per 28.4 g) converted to mmol/L, times the Cholesterol Treatment Trialists' 2010 slope per 1 mmol/L. Two versions: CHD-death slope applied to CHD deaths only (`ldl_chd`) and all-cause-mortality slope applied to all deaths (`ldl_all`).

**Scenarios (the causal multiplier c).** (First draft: "bracket"; revised by decisions 3 and 16.)
- Face value: c = 1 on the cohort curve.
- Calibrated: the cohort RR scaled by Schwingshackl et al. 2021's ratio of risk ratios (RCT over cohort), c = ln(RR28 · RRR) / ln(RR28). The main calibration uses all 71 pairs; the mortality calibration the all-cause-mortality pairs; three more strata are sensitivities (decision 3, revised).
- Cardiovascular deaths only, and the two LDL-pathway scenarios, as above.
- A transparent dial at c = 0.1, 0.33 and 1 (reported in one sentence of Results).

**Uncertainty.** Monte Carlo, n = 20,000, fixed seed. RR28 lognormal from its CI (the curve's shape scales with the draw); RRR lognormal from its prediction interval; LDL slope normal from its CI; CTT slopes lognormal from their CIs. Report mean and 80% and 95% intervals. Common random numbers across scenarios.

**Nut type.** The main model gives every nut the same per-gram class effect: nut trials show no significant heterogeneity in LDL lowering by nut type (Del Gobbo et al. 2015). Nut-specific evidence is tabulated, not modeled. One sensitivity adds an ALA channel for nuts with ALA: Naghshi et al. 2021's all-cause slope per gram of ALA, applied only to ALA inside the observed 0–3 g/day range given background ALA, at the same causal multiplier as the class effect.

**Cost.** Dated retail prices per kg → $/yr at the modeled dose → cost per life-year gained at 3% discounting of both costs and life-years (ratio of means), plus undiscounted $/yr.

**Outputs.** Sex ∈ {female, male}; a0 ∈ {30, 40, 50, 60, 70}; Δ ∈ {5, 10, 15, 20, 28, 40} g/day; B ∈ {0, 10, 20, 28} g/day; nut ∈ {walnut, almond, pistachio, pecan, hazelnut, macadamia, cashew, peanut}. Brazil nut appears only in the selenium note.

**Reproduction checks (tests).** (1) Baseline e_x matches NVSR. (2) Fadnes 2022: with their US inputs (nuts 0 → 25 g/day from age 20, their relative risk, 10-year phase-in), ΔLE for US men lands within 15% of their 2.0 years; the test prints the gap. (3) results.json regenerates byte-identically from a clean clone.

## Evidence row schema (`data/evidence.yaml`)

```yaml
- id: aune2016_allcause_per28g        # snake_case, unique
  kind: cohort_meta_dose_response     # cohort_meta_dose_response | cohort | rct_mediator | mediator_slope | rct_hard_endpoint | mendelian_randomization | calibration_corpus | reference_value | lab_or_storage_study | trial_biomarker
  exposure: "Total nuts (tree nuts and peanuts), per 28 g/day"
  outcome: "All-cause mortality"
  measure: RR                         # RR | HR | OR | RRR | mean_difference | value
  unit: null                          # e.g. mg/dL per 28.4 g/day
  estimate: 0.78
  ci_low: 0.72
  ci_high: 0.84
  ci_level: 0.95
  pi_low: null
  pi_high: null
  support: "Intakes observed roughly 0 to 30 g/day"   # observed exposure range, where relevant
  population: "..."
  notes: "..."                        # design, adjustment, heterogeneity, funding
  source:
    key: aune2016nut                  # bib key
    doi: "10.1186/s12916-016-0730-3"
    pmid: "27916000"
    pmcid: "PMC5137221"
    first_author: "Aune"
    authors: "Aune D, Keum N, Giovannucci E, ..."
    title: "..."
    journal: "BMC Medicine"
    year: 2016
    volume: "14"
    issue: "1"
    pages: "207"
  locator: "Abstract; Results, Table 2"
  verified:
    doi_resolves: true
    title_matches: true
    first_author_matches: true
    value_checked_in: "full text"     # abstract | full text | data file | api
    checked_on: "2026-09-23"
```

Rules: a number enters `estimate`/`ci_*` only if the checker read it in the source this session. No quotes longer than 15 words. `scripts/check_citations.py` resolves every DOI on Crossref and fails on any title or first-author mismatch (offline mode compares against `data/sources/crossref/`).

## Decisions after the data check (2026-09-23)

The integrity check (`data/CHECK.md`) found seven places where the evidence constrains the design above. These decisions supersede the text above where they conflict.

1. **Baseline year: 2023.** NVSR 74-06 (United States Life Tables, 2023) replaces NVSR 72-12 (2021, a COVID peak year: COVID was 12% of 2021 deaths). Cause shares come from the 2023 NCHS multiple-cause mortality file, checked against published 2023 totals. 2021 stays available as a sensitivity only if it costs nothing extra.
2. **Aune dose curve.** Main case: Aune 2016 Additional file 1 Table S15 (all-cause) and S14 (CVD mortality) points at 0, 5, 10, 15, 20, 25 and 28 g/day, made nonincreasing by a running minimum (the curve holds its lowest RR once reached), interpolated linearly in log RR between points, flat beyond 28 g. Sensitivities: (a) the points as printed, interpolated with PCHIP in log RR (this allows the small uptick above 20 g); (b) the linear per-28 g estimate (RR 0.78) with the plateau shape f(g) = ln(RR28)·(1 − e^(−g/k))/(1 − e^(−28/k)), 90% of the effect at 15 g. Uncertainty: scale the whole curve by the draw of the per-28 g RR relative to its mean (lognormal from the CI of the row the curve's 28 g point comes from).
3. **Calibration.** `calibrated` uses the dietary intake versus dietary intake stratum (RRR 0.98, PI 0.90–1.07): c_cal = ln(RR·RRR)/ln(RR) may exceed 1, and PI draws may fall on both sides of 1; that is what the calibration says. `calibrated_all_cause` uses the all-cause-mortality stratum (RRR 1.17, PI 0.99–1.39; mostly supplement trials). Also report the overall stratum (1.09). None of the 23 intake-versus-intake pairs is a nut; the paper says so.
4. **Randomized floor by nut type.** Tree nuts: Del Gobbo 2015 LDL from randomized trials only (−4.2 mg/dL per 28.4 g/day; the −4.8 estimate pools nonrandomized trials and is a sensitivity; Del Gobbo excluded peanuts). Peanuts: Jafari Azad 2020 (−3.31 mg/dL, P = 0.472; SE derived from the P value). Linear in dose over 0–40 g/day (Del Gobbo reports larger effects at ≥ 60 g/day, outside this range). CTT slopes drawn with the z for each row's `ci_level` (the CHD-death row is a 99% CI). LDL unit conversion: 38.67 mg/dL per mmol/L (structural constant).
5. **Life table open interval.** Use the table's own e100: T100 = l100 · e100 at baseline; under treatment the open interval is e100 / M(100). The baseline test then holds within 0.01 years at every age.
6. **Fadnes reproduction.** Inputs we can match: RR 0.84 at 25 g/day (their input, equal to Aune S15), 10-year linear phase-in, start at age 20, 0 → 25 g/day, all-cause. Baseline differs (they used GBD 2019 US mortality, e20 = 57.8 for men); the test runs on our baseline, prints ours versus theirs for both sexes, and passes within 15%.
7. **ALA sensitivity.** Naghshi 2021's included intakes span 0.35–3.0 g/day. Background ALA defaults to the US adult mean, 1.93 g/day (WWEIA 2017–March 2020); a nut's ALA counts only for the part of total intake inside [max(background, 0.35), 3.0]. Second scenario: background 5 g/day (a seed-heavy diet), where walnut ALA counts for nothing.
8. **Seeds.** Aune's exposure is tree nuts and peanuts; IHME's includes seeds. Background B in the main model counts nuts only; the paper notes the seed question.
9. **Brazil nut.** Not modeled; appears only in the selenium note.
10. **Evidence rows for reference data.** The life tables, the mortality file, USDA FoodData Central, IHME Burden of Proof and the Fadnes targets each get an evidence row (kind `reference_value` or `life_table`), so the bibliography and the citation check cover them. `source.url` is allowed when a source has no DOI.

## Revision after review (2026-09-24)

Six reviewers read the first full draft: numbers and citations, mechanism against code, a hostile referee, reproduction from a clean clone, the deploy wrapper, and voice. These decisions supersede the matching earlier ones.

3 (revised). **Calibration.** The main calibration (`calibrated`) uses all 71 Schwingshackl pairs (RRR 1.09, PI 0.81–1.46) because it picks no subset of comparisons. The paper reports five strata: all-cause-mortality pairs (1.17, `calibrated_mortality`, the second calibration in the main results), pairs whose cohort estimate was protective (1.12, `calibrated_protective`), all 71 pairs, the six ALA and Mediterranean-diet intake pairs pooled here (about 1.07, `calibrated_analog`) and the intake-versus-intake stratum (0.98, `calibrated_diet`). The intake stratum was the first draft's "matching" calibration; its pairs include pregnancy and colorectal-adenoma outcomes, single pairs range 0.63–3.07, and the authors caution that the ratio's direction depends on the direction of the underlying effects, so it is a sensitivity. Round 2: the pipeline pools subsets of the 23 intake pairs (`calibration.intake_subsets` in results.json, from `data/calibration/` through its manifest): the 15 without pregnancy or colorectal outcomes pool to about 0.97 and the 19 whose cohort estimate was protective to about 1.00, so neither objection moves the intake answer toward 1.09, and the ratios above 1 come from supplement comparisons (supplement-versus-status pairs, 1.29). Each stratum is reported with both anchors: Aune's linear per-28 g estimate (main) and the main curve's own relative risk at 28 g.

4 (revised). **LDL pathway, not a floor.** The randomized scenarios are the LDL pathway. They can understate the effect (other pathways; statin trials last about five years while lifelong lower LDL does more per mmol/L) or overstate it (LDL effects from 4–6 week trials at about 60 g/day, a nonlinear dose-response with larger effects at 60 g/day or more, and the one two-year trial found less per gram).

11. **Reference dose 15 g/day.** The main curve first reaches its minimum at 15 g (a test checks), so the reference case, the scenario figure, the sensitivity and calibration tables, the cost figure and the ALA sensitivity use 15 g; the reference table adds one Aune serving (28 g).

12. **New sensitivities.** The curve measured from 5 g, Aune's first tabulated intake, so the step from none to some counts for nothing; the curve rescaled to the cohorts with ten or more years of follow-up (RR 0.84 per 28 g) and to the estimate without the five smallest studies (0.80), each drawn on the main estimate's column; deaths from external causes (ICD-10 V01–Y89, a new column in the cause shares) left out of the multiplier; the log relative risk falling linearly to half between 65 and 85 (a modeling choice); the fixed-effect ALA slope (0.99); sex-specific background ALA. Round 2: in the two rescaled rows each calibration recomputes c against the row's own per-28 g draw (`Model.c(member, anchor, rr_role)`), so the ratio of risk ratios applies to the association the row assumes and eq-calibration holds draw by draw (the main calibration keeps about 51% of the ten-year cohorts' association, not the main case's 65%); the curve measured from 5 g keeps Aune's main estimate and so the main c. Leaving out external causes applies to the all-deaths LDL pathway too (structure `nonexternal`); the coronary LDL pathway and the cardiovascular scenario already act on one cause.

13. **Nearest pairs.** The six pairs are evidence rows (`schwingshackl2021_pair_*`), pooled by DerSimonian–Laird with a t(k − 2) prediction interval (`model.pool_ratios`; `model.pool_stats` refuses fewer than three rows, where that interval is undefined). They rest on two trial sources, and the Mediterranean-diet trial evidence is PREDIMED with both Mediterranean arms combined. `data/calibration/` holds all 23 intake pairs read from Supplementary Figure 9; a test pools them and reproduces the published 0.98 (0.93–1.04), PI 0.90–1.07.

14. **Estimand.** Nuts eaten in place of other calories, which is what energy-adjusted cohort analyses describe. Most lipid trials describe nuts added to the diet: of Del Gobbo's 61 trials, 47 gave nuts on top of a common background diet and 14 advised participants to keep total energy constant (row `delgobbo2015_ldl_per28g`, notes). The paper reports results as nuts eaten in place of other calories and says the LDL pathway rests mostly on trials that added them.

15. **Engine.** Each draw's gain depends on the draw only through its scalar log multiplier, so `Model.gain` evaluates the life table on 1,025 multipliers spanning the draws and interpolates (error under 0.001 day, which `tests/test_model.py::test_interpolated_gain_matches_exact` enforces against evaluating every draw).

16. **Names.** "Scenarios", not a "bracket" of "members": LDL pathway, coronary deaths (`ldl_chd`); LDL pathway, all deaths (`ldl_all`); cardiovascular deaths only; mortality calibration; main calibration; face value. One label set (`model.SCENARIO_LABEL`, written to results.json) feeds the figures, the tables and the prose.

17. **Sources the reviewers added.** PREDIMED's all-cause and cardiovascular death and stroke hazards and its nut mix (NEJM full text), PREDIMED's observational nut-frequency analysis (Guasch-Ferré 2013), Aune's follow-up strata, Luu's peanut-butter and second-fifth estimates, SELECT's diabetes result, Silverman 2016 (non-statin LDL lowering), Ference 2017 (cumulative LDL exposure), the WAHA two-year walnut trial, Liu 2020 (changes in nut intake), the 2022 umbrella review (which reuses Aune's estimate) and a 2026 meta-analysis (abstract only; its highest-versus-lowest estimate is used because its per-serving unit looks misprinted). The IHME curve is cited to IHME's visualization, and Zheng 2022 for the method. Round 2: Aune's per-serving estimates for infectious, kidney, respiratory and diabetes mortality (`aune2016_*_per28g_mortality`; the abstract's I² for infections, 54%, disagrees with Table 1's 0%, noted in the row), and PREDIMED's nut intake from Guasch-Ferré 2013, one row per quantity: the three baseline groups (0, 4.9 and 25.7 g/day; n = 2,118, 2,803 and 2,295, written '(n = N' in `population` and read by `EvidenceRow.count`) and each arm's change (+15.95, −0.80, −3.12 g/day). The pipeline's `predimed_check` applies the arms' changes to each baseline group on the main curve at face value: HR about 0.89 at full effect and 0.97 averaged over the trial's median 4.8 years with the ten-year phase-in, both inside the trial's interval for death (0.86–1.47).

## Deviations

Where the model (src/whatnut/, builder B1) departs from or fills a gap in the text above. One line each.

- **Curve uncertainty row.** "The row the curve's 28 g point comes from" is read as the linear per-28 g row: all-cause scales by draws of `aune2016_allcause_per28g` (0.78, 0.72–0.84), the CVD curve by `aune2016_cvd_per28g_mortality` (0.76, 0.67–0.86); the S14/S15 pointwise CIs are not used.
- **RR28 in the calibration.** c = ln(RR28 · RRR)/ln(RR28) uses the same per-28 g draw as the curve scale (for a rescaled curve, that curve's own per-28 g draw; decision 12). On the linear per-28 g estimate the calibrated log RR at 28 g is ln RR28 + ln RRR, draw by draw; on the main curve, whose value at 28 g is ln 0.82 rather than ln 0.78, it is 0.80 × (ln RR28 + ln RRR). The alternative anchor, c = ln(RR_curve(28) · RRR)/ln RR_curve(28), is reported for every stratum (decision 3, revised).
- **Prediction-interval level.** The schema has no level for `pi_low`/`pi_high`; RRR draws take the row's `ci_level` (95%, as Schwingshackl 2021 reports).
- **All strata are grid members.** Every calibration stratum (`calibrated` on all pairs, `calibrated_mortality`, `calibrated_protective`, `calibrated_analog`, `calibrated_diet`) sits in the grid.
- **CVD-only carve-out at c = 1.** DESIGN does not give its multiplier; it takes the CVD curve at face value (`ASSUMPTIONS["cvd_only_c"]`).
- **Phase-in.** φ scales the log hazard multiplier (Fadnes 2022 does not say whether they ramp the HR or its log), takes its mid-year value in each single year of age, and applies to every scenario, including the LDL pathway and the cause-restricted scenarios (h' = h[1 − p + p·exp(φβ)]).
- **Cause shares by age.** The 2023 file has 10-year groups from 25–34 to 85+; single ages take their group's share, ages under 25 take the 25–34 share, and the open interval takes 85+. Only the age figure starts below 30, at 20 (its coronary LDL pathway reads the 25–34 share for ages 20–24); the grid starts at 30.
- **Peanut LDL dose.** Jafari Azad 2020's doses are paywalled; its WMD (−3.31 mg/dL) is read as the effect of one 28.4 g/day serving, and its SE comes from P = 0.472, parsed from the row's notes because the schema has no P-value field.
- **LDL pathway above face value at high background.** The running-minimum curve is flat from 15 g/day, so face value is exactly zero for B ≥ 15 while the linear LDL pathway is not; the ordering LDL pathway ≤ face value holds, and is tested, from zero background only.
- **Rows without a DOI.** Crossref cannot match these, so they have `title_matches: null`. The model reads three: `wweia_1720_ala_men`, `wweia_1720_ala_women` and `nchs_mortality_2023`; the paper's fill also reads `ihme_bop_nuts_seeds_ihd`, `fdc_brazil_nut_selenium`, `fped_nut_oz_eq_grams` and `wweia_1720_nuts_seeds_adults`. `data.row` accepts a row without a DOI only when it carries `source.url` and `value_checked_in`, so every pipeline run and every fill enforces this, and a test checks the model's rows. `scripts/build_bib.py` gives each URL-cited source a `urldate`, the latest `checked_on` among its rows.
- **Background ALA.** The sex-specific US means (rows `wweia_1720_ala_men`, 2.16, and `wweia_1720_ala_women`, 1.72 g/day; decision 12) and 5 g/day, not the brief's 1.5 g.
- **ALA channel scope.** Reported at the reference case (age 40, 0 → 15 g/day) for face value and the main calibration, with the random-effects and the fixed-effect slopes, as total gain and as the paired increment over the class effect.
- **Cost.** Price is the median of the primary retail rows per nut (`prices_by_nut.csv`); costs accrue while alive (treated survival), each single year discounted at mid-year and the open interval at its baseline midpoint; cost per life-year is reported at the reference dose for the main and mortality calibrations, face value and both LDL-pathway scenarios, with peanuts' LDL pathway using peanut LDL.
- **Extra sensitivities, free with data on disk.** The 2021 baseline (archived NVSR 72-12 tables and 2021 cause shares) for the reference case and the Fadnes rows; the LDL pathway with all 61 of Del Gobbo's controlled trials, randomized and not (−4.8 mg/dL).
- **Fadnes reproduction rows.** The test uses the age-20 targets from evidence rows `fadnes2022_us_{men,women}_25g`; results.json also compares ages 40, 60 and 80 from `data/curves/fadnes2022_targets.yaml` (the age-40 and age-80 targets were read from figure images).
- **Linear-plateau sensitivity beyond 28 g.** The formula keeps rising slowly past 28 g/day, as written; it is not flattened.
- **Tooling.** pytest no longer runs coverage (`--cov` dropped with pytest-cov); seaborn, black and mypy left the dependencies; the fetch scripts' `requests` and `pypdf` moved to a `fetch` extra. Hypothesis (in the `dev` extra) runs `tests/test_properties.py`, which checks the pooling, the phase-in share, the PREDIMED check, group-size parsing and the fill's rounding on arbitrary inputs, not only the paper's.
