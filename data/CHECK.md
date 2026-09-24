# Data integrity check

Checked 2026-09-23, 23:10–23:25 EDT, against `data/` as the builders left it.
`data/evidence.yaml` sha256 at check time: `9d9453216b6770fc2f4d5259851eb947c83374b5e2029e76e8a0a59e1dd25c3f`. No file under `data/` or `scripts/` changed during the check.

Rerun the mechanical parts (schema, live Crossref, manifests, life tables, cause shares) with:

```
.venv/bin/python scripts/check_integrity.py --out /tmp/integrity.json
```

The builders' own `scripts/check_citations.py` also passes, online and `--offline`. Both runs exit 0.

## Verdict

Nothing blocks. No wrong numbers turned up: I re-read all 60 rows in their primary sources, including the 8 random ones. Every DOI resolves on Crossref, and every title and first author matches its row. All 171 manifest entries exist and match their sha256. The life tables reproduce NVSR 72-12. Cause shares are consistent: CVD ≥ CHD + stroke holds in every cell.

The problems are small: two wrong page locators, one misleading id, and one schema deviation. There are also seven places where the evidence contradicts or constrains DESIGN.md. Items 1 to 3 of those change results.

## 1. evidence.yaml: parse, ids, schema

- It is valid YAML: a list of 60 rows with 60 unique ids, all snake_case.
- Every row has all 18 top-level fields, all 12 `source` fields and all 5 `verified` fields. `kind`, `measure` and `value_checked_in` are all values the schema allows.
- No estimate falls outside its CI or PI. No row has only one CI bound, and no row has a CI with a null `ci_level`.
- No quoted passage is longer than 15 words. The longest is 10 words, in `aune2016_allcause_per28g.notes`.
- **Schema deviation:** six rows without a DOI add a `source.url` field that the schema does not have. They are `vidrih2012_ground_walnut_oxidation`, `fdc_brazil_nut_selenium`, `wweia_1720_nuts_seeds_adults`, `fped_nut_oz_eq_grams`, `wweia_1720_ala_adults` and `fda_aflatoxin_action_level`. Their three `verified.*_matches/doi_resolves` flags are `null`. The field is sensible, so either add an optional `source.url` to DESIGN.md or drop it. Every such URL returned HTTP 200 on 2026-09-23.

### Rows by id

In the "re-read" column, "sample" marks the 8 random rows (section 3) and "yes" marks rows I re-read on top of the sample. The last column names the source I read.

| id | kind | measure | estimate [CI] | re-read | read in |
|---|---|---|---|---|---|
| aune2016_allcause_per28g | cohort_meta_dose_response | RR | 0.78 [0.72, 0.84] | yes | abstract; Add. file 1 Table S17 |
| aune2016_allcause_per28g_excl_small_studies | cohort_meta_dose_response | RR | 0.80 [0.74, 0.87] | yes | Results, all-cause paragraph |
| aune2016_cvd_per28g | cohort_meta_dose_response | RR | 0.79 [0.70, 0.88] | yes | abstract |
| aune2016_cvd_per28g_mortality | cohort_meta_dose_response | RR | 0.76 [0.67, 0.86] | sample | Table S16 |
| aune2016_chd_per28g | cohort_meta_dose_response | RR | 0.71 [0.63, 0.80] | yes | abstract |
| aune2016_chd_per28g_mortality | cohort_meta_dose_response | RR | 0.69 [0.63, 0.75] | yes | Table S16 |
| aune2016_stroke_per28g | cohort_meta_dose_response | RR | 0.93 [0.83, 1.05] | yes | abstract |
| aune2016_stroke_per28g_mortality | cohort_meta_dose_response | RR | 0.95 [0.79, 1.15] | yes | Table S16 |
| aune2016_cancer_per28g | cohort_meta_dose_response | RR | 0.85 [0.76, 0.94] | yes | abstract |
| aune2016_cancer_per28g_mortality | cohort_meta_dose_response | RR | 0.83 [0.75, 0.92] | yes | Table S17 |
| delgobbo2015_ldl_per28g | rct_mediator | mean_difference | -4.8 [-5.5, -4.2] | yes | PMC full text, Table 2 |
| delgobbo2015_ldl_per28g_rct | rct_mediator | mean_difference | -4.2 [-5.0, -3.4] | yes | PMC full text, Table 2 |
| delgobbo2015_apob_per28g | rct_mediator | mean_difference | -3.7 [-5.2, -2.3] | yes | PMC full text |
| delgobbo2015_apob_per28g_rct | rct_mediator | mean_difference | -4.2 [-5.7, -2.6] | yes | PMC full text |
| ctt2010_chd_death_per_mmol | mediator_slope | RR | 0.80 [0.74, 0.87] (99% CI) | yes | full text; Figure 5 image |
| ctt2010_all_cause_per_mmol | mediator_slope | RR | 0.90 [0.87, 0.93] | yes | full text; Figure 5 |
| ctt2010_vascular_death_per_mmol | mediator_slope | RR | 0.86 [0.82, 0.90] | yes | Figure 5 image ("Any vascular") |
| ctt2010_major_vascular_events_per_mmol | mediator_slope | RR | 0.78 [0.76, 0.80] | yes | abstract |
| schwingshackl2021_rrr_overall | calibration_corpus | RRR | 1.09 [1.04, 1.14], PI 0.81–1.46 | yes | Table 1 |
| schwingshackl2021_rrr_overall_cohort_rr_below_1 | calibration_corpus | RRR | 1.12 [1.07, 1.17], PI 0.87–1.45 | yes | Results |
| schwingshackl2021_rrr_all_cause | calibration_corpus | RRR | 1.17 [1.11, 1.23], PI 0.99–1.39 | yes | Table 1 |
| schwingshackl2021_rrr_cvd | calibration_corpus | RRR | 1.05 [0.99, 1.12], PI 0.85–1.31 | yes | Table 1 |
| schwingshackl2021_rrr_intake_vs_intake | calibration_corpus | RRR | 0.98 [0.93, 1.04], PI 0.90–1.07 | yes | Table 1 |
| schwingshackl2021_rrr_supplement_vs_status | calibration_corpus | RRR | 1.29 [1.17, 1.42], PI 0.94–1.77 | yes | Table 1 |
| predimed2018_nuts_major_cvd | rct_hard_endpoint | HR | 0.72 [0.54, 0.95] | yes | PubMed abstract |
| predimed2018_evoo_major_cvd | rct_hard_endpoint | HR | 0.69 [0.53, 0.91] | yes | PubMed abstract |
| naghshi2021_ala_all_cause_per_g | cohort_meta_dose_response | RR | 0.95 [0.91, 0.99] | yes | full text |
| naghshi2021_ala_cvd_per_g | cohort_meta_dose_response | RR | 0.95 [0.91, 0.98] | yes | full text |
| abdelhamid2020_ala_all_cause | rct_hard_endpoint | RR | 1.01 [0.84, 1.20] | sample | abstract; SoF 2; Analysis 4.1 |
| eslamparast2017_golestan | cohort | HR | 0.71 [0.58, 0.86] | sample | PMC full text, Tables 2–3 |
| luu2015_scc_shanghai | cohort | HR | 0.79 [0.73, 0.86] | yes | PMC full text |
| luu2015_shanghai_peanut_q5 | cohort | HR | 0.83 [0.77, 0.88] | yes | PMC full text |
| vandenbrandt2015_nlcs | cohort | HR | 0.77 [0.66, 0.89] | yes | PubMed abstract |
| guaschferre2017_total_nuts_cvd | cohort | HR | 0.86 [0.79, 0.93] | yes | PMC full text |
| guaschferre2017_peanut_cvd | cohort | HR | 0.87 [0.82, 0.93] | yes | PMC full text |
| guaschferre2017_treenut_cvd | cohort | HR | 0.85 [0.79, 0.91] | sample | PMC full text, Table 3 |
| guaschferre2017_walnut_cvd | cohort | HR | 0.81 [0.71, 0.92] | yes | PMC full text, Table 3 |
| liu2021_walnut_mortality | cohort | HR | 0.86 [0.79, 0.93] | yes | abstract |
| wang2025_mr | mendelian_randomization | OR | 1.4866 [1.0491, 2.1065] | yes | PMC full text |
| guaschferre2018_walnut_ldl | rct_mediator | mean_difference | -5.51 [-7.72, -3.29] | yes | PMC full text |
| leebravatti2019_almond_ldl | rct_mediator | mean_difference | -5.83 [-9.91, -1.75] | yes | PMC full text |
| hadi2023_pistachio_ldl | rct_mediator | mean_difference | -3.82 [-5.49, -2.16] | yes | PubMed abstract |
| zhang2026_pecan_ldl | rct_mediator | mean_difference | -7.42 [-10.83, -4.01] | yes | PMC full text |
| perna2016_hazelnut_ldl | rct_mediator | mean_difference | -0.15 [-0.308, -0.003] mmol/L (95% HPD) | yes | PMC full text |
| griel2008_macadamia_ldl | trial_biomarker | mean_difference | null | yes | abstract (3.14 vs 3.44 mmol/L; null is justified) |
| jones2023_macadamia_ldl | trial_biomarker | mean_difference | -4.7 [-14.3, 4.8] | yes | PMC full text |
| jalali2020_cashew_ldl | rct_mediator | mean_difference | -0.93 [-4.83, 2.96] | yes | accepted manuscript |
| jafariazad2020_peanut_ldl | rct_mediator | mean_difference | -3.31 [null] | yes | abstract (no CI printed; P = 0.472) |
| nieman2012_chia_milled_vs_whole | trial_biomarker | value | 58 | yes | abstract |
| malcolmson2000_milled_flax_storage | lab_or_storage_study | value | 128 | sample | Crossref abstract (fetched live) |
| vidrih2012_ground_walnut_oxidation | lab_or_storage_study | value | null | yes | PDF Table 6 (C18:3 range 9.70–13.20%) |
| schlormann2015_roasting | lab_or_storage_study | value | 17 | yes | abstract (17-fold) |
| stranges2007_npc_diabetes | rct_hard_endpoint | HR | 1.55 [1.03, 2.33] | yes | abstract |
| efsa2023_selenium_ul | reference_value | value | 255 | yes | Crossref abstract |
| nasem2000_selenium_ul | reference_value | value | 400 | sample | NAP chapter 7 page |
| fdc_brazil_nut_selenium | reference_value | value | 1920 | yes | FDC JSON: 15 data points, range 136–2740 |
| wweia_1720_nuts_seeds_adults | reference_value | value | 0.84 | sample | FPED Table 1e PDF |
| fped_nut_oz_eq_grams | reference_value | value | 14.175 | yes | FPED 2017–18 methodology |
| wweia_1720_ala_adults | reference_value | value | 1.93 | sample | WWEIA Table 1 PDF |
| fda_aflatoxin_action_level | reference_value | value | 20 | yes | CPG 570.375, 570.500, 570.200, 555.400 |

## 2. DOIs on Crossref (live, 2026-09-23)

28 unique DOIs cover 54 rows. All returned HTTP 200. For every row, the Crossref title matches the row title exactly after normalizing case and punctuation (Jaccard 1.00), and the Crossref first author matches `source.first_author`. That includes the organizational authors CTT Collaboration, the EFSA NDA Panel and the NASEM Panel. PMID, PMCID and DOI agree with PubMed for all 25 distinct sources that carry a PMID. The cached records in `data/sources/crossref/` match the live ones. So there are **no title or first-author mismatches and no unresolvable DOIs.**

I also compared year, volume, issue and pages. Neither difference below is a row error:
- `eslamparast2017_golestan` (10.1093/ije/dyv365): Crossref has only the 2016 online date, and its page field is `dyv365`. PubMed confirms the row: 2017;46(1):75-85. A year check against Crossref will flag this row falsely.
- `luu2015_*` (10.1001/jamainternmed.2014.8347): Crossref deposits only the first page (755). The row's 755-766 matches PubMed (755-66).

Six rows have no DOI and are listed in section 1. I also checked the DOIs cited in `data/` that are not in evidence.yaml. All resolve and match: Fadnes 2022 (10.1371/journal.pmed.1003889), its correction (…1003962), NVSR 72-12 (10.15620/cdc:132418) and Sala-Vila 2016 JAHA (10.1161/JAHA.115.002543).

## 3. Eight random rows re-read in the primary source

I drew the sample with `random.Random(seed)`, where the seed is the first 16 hex digits of sha256 over the ids joined by newline, in file order. The ids were: `wweia_1720_ala_adults`, `nasem2000_selenium_ul`, `abdelhamid2020_ala_all_cause`, `eslamparast2017_golestan`, `guaschferre2017_treenut_cvd`, `wweia_1720_nuts_seeds_adults`, `aune2016_cvd_per28g_mortality` and `malcolmson2000_milled_flax_storage`.

**No estimate or CI disagrees.** The notes' secondary numbers also check out: the Golestan category and sex HRs, CVD 0.77 (0.58–1.01), and mean intake of 3.5 and 2.6 g/day; the WWEIA sex splits and age-band extremes; the Aune incidence subgroup 0.83 (0.64–1.08) with P between subgroups 0.48; the Abdelhamid low-risk-of-bias estimate 1.02 (0.72–1.45); and the NASEM NOAEL of 800, UF of 2 and RDA of 55.

Locator and cosmetic problems I found in the sample:
- `wweia_1720_ala_adults.locator` says "page 6 of 9". The PFA 18:3 column is on **page 7 of 9** of `Table_1_NIN_GEN_1720.pdf`.
- `wweia_1720_nuts_seeds_adults.locator` says "p. 5". The Nuts and Seeds column is on **page 6 of 8** of `Table_1_FPED_GEN_1720.pdf`.
- `malcolmson2000_milled_flax_storage.notes` leaves out that total volatiles rose during storage in the mixed-variety sample, as the abstract reports. Only a completeness issue.
- The cached NAP page is named `nap_9810_chapter9_selenium.html`, but it holds Chapter 7. The locator correctly says Chapter 7.

I re-read the other 52 rows as well (table above), and all agree. Two things to note from them:
- `luu2015_scc_shanghai` is the US Southern Community Cohort Study only. Shanghai is the other row, so an id such as `luu2015_sccs` would not mislead.
- `data/curves/aune2016_nonlinear.csv` matches Additional file 1 Tables S14 and S15 cell for cell: 75 of 75 non-reference cells, parsed independently from the PDF. `ihme_bop_nuts_seeds_ihd.csv` matches the raw API JSON on all 100 grid points. `composition.csv` matches the raw FDC JSON for all 12 foods and 10 nutrients.

## 4. Manifests

| manifest | entries | exist and sha256 matches |
|---|---|---|
| causes/MANIFEST.json | 6 | 6 |
| composition/MANIFEST.json | 16 | 16 |
| curves/MANIFEST.json | 35 | 35 |
| life_tables/MANIFEST.json | 7 | 7 |
| prices/MANIFEST.json | 22 | 22 |
| sources/crossref/MANIFEST.json | 69 | 69 |
| sources/crossref/texts/MANIFEST.json | 16 | 16 |

Every file under `data/` is listed by some manifest. The only exceptions are `evidence.yaml`, this file and `.gitignore`. Every raw download has a `url` and a `fetched_at`, with these exceptions in prices:
- `prices` `unused_files/raw/walmart/walmart_search_raw_almonds_curl.html.gz` has neither. It is marked unused.
- The Costco and Walmart browser captures use URL templates, with the per-product URLs inside the capture.
- The Target `fetched_at` is marked "approximate".

## 5. Life tables and cause shares

**Life tables.** `male.csv`, `female.csv` and `total.csv` equal the NVSR 72-12 xlsx cells exactly (max |Δq| = 0 and max |Δe| = 0 over ages 0–100). e0 in the csvs is 73.5499 (male), 79.3281 (female) and 76.3702 (total). These round to the published 73.5, 79.3 and 76.4, and e20, e40, e60 and e80 round to the printed table values. Recomputing e_x from the csv q_x with the mid-year convention reproduces the tables within 0.0022 years at every age, **provided the open interval uses the table's own e100.** Male e100 is 1.9495 and female e100 is 2.2149. See DESIGN item 4 for the case where it does not.

**Cause shares** (NCHS 2021 multiple-cause microdata):
- Both csvs are consistent in every row. CVD ≥ CHD + stroke holds everywhere; the smallest margins are 4 deaths (female, age not stated) and 58 deaths (male 1–4).
- CVD + cancer ≤ all deaths; each share equals deaths ÷ all deaths; male + female = total.
- The all-ages totals match NVSR 73-08: 3,464,231 deaths, 605,213 C00–C97, 162,890 I60–I69 and 375,476 I20–I25. IHD by age group matches the NVSR row exactly.
- CVD here is I00–I99 (931,578 deaths), as DESIGN specifies. NVSR's "major cardiovascular diseases" is I00–I78 (925,923).

## Where the evidence contradicts or constrains DESIGN.md

1. **The Aune curve is not monotone, so "interpolated monotonically ... flat beyond the highest observed intake" is ambiguous and decides Q2.**
   - The all-cause RR in Table S15 is 0.89, 0.84, 0.82, 0.82, 0.84 and 0.85 at 5, 10, 15, 20, 25 and 28 g/day. CVD mortality in S14 bottoms out at 0.80 at 15 g and returns to 0.85 at 28 g.
   - A shape-preserving interpolant of these points gives f(B+Δ) − f(B) > 0, a modeled harm, for B = 20 at every Δ. For B = 28 it gives exactly 0.
   - DESIGN must say whether to enforce a nonincreasing curve (a running minimum, flat at 0.82 from about 15–20 g) or use the points as printed. Otherwise the B ∈ {20, 28} outputs are an artifact of the interpolant.
   - A residual labeling caveat remains. The S14 and S15 titles say "peanuts", while the main text cites both tables for total nuts. The builder's reading, that these are total nuts, is supported. Two P-nonlinearity values in the tables still differ from the main text: total cancer is 0.003 against 0.11, and CVD is <0.0001 against 0.001.
2. **The calibrated multiplier sits above face value in the "matching stratum."** The intake-v-intake RRR is 0.98 (0.93–1.04), with PI 0.90–1.07. So c_cal = ln(0.78 × 0.98) / ln(0.78) = **1.08**, and the calibrated member exceeds c = 1. The other strata give smaller values: all-cause 1.17 → c_cal 0.37; overall 1.09 → 0.65; cohort RR < 1 subset 1.12 → 0.54; CVD 1.05 → 0.80. None of the 23 intake-v-intake pairs is a nut. The all-cause stratum is mostly supplement trials, per the row notes. The bracket needs an explicit rule for c_cal > 1, and for PI draws on both sides of 1.
3. **The class effect for peanuts is not what Del Gobbo 2015 shows.**
   - Del Gobbo excluded legumes, peanuts included, and pooled tree nuts only. Their "no heterogeneity by nut type" finding covers tree nuts.
   - The only peanut LDL meta-analysis in the data (`jafariazad2020_peanut_ldl`) gives -3.31 mg/dL, P = 0.472, not significant.
   - Del Gobbo also found the LDL dose-response nonlinear (P < 0.001, with larger effects at 60 g/day or more). DESIGN uses it as linear per 28.4 g.
   - The per-type P values are in Supplemental Table 2, which was not retrievable.
4. **"q = 1 at 100" with the mid-year convention fails DESIGN's own 0.05-year test.** If the open interval gets half a year, female e80 is 9.3128 against the table's 9.3741, a gap of 0.061. Total e80 is off by 0.045 and female e0 by 0.035. Using the table's T100 = l100 × e100 passes at every age, within 0.0022. Under treatment, the open interval then needs its own hazard adjustment, for example e100 ÷ M.
5. **The CTT CHD-death slope has a 99% CI.** The paper gives 95% CIs only for summary rate ratios. The row correctly stores `ci_level: 0.99`. The "lognormal from its CI" draw must use z = 2.576 for `ctt2010_chd_death_per_mmol` and 1.96 for the others. The randomized floor also needs the mg/dL → mmol/L LDL factor, and no evidence row holds it.
6. **Fadnes reproduction inputs.** Fadnes used GBD 2019 US mortality: their typical-diet e20 for US men is 57.8, against 54.4 in NVSR 2021. `data/` holds no GBD 2019 mortality, so "with their US inputs" can only be met for the HR (0.84 at 25 g, which equals Aune S15 at 25 g) and the phase-in, not the baseline.
   - As a scratch check, I ran HR 0.84 on the NVSR 2021 tables with a 10-year linear phase-in from age 20. This is not the model. It gives ΔLE ≈ 2.10 years for men against Fadnes's 2.0 (+5%), and 1.87 for women against 1.7 (+10%). The 15% test looks passable despite the different baseline.
7. **ALA sensitivity range.**
   - Naghshi's included intakes run from 0.35 to 3.0 g/day, not from 0.
   - Mean adult 18:3 intake (all isomers) is already 1.93 g/day (WWEIA 2017–March 2020).
   - A 28 g walnut serving adds about 2.54 g (FDC 9.08 g/100 g, 18:3 undifferentiated).
   - So at mean background, only about 1.07 g of a walnut serving's ALA falls inside the observed range.

Not contradictions, but worth a decision:
- The 2021 baseline is a COVID year: U07.1 is 12.0% of all 2021 deaths, and NVSR 72-12 reports 2021 e0 as the lowest since 1996. COVID deaths inflate the denominator of the cause shares.
- `references.bib` is generated from evidence.yaml, and `paper/extra.bib` is empty. Fadnes 2022, NVSR 72-12, NVSR 73-08, IHME Burden of Proof, Johansson 2020 and USDA FDC are used in `data/` but have no evidence row. They will get no bib entries, and `check_citations.py` will not check them.
- `data/causes/raw/mort2021us.zip` (164.6 MB) is gitignored, because it is too large for GitHub. `fetch_causes.py` re-downloads it. In a clean clone that file is absent, so any `data.py` step that checks every manifest entry's sha256 on load must skip raw files that can be re-fetched, or fetch them first. This bears on DESIGN's reproduction check (3), the byte-identical rebuild from a clean clone.

## Not verified

- Del Gobbo Supplemental Tables 2–3 (per-nut-type P values): they are not open access, and ScienceDirect returned 403.
- Full texts of Griel 2008, Jafari Azad 2020 and Hadi 2023 (publisher 403). Their rows rely on abstracts, and the notes say so.
- Whether S14 and S15 are total nuts rather than peanuts. The main text supports total nuts, but only the figures, which are images, would settle it.
- Prices: I checked only the manifest hashes. I did not re-read prices against the stores.
