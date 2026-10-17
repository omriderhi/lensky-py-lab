# Report: satellite data cleaning audit (MODIS, S2, L8)

Spec: `docs/features/satellite-data-cleaning-audit.md`. Code: `scripts/audit/satellite_cleaning_audit.py`
(run it to regenerate everything). Outputs: `data/results_satellite_audit/` (gitignored):
`q1_removal_stats.csv`, `phenology_by_variant.csv`, `table4_by_variant.csv`,
`direct_nsrs_agreement.csv`, `figures/<source>_cleaning_variants.png`.
Inputs `data/research_results/RH_NDVI/*.csv` were not modified. NSRS_3 factor was derived
from the data in the same run (1.384), not hardcoded; NSRS processing is unchanged.

## Summary

1. **The old rule was badly biased.** It discarded 78 % of MODIS, 74 % of L8 and 44 % of S2 observations, and kept
   the tails (kept-value SD 0.153 vs raw 0.093 for MODIS). Its phenology is not usable as a baseline.
2. **The current filter (window 7, k 3) is wrong for the sparse sources.** On L8 it removes the three highest
   observations of the record, i.e. the real peaks (0.724 on 2019-01-09, 0.734 on 2020-03-07, 0.776 on 2021-02-15),
   and on S2 it removes the first observation (0.744, 2018-12-31) and 0.687 (2021-01-09). L8 PoS value falls from 0.734 to 0.599 in 2020.
   For MODIS (dense) it is nearly harmless (4.7 % removed).
3. **Outlier filtering barely matters for MODIS**: skipping it, a ±15-day window, and a one-sided variant give the same phenology and the same Table-4 metrics to the third decimal.
4. **Recommendation:** for satellites use a **calendar window (±15 d) that removes only downward outliers**
   (`outlier_window_days=15, outlier_direction="down"`). It removes 0.5 % / 4.3 % / 6.8 % (MODIS / S2 / L8), every removed point is below its local median, no peak is touched.
   The option is implemented but the **defaults in `scripts/run_rh_ndvi.py` are not changed** (author's call; this changes the satellite columns of Table 3 / Table 4).

## Q1. Was the old output biased?

Removed counts (after the extreme-value filter), `q1_removal_stats.csv`:

| Source | n in | old rule removed | A: window 7 / k 3 | B: ±15 d both | C: ±15 d down | E: SG envelope |
|---|---|---|---|---|---|---|
| MODIS | 1108 | **863 (77.9 %)** | 52 (4.7 %) | 8 (0.7 %) | 5 (0.5 %) | 527 (47.6 %) |
| S2 | 69 | 30 (43.5 %) | 12 (17.4 %) | 9 (13.0 %) | 3 (4.3 %) | 9 (13.0 %) |
| L8 | 73 | 54 (74.0 %) | 15 (20.5 %) | 9 (12.3 %) | 5 (6.8 %) | 3 (4.1 %) |

The old rule removed values both above and below the local median (MODIS 350 above, 364 below), concentrated in
exactly the transition months it was supposed to protect (MODIS 256 removals in Dec–Apr, 293 in Jun–Aug), and the
cleaned series is bimodal (MODIS kept SD 0.153 vs raw 0.093). Effect on MODIS PoS value: 0.714/0.693/0.680/0.683/0.651 (old, 2018–22)
vs 0.599/0.632/0.634/0.655/0.601 with no outlier filter at all, so the old peaks were inflated by 0.03–0.11, as the spec suspected.
Old PoS/SoS dates are also unrelated to the new ones (e.g. MODIS 2018 PoS day 20 vs 58–59; 2019 day 43 vs 11–13).

## Q2. Is the current filter appropriate per source?

- **MODIS: yes, but unnecessary.** 52 points removed, no systematic loss of peaks (PoS value identical to no-filter to ±0.004 in four of five years).
- **S2: partly.** Window 7 spans ~5 weeks of images. It removes 6 points above and 6 below the local median; the above-median ones include the first record value (0.744) and 0.687 on 2021-01-09, both in the high-NDVI season. S2 2019 PoS: with the window filter day 42 / 0.707; with every other option the PoS is at the record start (day 365 of the previous hydrological year, 0.743), which is a **truncation artefact** (record begins 2018-12-31), not a result — see "Not verified".
- **L8: no.** Window 7 spans ~6 weeks; it removes 8 points above and 7 below the local median, including all three seasonal peaks. L8 peaks 0.669/0.599/0.743 (window 7) vs 0.724/0.734/0.771 (no filter, B, C, E all agree).

External check against NSRS (daily mean of NSRS_1–3 LOWESS, overlapping dates only, `direct_nsrs_agreement.csv`).
Overlap sizes differ between variants (the old rule leaves few points), so compare within a column only:

| Satellite | variant | n | bias | RMSE | r |
|---|---|---|---|---|---|
| MODIS | A window 7 | – | −0.025 | 0.052 | – |
| MODIS | C | 385 | −0.023 | 0.052 | 0.932 |
| MODIS | D none | 389 | −0.023 | 0.052 | 0.934 |
| S2 | A window 7 | – | 0.062 | 0.077 | – |
| S2 | C | 27 | 0.057 | 0.073 | 0.929 |
| S2 | D none | 29 | 0.054 | 0.069 | 0.933 |
| L8 | A window 7 | – | 0.054 | 0.059 | – |
| L8 | C | 16 | 0.033 | 0.060 | 0.897 |
| L8 | D none | 17 | 0.033 | 0.059 | 0.906 |

No filter beats "none" against NSRS for S2 and L8; the differences are within what 17–29 overlapping dates can resolve. The old rule's
MODIS RMSE (0.041) looks better but is computed on 102 dates (vs 389) selected by the rule itself, so it is not comparable.

## Q3. Design comparison

(a) window 7/k 3 — fails on sparse sources (above). (b) ±15 d, both sides — fixes the span problem, but still removes
S2/L8 points above the median (4–5 each). (c) ±15 d, downward only — removes only low points; indistinguishable from none on MODIS, removes the visible cloud dips on S2/L8.
(d) none — best direct agreement on S2, and phenology equal to (c) everywhere except two L8/S2 SoS dates.
(e) simplified Chen et al. (2004) upper-envelope Savitzky–Golay (my reduction of the method: 45-day window, order 2, 8 iterations, remove >0.05 below the envelope; **not a faithful reimplementation**) — removes 48 % of MODIS (dozens of valid winter values, PoS dates shifted 7–30 days), so its parameters would need tuning and it is not recommended here.

**Recommendation: (c).** Reason: cloud/aerosol contamination is one-sided; (c) removes the clearly depressed points, cannot remove a peak, and does not depend on the observation cadence. (d) is an acceptable alternative; the result does not hinge on the choice (Q4).

## Q4. Sensitivity

PoS value, window 5/7/11/15 × k 2.5/3/4 (variant A grid), min–max across all 12 settings (`phenology_by_variant.csv`):

| Source | year | PoS value | EoS day |
|---|---|---|---|
| MODIS | 2018–2022 | 0.60 / 0.63 / 0.63 / 0.64–0.66 / 0.60 (range ≤ 0.02) | within ±3 d except 2020 (180–238) |
| S2 | 2020 | 0.61–0.71 | 145–160 |
| L8 | 2019/2020/2021 | 0.67–0.70 / **0.56–0.64** / **0.53–0.74** | 127–135 / 159–233 / 84–105 |

MODIS is stable (the 2020 EoS and the 2021/2022 SoS/PoS day ranges come from flat summer/winter curves where the 20 % threshold crosses at near-equal NDVI). S2 and L8 are not: results change by up to 0.2 NDVI and months depending on window and k — another reason not to use an observation-count filter on them.
PoS day-of-year ranges of 1–366 in the table (L8 2021, MODIS 2021) are wrap-around at the hydrological-year boundary, not real month-scale shifts.

Table 4 (MODIS: `table4_by_variant.csv`; grid min–max): Full signal MAE 0.041–0.043, RMSE 0.052–0.053, r 0.972–0.975, bias −0.02 — essentially identical for A, B, C, D. S2: Full signal MAE 0.054–0.064, r 0.89–0.96, bias +0.05. L8 (n = 11–16 dates): Full signal r 0.17–0.98 across grid; at A (n 11) r 0.979, at C/D r 0.88–0.90 — L8 Table-4 numbers are not stable.
Woody / Herbaceous rows: MAE 0.35–0.45 (herbaceous), r negative for S2/L8 woody. These reflect comparing a satellite-derived component to a different-quantity NSRS layer (bias ≈ −MAE, see `decomposition_validation.py` header) and 11–25 paired dates, and **do not change with the cleaning choice** except L8.

## Q5. Methods text (Section 2.4.1)

- NSRS: "Values outside [0.2, ∞) were discarded; each remaining observation was compared with the median of its 7 neighbouring daily observations and removed if it deviated by more than max(3 × 1.4826 × MAD, 0.02), where MAD is taken over a 31-observation window; the series was then smoothed with LOWESS." (matches current code)
- MODIS, S2, L8 (if recommendation adopted): "Values outside [min, max] (MODIS ≤ 0.8; S2, L8 ≥ 0.4) were discarded. An observation was additionally removed when it lay more than max(3 × 1.4826 × MAD, 0.02) **below** the median of all observations within ±15 days (MAD over ±90 days); high values were retained because cloud and atmospheric contamination lower NDVI. The series was then smoothed with LOWESS."
- If the current code is kept for the satellites, the text must say 7 *observations* (≈ 1 week for MODIS, ≈ 5–6 weeks for S2/L8), and that this removes the highest L8 values.

## Config-only alternative: per-source threshold floor (`scripts/audit/floor_variant.py`)

The observation-window filter with a higher `outlier_min_threshold` for the sparse sources (MODIS 0.02 unchanged, S2 0.08, L8 0.10; window 7, k 3).
Larger windows make the L8 problem worse (window 11/15 remove 6–7 of the 7 highest observations); the floor is the effective lever
(L8 window 7: floor 0.02 removes 15 points, 0.08 removes 3, 0.10 removes 2). Outputs: `floor_phenology.csv`, `floor_table4.csv`, `floor_direct.csv`.

PoS value (A = current, F = floor, C = ±15 d downward-only, D = none):

| | A | F | C | D |
|---|---|---|---|---|
| MODIS 2018–22 | = | identical to A | within ±0.004 | within ±0.004 |
| S2 2019 / 2020 / 2021 | 0.707 / 0.704 / 0.800 | 0.743 / 0.705 / 0.800 | 0.743 / 0.704 / 0.800 | 0.743 / 0.706 / 0.797 |
| L8 2019 / 2020 / 2021 | 0.669 / 0.599 / 0.743 | 0.724 / **0.642** / 0.772 | 0.724 / 0.734 / 0.771 | 0.724 / 0.734 / 0.771 |

Agreement with NSRS: S2 RMSE 0.077 (A) → 0.072 (F), r 0.919 → 0.931; Table 4 Full signal MAE 0.061 → 0.058, r 0.908 → 0.938. L8 RMSE is 0.059 for A, F and D (n 11–17: not resolvable);
Table 4 Full signal r 0.979 (A, n 11) → 0.912 (F, n 14). MODIS identical. S2/L8 SoS/EoS dates still move between variants (e.g. L8 2020 SoS day 265 vs 303; S2 2020 EoS day 136 vs 152).
The floor recovers the S2 and L8 2019/2021 peaks but **still removes the L8 2020-03-07 peak (0.642 vs 0.734)**. The floors are tuned to this site.

## Decision

- **Now (research hand-over):** keep the **floor option**. `scripts/run_rh_ndvi.py` sets `outlier_min_threshold` to 0.08 (S2) and 0.10 (L8); MODIS and NSRS are unchanged. The Methods text should state window = 7 observations, floors as above, and that they were chosen from the sensitivity analysis. Known limitation: one L8 peak (2020) is still removed.
- **Future (after the research is handed over):** move the satellites to the **downward-only, calendar-window** filter (`outlier_window_days=15, outlier_direction="down"`, already implemented). It is independent of observation cadence and cannot remove a peak. Literature support is for the premise (clouds and atmosphere lower NDVI: Holben 1986, Viovy et al. 1992, Chen et al. 2004, TIMESAT), read at abstract/secondary level only; the specific median/MAD rule is this project's design, not a published method.

## Manuscript cells / sentences affected by the recommendation (to be checked against the .docx by the author; I did not open it)

- Section 2.4.1: replace the single "sliding-window" description by the per-group text above.
- Table 3 satellite rows (MODIS, S2, L8 SoS/PoS/EoS dates and PoS values): L8 changes most (PoS 0.599→0.734 in 2020); S2 2019 changes (edge case below); MODIS PoS values are within ±0.004 of the no-filter values but differ from the old-rule values (see Q1) by −0.03…−0.11.
- Table 4 (MODIS, S2 rows, and the new L8 rows): MODIS ≈ unchanged vs. current window-7 numbers; S2 Full signal MAE 0.061→0.059, r 0.908→0.937; L8 r 0.979→0.880 (n 11→15).
- Sections 3.1–3.2: any statement quoting satellite peak/EoS dates; any claim that the satellite cleaning "removed clouds" without qualification.
- Fig S4–S6 captions: S4's "bimodal winter/summer clusters" for MODIS may be a property of the old rule (kept SD 0.153 vs raw 0.093) rather than of the raw data; re-check against the raw histogram.

## Not verified

- The Chen et al. (2004) reference was only read at abstract level in the spec; the simplified envelope implemented here is not that algorithm and no TIMESAT comparison was run.
- No ground truth for individual satellite observations (cloud flags / QA bands were not available), so "outlier" status of a removed point is inferred from neighbours, not confirmed.
- S2 2019, MODIS 2018 and L8 2019 hydrological years begin mid-season (records start Jan 2018/2019), so SoS/PoS in those years are partly edge effects (`SoS_doy` 5 or 365, `PoS_doy` 365). They were not corrected.
- S2/L8 overlap with NSRS is 16–29 dates; metric differences of ~0.01 are not resolvable.
- The `.docx` manuscript was not opened; the list of affected cells follows the spec's list and the numbers above.
- `scripts/run_rh_ndvi.py` was not re-run end-to-end with the new option; the audit used the same pipeline functions on the same CSVs.

## Addendum: L8 same-date duplicates (supersedes the L8 floor results above)

The L8 CSV lists 22 dates twice. Earth Engine shows why: the site lies in the overlap of rows 37 and 38 of path 174 (`LANDSAT/LC08/C02/T1_L2`),
so one overpass is exported as two scenes about 24 s apart (values differ by ~0.01). They are one observation. `SourceConfig.average_same_date` /
`average_same_date()` now averages them (enabled for L8 in `run_rh_ndvi.py`; MODIS, S2 and NSRS have no duplicate timestamps). L8 then has 51 distinct valid dates, not 73 rows.
The original `C01` collection no longer exists in Earth Engine, so the CSV could not be regenerated or compared value by value.

Effect: observation windows are now twice as wide in time, and the **L8 floor no longer protects the peaks**. With window 7 the removal is driven by the MAD term, not the floor:
floors 0.02 to 0.15 all remove the top-3 values (0.78, 0.74, 0.73) plus 0.69; only window 5 with floor 0.15 (or no filter) keeps them. L8 PoS value, window-7 + floor 0.10:
2020 0.641 and 2021 **0.538**, against 0.734 and 0.772 with no filter or the downward-only ±15 d option. S2 is unaffected. So the L8 part of the Decision above rests on a tuning that held only on the duplicated series;
it needs the author's revisit (options: no outlier filter for L8, or the downward-only calendar window now).

## Update: L8 excluded from the analysis by data-sufficiency rules

Given the addendum above, L8 is left out of phenology, Table 4 and the comparative/decomposition figures, by rule rather than by choice: `lensky_py_lab.pipeline.eligibility`
(>= 40 valid dates in the NSRS window and valid data in >= 60 % of months, judged after the extreme filter and before the outlier filter). RH verdicts (`source_eligibility.csv`):

| Source | valid dates in window | month coverage | verdict |
|---|---|---|---|
| MODIS | 523 | 1.00 | in |
| S2 | 45 | 0.65 | in (narrowly) |
| L8 | 32 | 0.58 | out (both rules) |

The thresholds are judgment calls set after the data had been seen; L8 fails and S2 passes by small margins, so the Methods must state the rules and the numbers. L8 stays in the data-availability
chart ("(excluded)") and is still processed and shown in its data-cleaning figure. The L8 filter question therefore no longer affects the paper; the L8 floor (0.10) stays in the config only so that the processed L8 series is not cut when inspected.
Full run: `python scripts/run_rh_ndvi.py --data-dir data/research_results/RH_NDVI --ims-dir data/research_results/IMS --out-dir <dir>`.
