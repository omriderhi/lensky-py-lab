# Brief for the agent rewriting the paper: satellite data decisions (PR #12)

Read this before touching Section 2.4.1, Table 3, Table 4, Sections 3.1-3.2 or the Fig S4-S6 captions.
It records what was decided about MODIS / Sentinel-2 / Landsat-8, why, and which statements in the manuscript no longer match the code.
Detail and evidence: `docs/features/satellite-data-cleaning-audit-report.md`. The `.docx` was **not** opened or edited by the people/agents who wrote this; compare against it yourself.

## 1. Decisions (final for the paper)

1. **Outlier filter, NSRS and MODIS: unchanged.** Observation window 7, removal threshold `max(3 x 1.4826 x MAD, 0.02)`, MAD over 31 observations. It is a median/MAD test, applied after the extreme-value filter and before LOWESS.
2. **Outlier filter, S2: same filter with a raised floor of 0.08 NDVI** (instead of 0.02). Reason: 0.02 was tuned for daily ground sensors; on a sparse series 7 observations span about 5 weeks and the filter removed real high-season values.
3. **L8 is excluded from the analysis** (no phenology, no Table 3 / Table 4 rows, no comparative or decomposition figures). It is excluded by a stated rule, not by hand (section 3). L8 **stays in the data-availability figure**, labelled "(excluded)". Its data-cleaning figure is still produced.
4. **L8 same-date rows are averaged** (one overpass exported as two adjacent-row scenes). This is a data fix and matters only if L8 is shown (availability / cleaning figure).
5. **After the research is handed over, the repo's satellite default should become the downward-only, calendar-window filter** (`outlier_window_days=15, outlier_direction="down"`, implemented, tested, unused by the research config). It is **not** what the paper's results used. Do not describe it as the method of the paper.

## 2. What the manuscript must say (replace the current Section 2.4.1 wording)

- NSRS and MODIS: values outside [min, max] are discarded (NSRS >= 0.2; MODIS <= 0.8); each observation is removed if it differs from the median of its 7 neighbouring observations by more than max(3 x 1.4826 x MAD, 0.02) with MAD over a 31-observation window; the series is then smoothed with LOWESS.
- S2: values below 0.4 are discarded; the same test with a floor of 0.08. Say that the floor was chosen from a sensitivity analysis on this site's data.
- State that the window counts **observations**, not days (about one week for daily MODIS, about five weeks for S2).
- If the paper mentions L8, say it was acquired and processed, had 51 distinct valid dates, and was excluded under the rules in section 3.
- Do **not** claim that "cloud-contaminated values were removed" without qualification. MODIS gets no pixel-level cloud mask in the Earth Engine script (only the NDVI >= 0.35 mask), so MODIS cloud dips are handled only by the filter above and by LOWESS. S2 and L8 only have a scene-level cloud filter (< 10 %).
- Do not cite the downward-only approach as the paper's method (decision 5). If it appears at all, it belongs in a "future work / released package" sentence.

## 3. Eligibility rules (state them in Methods, with the numbers)

A satellite takes part only if both hold over the NSRS observation window (2019-10-06 to 2021-11-03), judged after the extreme-value filter and before the outlier filter (so the verdict does not depend on filter settings or on any result):
- at least **40** distinct valid observation dates in the window;
- valid data in at least **60 %** of the calendar months in the window.

| Source | valid dates in window | month coverage | verdict |
|---|---|---|---|
| MODIS | 523 | 1.00 | in |
| S2 | 64 | 0.89 | in |
| L8 | 32 | 0.58 | out (fails both) |

Be candid in the text: the thresholds are judgment calls fixed after the RH data had been seen, and L8 fails by small margins (S2 passes comfortably since its series was extended to Nov 2021, see `s2-extension.md`). Do not present them as standard thresholds from the literature (no citation exists for them). Reviewers may ask; the honest answer is in `pipeline/eligibility.py` and the README.

## 4. Why these decisions (short evidence)

- The pre-v12 filter (`average_window`, kept only values far from the global mean) removed 78 % of MODIS, 74 % of L8, 44 % of S2 observations and inflated MODIS peaks by 0.03-0.11 NDVI. Any pre-v12 satellite number is wrong. It must not appear anywhere.
- The current filter is harmless for MODIS (4.7 % removed; peaks identical to "no outlier filter" within 0.004).
- On sparse series it removes real peaks: L8's three highest values and, with the 0.02 floor, S2 values in the high-NDVI season. The S2 floor of 0.08 fixes S2 (PoS values match the no-filter series). Re-verified on the single-product series: floors 0.08-0.15 are identical, and at 0.08 the filter removes 1 of 91 observations (see `s2-extension.md`).
- L8: the research CSV lists 22 dates twice. Earth Engine (`LANDSAT/LC08/C02/T1_L2`) shows the point lies in the overlap of rows 37 and 38 of path 174; both scenes come from one overpass seconds apart. After averaging, L8 has 51 valid dates (not 73 rows), and no filter setting tried protects its peaks while an observation window is used. Its Table 4 correlations ranged from 0.17 to 0.98 across window / k settings, on 10-17 paired dates. That is why it is excluded rather than tuned.
- The original `LANDSAT/LC08/C01/T1_SR` collection used by the research JS no longer exists in Earth Engine, so the L8 series cannot be regenerated or compared value by value (S2 `COPERNICUS/S2_SR` still works but is deprecated, and no longer matches the harmonised collection; the S2 series was therefore regenerated as one product, see `s2-extension.md`).

## 5. Numbers as of this PR (regenerate before quoting)

Run: `python scripts/run_rh_ndvi.py --data-dir data/research_results/RH_NDVI --ims-dir data/research_results/IMS --out-dir data/results_<name>` (outputs are gitignored; this snapshot is from the single-product S2 run, `data/results/s2_single_product_run`; the MODIS and NSRS rows are unchanged from `data/results_eligibility_2026-10-17`). NSRS_3 factor derived from the data: 1.384 (RMSE 0.159 -> 0.0405, R2 0.899, n = 470); the manuscript's 1.36 predates the cleaning fix and the 1.4 is only a comparison value.

Table 4 (Full signal vs NSRS_3, Woody vs NSRS_2, Herbaceous vs NSRS_1):

| Satellite | Component | n | MAE | RMSE | r | bias |
|---|---|---|---|---|---|---|
| MODIS | Full signal | 371 | 0.042 | 0.052 | 0.974 | -0.018 |
| MODIS | Woody | 357 | 0.123 | 0.140 | 0.045 | -0.120 |
| MODIS | Herbaceous | 342 | 0.449 | 0.459 | 0.863 | -0.449 |
| S2 | Full signal | 46 | 0.039 | 0.048 | 0.956 | 0.027 |
| S2 | Woody | 46 | 0.138 | 0.156 | -0.219 | -0.138 |
| S2 | Herbaceous | 44 | 0.385 | 0.390 | 0.917 | -0.385 |

The woody and herbaceous rows compare a satellite-derived component with a differently defined NSRS layer (bias is about minus the MAE; see the header of `phenology/decomposition_validation.py`). Do not read them as accuracy of the decomposition. The S2 rows rest on 44-46 dates (S2 series extended to Nov 2021 and regenerated as one product), so differences of about 0.01 are not meaningful.

Phenology (hydrological year Y = Sep Y-1 to Aug Y), MODIS and S2 (the CSV dates carry a 21:00/22:00 time of day from time-zone conversion, so a date here may be one day off from the local calendar date; recheck before quoting exact days):

| Source | Year | SoS | PoS | EoS | PoS value | note |
|---|---|---|---|---|---|---|
| MODIS | 2018 | 2018-01-05 | 2018-02-27 | 2018-04-16 | 0.599 | record starts Jan 2018: SoS is an edge effect |
| MODIS | 2019 | 2018-11-01 | 2019-01-13 | 2019-06-29 | 0.632 | |
| MODIS | 2020 | 2019-10-30 | 2020-03-01 | 2020-07-01 | 0.634 | |
| MODIS | 2021 | 2020-11-05 | 2021-02-20 | 2021-06-01 | 0.655 | |
| MODIS | 2022 | 2021-11-08 | 2022-02-06 | 2022-07-26 | 0.601 | |
| S2 | 2019 | 2018-12-31 | 2018-12-31 | 2019-05-09 | 0.744 | **record starts 2018-12-31: SoS and PoS are edge artefacts, do not interpret** |
| S2 | 2020 | 2019-11-30 | 2020-03-04 | 2020-05-29 | 0.702 | SoS moved 25 days between S2 product versions (2019-11-05 before): treat S2 SoS as imprecise |
| S2 | 2021 | 2020-10-30 | 2021-02-10 | 2021-05-06 | 0.810 | EoS now found because the S2 record runs to 2021-11-16 (it was censored when S2 ended 2021-04-30) |

`extract_phenology` reports EoS only if the curve falls below the threshold before the record ends; otherwise `EoS_censored` is True and EoS is blank. Do not fill it with the last day of data.

## 6. Manuscript cells and sentences that change (check each against the `.docx`)

- **Section 2.4.1:** per section 2.
- **Table 3 satellite rows:** MODIS and S2 per section 5; L8 rows removed. MODIS PoS values are 0.03-0.11 lower than any pre-v12 values.
- **Table 4:** MODIS and S2 rows per section 5; L8 rows removed (the L8 decomposition has no support).
- **Sections 3.1-3.2:** any quoted satellite peak / EoS date, and any statement that L8 agrees (or not) with NSRS.
- **Fig S4-S6 captions and figures:** regenerate all from the run above. The MODIS "bimodal winter / summer clusters" in the S4 caption may come from the pre-v12 rule (kept-value SD 0.153 vs raw 0.093); re-check against the new figure, do not assume.
- **Data availability figure:** now shows L8 as "(excluded)". Mention it in the caption.
- **Methods / data section:** add the eligibility rules (section 3) and the L8 duplicate-scene note if L8 is mentioned.

## 7. Known limitations to carry into the text (or at least not contradict)

- The S2 floor (0.08) and the eligibility thresholds are tuned to this one site's data.
- Records start mid-season (MODIS Jan 2018, S2 2018-12-31), so the first hydrological year's SoS (and for S2, PoS) is partly an edge effect.
- Sensitivity: MODIS results are stable across window 5-15 and k 2.5-4; S2 and L8 are not, which is part of why an observation-count filter is a weak design for sparse series.
- The literature for "clouds lower NDVI, so low values are the suspect ones" (Holben 1986; Viovy et al. 1992 BISE; Chen et al. 2004; TIMESAT) was read only at abstract or secondary level. Read the full texts before citing; the specific median/MAD rule used here is this project's design, not a published method.
- The `.docx` manuscript, Fig S4-S6 and the original GEE script outputs could not be compared directly.
