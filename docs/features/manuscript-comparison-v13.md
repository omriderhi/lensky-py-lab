# Manuscript v13 vs the current outputs (satellite parts)

Compared `archive/Derhi_WoodyHerbaceous_v13_TRACKED_Claude.docx` (text and tables read from the document XML; the file was **not** edited)
with the outputs of `python scripts/run_rh_ndvi.py` on the current data (2026-10-17, `data/results/`). Earlier comparison of v12:
`manuscript-comparison.md`. Companion: `satellite-data-products.md` (products, numbers, statements to update).

## Where the differences come from

1. **Changes before this branch** (the outlier-filter replacement of PR #11, S2 floor and eligibility of PR #12). MODIS and NSRS outputs are
   identical before and after the S2 / L8 work on this branch (phenology and calibration compared), so every MODIS and NSRS difference below comes
   from those earlier changes, not from the S2 regeneration or the L8 re-extraction.
2. **This branch:** S2 regenerated as one product and extended to 2021-11-16; L8 re-extracted (Collection 2) and excluded.
3. **Text that never matched the code** (section 3 below).

Figures were not diffed; only tables and text.

## 1. Table 3 (phenology), manuscript vs current

Dates are the date part of the stored timestamp, which is what the manuscript's DOY follows (may be one day off the local date).

| Source | Year | Manuscript SoS | Current SoS | Manuscript PoS | Current PoS | Manuscript EoS | Current EoS | Peak ms -> now |
|---|---|---|---|---|---|---|---|---|
| MODIS | 2019 | 11 Oct 2018 (284) | 01 Nov 2018 (305) | 12 Feb 2019 (43) | 13 Jan 2019 (13) | 08 Jun 2019 (159) | 29 Jun 2019 (180) | 0.69 -> 0.63 |
| MODIS | 2020 | 07 Oct 2019 (280) | 30 Oct 2019 (303) | 09 Feb 2020 (40) | 01 Mar 2020 (61) | 28 Jun 2020 (180) | 01 Jul 2020 (183) | 0.68 -> 0.63 |
| MODIS | 2021 | 25 Oct 2020 (299) | 05 Nov 2020 (310) | 11 Feb 2021 (42) | 20 Feb 2021 (51) | 07 Jun 2021 (158) | 01 Jun 2021 (152) | 0.68 -> 0.65 |
| S2 | 2020 | 19 Oct 2019 (292) | 30 Nov 2019 (334) | 17 Jan 2020 (17) | 04 Mar 2020 (64) | 31 May 2020 (152) | 29 May 2020 (150) | 0.71 -> 0.70 |
| S2 | 2021 | 21 Oct 2020 (295) | 30 Oct 2020 (304) | 11 Feb 2021 (42) | 10 Feb 2021 (41) | 11 Apr 2021 (101) | 06 May 2021 (126) | 0.80 -> 0.81 |
| NSRS_1 | 2020 | 01 Jan 2020 (1) | 28 Dec 2019 (362) | 29 Feb 2020 (60) | 29 Feb 2020 (60) | 10 Apr 2020 (101) | censored | 0.78 -> 0.78 |
| NSRS_1 | 2021 | 25 Nov 2020 (330) | 28 Nov 2020 (333) | 15 Feb 2021 (46) | 15 Feb 2021 (46) | 04 Apr 2021 (94) | 19 Jul 2021 (200) | 0.81 -> 0.81 |
| NSRS_3 | 2020 | 10 Jan 2020 (10) | 06 Jan 2020 (6) | 04 Mar 2020 (64) | 04 Mar 2020 (64) | 15 Apr 2020 (106) | censored | 0.74 -> 0.76 |
| NSRS_3 | 2021 | 13 Nov 2020 (318) | 10 Nov 2020 (315) | 17 Feb 2021 (48) | 16 Feb 2021 (47) | 02 Jun 2021 (153) | 30 Jun 2021 (181) | 0.72 -> 0.73 |

Rows the current run produces but the manuscript table does not have:

| Source | Year | | Current SoS | | Current PoS | | Current EoS | Peak now |
|---|---|---|---|---|---|---|---|---|
| NSRS_1 | 2022 | | 02 Sep 2021 (245) | | 02 Sep 2021 (245) | | 11 Sep 2021 (254) | -> 0.43 |
| NSRS_2 | 2020 | | 04 Jan 2020 (4) | | 18 Apr 2020 (109) | | censored | -> 0.69 |
| NSRS_2 | 2021 | | 11 Nov 2020 (316) | | 04 Mar 2021 (63) | | 24 Jul 2021 (205) | -> 0.65 |
| NSRS_2 | 2022 | | 02 Sep 2021 (245) | | 02 Sep 2021 (245) | | 04 Oct 2021 (277) | -> 0.46 |
| NSRS_3 | 2022 | | 02 Sep 2021 (245) | | 06 Sep 2021 (249) | | 19 Sep 2021 (262) | -> 0.40 |
| MODIS | 2018 | | 05 Jan 2018 (5) | | 27 Feb 2018 (58) | | 16 Apr 2018 (106) | -> 0.60 |
| MODIS | 2022 | | 08 Nov 2021 (312) | | 06 Feb 2022 (37) | | 26 Jul 2022 (207) | -> 0.60 |
| S2 | 2019 | | 31 Dec 2018 (365) | | 31 Dec 2018 (365) | | 09 May 2019 (129) | -> 0.74 |

- The manuscript omits MODIS 2018 and 2022, S2 2019 and NSRS 2022 seasons and NSRS_2 (degenerate or edge seasons; see `v12-review-fixes.md`).
- NSRS_1 / NSRS_3 2020 EoS is now censored (the NSRS record ends 2020-04-25), and NSRS 2021 EoS moved from April to June-July (DOY 94 -> 200, 153 -> 181):
  the manuscript's EoS DOY 94-153 for NSRS no longer holds.
- S2 2021 EoS: 11 Apr (DOY 101) -> 06 May (DOY 126); S2 2020 SoS 19 Oct -> 30 Nov (DOY 292 -> 334; imprecise, see `s2-extension.md`).
- No L8 rows in the manuscript table: consistent with L8 being excluded.

## 2. Table 4 (agreement with NSRS), manuscript vs current

| Source | Component | n ms -> now | MAE | RMSE | r | Bias |
|---|---|---|---|---|---|---|
| MODIS | Full signal (NSRS_3) | 86 -> 371 | 0.026 -> 0.042 | 0.033 -> 0.052 | 0.98 -> 0.97 | -0.008 -> -0.018 |
| MODIS | Woody (NSRS_2) | 67 -> 357 | 0.192 -> 0.123 | 0.212 -> 0.140 | 0.05 -> 0.04 | -0.192 -> -0.120 |
| MODIS | Herbaceous (NSRS_1) | 86 -> 342 | 0.426 -> 0.449 | 0.434 -> 0.459 | 0.93 -> 0.86 | -0.426 -> -0.449 |
| S2 | Full signal (NSRS_3) | 16 -> 46 | 0.065 -> 0.039 | 0.075 -> 0.048 | 0.91 -> 0.96 | 0.059 -> +0.027 |
| S2 | Woody (NSRS_2) | 11 -> 46 | 0.184 -> 0.138 | 0.196 -> 0.156 | -0.48 -> -0.22 | -0.184 -> -0.138 |
| S2 | Herbaceous (NSRS_1) | 18 -> 44 | 0.413 -> 0.385 | 0.417 -> 0.390 | 0.93 -> 0.92 | -0.413 -> -0.385 |

n grows several-fold because the old rule discarded most observations (it kept 22 % of MODIS). The manuscript's MAE / RMSE / r for the full signal
and for the herbaceous layer move, and the woody bias shrinks (MODIS -0.192 -> -0.120).

## 3. Statements in the text that no longer hold (or never did)

| Where | Manuscript says | Current facts |
|---|---|---|
| 2.3, S2 | "Cloud masking used the QA60 bitmask band" | **Never true for these data.** The research script and the client use only the scene-level filter `CLOUD_COVERAGE_ASSESSMENT < 10` and an NDVI >= 0.35 mask; no QA60 mask. Collection: `COPERNICUS/S2_SR_HARMONIZED` |
| 2.3, L8 | "LaSRC with CFMask cloud/shadow masking" | The original export used only `CLOUD_COVER < 10` (research script, C01). The current C02 extraction applies the `QA_PIXEL` cloud and shadow bits (matches the text) plus `CLOUD_COVER < 10` and NDVI >= 0.35. L8 is excluded from the analysis |
| 2.3, MODIS | "MOD09GQ V006" | Correct: the collection `MODIS/006/MOD09GQ` reproduces the data exactly (not Collection 6.1). The NDVI >= 0.35 mask and the absence of a pixel-level cloud mask are not stated |
| Data statement (end) | "MODIS data: NASA EOSDIS LP DAAC" | The MODIS series was extracted through Google Earth Engine (`MODIS/006/MOD09GQ`), not downloaded from the DAAC. Add collection IDs, date accessed (2026-10-17) and the repository CSVs / `gee_extraction_log.json` |
| 3.1, agreement | MODIS r = 0.92 / 0.93 / 0.98, RMSE 0.089 / 0.050 / 0.033 (n = 67-86); S2 r = 0.93, RMSE 0.064 (n = 18) vs NSRS_1, r = 0.58 (n = 11) vs NSRS_2; L8 n = 4-5 | Current, pairing = satellite observation dates with an NSRS value: MODIS vs NSRS_1 / 2 / 3: r = 0.87 / 0.71 / 0.97, RMSE 0.096 / 0.082 / 0.052 (n = 342 / 357 / 371). S2: r = 0.88 / 0.62 / 0.96, RMSE 0.094 / 0.108 / 0.048 (n = 44 / 46 / 46). The pairing of the manuscript's numbers is not documented, so the comparison is indicative |
| 3.1, timing | PoS DOY 40-64 (MODIS), 17-42 (S2); EoS DOY 152-199 (MODIS), 101-152 (S2); NSRS PoS 46-64, EoS 94-153 | MODIS 2019-21: PoS DOY 13-61, EoS 152-183 (all years 2018-22: PoS 13-61, EoS 106-207). S2 2020-21: PoS 41-64, EoS 126-150. NSRS PoS 46-64 (unchanged), NSRS EoS 181-200 (2021 only; 2020 censored) |
| 3.2, woody baseline | MODIS 0.39 / 0.38 / 0.38 (slight decline), "near 0.40" MODIS, 0.44 S2 | MODIS woody baseline is flat at 0.451-0.454 (slight increase); S2 declines 0.474 -> 0.450 -> 0.427 (mean 0.452). The "gradual decline in perennial canopy density" reading holds for S2 only, and MODIS is no longer lower than S2 |
| 3.2, woody vs NSRS_2 | biased low by about 0.19; r = 0.05 (MODIS), r = -0.48 (S2, 11 dates) | bias -0.120 (MODIS) and -0.138 (S2); r = 0.04 and -0.22 (n = 357, 46) |
| 3.2, herbaceous | r = 0.93 for both; MAE about 0.42; peaks 0.28-0.37 (MODIS 0.28, S2 0.37) | r = 0.86 (MODIS), 0.92 (S2); MAE 0.449, 0.385; herbaceous peaks in the NSRS window: MODIS 0.18 (2020), 0.20 (2021); S2 0.26, 0.39 |
| 3.2, full signal | MODIS r 0.98, MAE 0.026 (n = 86); S2 r 0.91, MAE 0.065 (n = 16) | MODIS r 0.97, MAE 0.042 (n = 371); S2 r 0.96, MAE 0.039 (n = 46). S2 now agrees with NSRS_3 better than before, and on MAE better than MODIS |
| 3.2, sample sizes | "n = 67-86", "eleven to eighteen overlapping dates" for S2 | n = 342-371 (MODIS), 44-46 (S2) |
| Cleaning text (Fig S1-S6) | "MODIS required the most aggressive outlier removal"; S2 retains ~5-8 and L8 ~3-5 clean acquisitions per season | Outlier removal after the extreme-value filter: MODIS 52 of 1,108 (4.7 %), S2 1 of 91 (1.1 %), L8 4 of 63 (6.3 %). By count MODIS removes the most; by share L8 does, and S2 is effectively unfiltered. Clean S2 acquisitions per full hydrological year: 32 (2020), 35 (2021) (about 8 per quarter); L8: 19, 21 (about 5 per quarter). "Per season" must say what a season is |
| Fig 7 caption | MODIS, L8, S2 tick marks "after cloud filtering"; 2018-2022 | L8 is labelled "(excluded)" in the figure; the caption must say so |
| Fig 9-11 | Fig 11 compares L8 with NSRS | the comparative figure for L8 is no longer produced (L8 excluded); the Fig 10 (S2) note "angular S2 curve in 2020 reflecting scarce cloud-free acquisitions" must be checked against the regenerated figure |
| Fig S5 / S6 captions | "February 2019 - May 2021" | cleaned S2 series now run 2019-01 to 2021-11 (last clean S2 2021-11-10); L8 2019-01 to 2021-11 (last 2021-11-05) |
| Conclusion 1, 3 | MODIS SoS DOY 280-299, PoS 40-58, EoS 152-180 | MODIS 2019-21: SoS DOY 303-310 (2019: 305), PoS 13-61, EoS 152-183 |
| Table 2 / calibration (2.2.2, Fig 5, conclusion 2) | x1.36; R2 0.957, RMSE 0.030, n = 296 | data-derived factor 1.384; R2 0.899, RMSE 0.0405, n = 470 (manuscript value predates the cleaning fix; known, see `v12-review-fixes.md`) |

## 4. Not checked

- Figures (only CSV outputs, tables and text); the discussion section and Sections 3.3+ beyond the sentences above.
- How the manuscript's per-sensor agreement numbers (Section 3.1) were paired; the current numbers use satellite observation dates.
- The reference list and citations.
