# Spec: satellite data cleaning audit (MODIS, Sentinel-2, Landsat-8)

**For:** an agent working independently on branch `fix/p2-figure-readability` (or a branch off it).
**Goal:** decide, with evidence, how MODIS, S2 and L8 NDVI should be cleaned before LOWESS, and make the code and the manuscript Methods text say the same thing. Produce a written report; change code only where this spec says so.

## 1. Background (read first)

The pipeline cleans each source in three steps: `filter_extreme_values` → outlier filter → LOWESS (`src/lensky_py_lab/pipeline/`).

The outlier filter used to be `filter_by_average_groups`. Despite the manuscript (Section 2.4.1, "outlier detection using a sliding-window approach"), it compared every value against the **global** mean and **kept** values at least `average_window` away from it, discarding the ordinary values near the mean. The cleaned series became bimodal, the transitions that carry SoS and EoS were deleted, and the ends of series were trimmed. This was found on the NSRS ground sensors (see `docs/features/v12-review-fixes.md`, `docs/features/manuscript-comparison.md`).

It was replaced by `filter_outliers_sliding_window` (`pipeline/cleaner.py`): a point is removed when it deviates from the median of its centred window of `outlier_window` **observations** by more than `max(outlier_k × 1.4826 × MAD, outlier_min_threshold)`. Defaults: window 7, k = 3, floor 0.02 NDVI, MAD over 31 observations. The old rule is gone (`SourceConfig.from_notebook_dict` raises on `average_window`).

**The satellite sources currently use the same filter with the same untuned settings** (`outlier_window: 7` in `scripts/run_rh_ndvi.py`). Those settings were chosen for dense daily ground sensors. Nobody has checked that they suit satellite series. Treat every satellite number produced since this change as provisional.

## 2. Why satellites may need different handling

- **Noise is one-sided.** Cloud and atmospheric contamination push NDVI down, so good observations sit at the upper envelope. A symmetric window filter can treat a real high value as an outlier next to a cloud-depressed neighbour. Chen et al. (2004), *Remote Sens. Environ.* 91:332–344, doi:10.1016/j.rse.2004.03.014, builds a Savitzky–Golay fit towards the upper envelope for that reason (checked from the abstract only; read the full text before relying on it).
- **Sparsity.** A window of 7 observations covers about a week for daily MODIS but about 5 weeks for S2 (about 5 images/month) and about 6 for L8 (about 4/month). Observation-count windows are not comparable across sources. A time-based window is the natural alternative.
- **Different failure modes.** MODIS (MOD09GQ, 250 m, daily) has geometry noise, bimodal winter/summer clusters (manuscript Fig S4 caption) and a configured maximum of 0.8. S2 and L8 are cloud-screened upstream and sparse.
- **Mixed pixels.** The satellite pixel mixes woody and herbaceous cover, so real seasonal change is large and fast, and a window that is too short or a threshold that is too tight can cut genuine green-up.

## 3. Observed effect of the change (from the author's run, `data/research_results/RH_NDVI`)

Comparison of `phenology_markers.csv`: old rule (factor 1.364 run) vs sliding window (window 7, k = 3, floor 0.02).

| Source | Year | PoS shift (days) | PoS value old → new | EoS shift (days) |
|---|---|---|---|---|
| MODIS | 2018 | +38 | 0.714 → 0.599 | +8 |
| MODIS | 2019 | −30 | 0.693 → 0.632 | +21 |
| MODIS | 2020 | +21 | 0.680 → 0.634 | +3 |
| MODIS | 2021 | +9 | 0.683 → 0.655 | −6 |
| MODIS | 2022 | −21 | 0.651 → 0.601 | +8 |
| S2 | 2019 | +42 | 0.743 → 0.707 | +79 |
| S2 | 2020 | +21 | 0.710 → 0.704 | −3 |
| S2 | 2021 | −6 | 0.797 → 0.800 | censored (record ends before EoS) |

MODIS peaks fall by 0.03 to 0.11. The old rule kept only the extremes, so it probably inflated the MODIS peaks. Table 4 (woody/herbaceous decomposition vs NSRS) and the satellite columns of Table 3 depend on these series. L8 had no decomposition before and now has one.

## 4. Questions to answer

1. **Is the old satellite output biased, and how?** Show the cleaned series (old vs new) against raw for MODIS, S2, L8, and quantify what the old rule removed (counts, by season, by NDVI level).
2. **Is the new filter appropriate for each source?** For each source, does it remove clouds/noise without removing real green-up or the true peak? Use the NSRS series as external reference (daily, near-surface, same site) wherever dates overlap.
3. **Which design should satellites use?** Evaluate at least: (a) the current window filter, (b) a time-based window (e.g. ±15 days), (c) a one-sided / upper-envelope variant that removes only downward outliers, (d) no outlier filter (extreme-value filter + LOWESS only). Include one standard method from the literature as a reference (e.g. Savitzky–Golay upper envelope per Chen et al. 2004, or TIMESAT-style weighted fitting; verify what each paper actually does before citing).
4. **How sensitive are the results to the choice?** Report SoS/PoS/EoS dates, peak values and Table 4 metrics (MAE, RMSE, bias, r vs NSRS) under each option and under window 5/7/11/15 and k 2.5/3/4. A conclusion that holds across settings is stronger than one tuned to a setting.
5. **What should the Methods text say?** One sentence per source group, accurate to what the code does.

## 5. Method

- Work from `data/research_results/RH_NDVI/{MODIS,S2,L8}.csv`; do not modify them or `data/results/`.
- Put analysis scripts under `scripts/audit/` (new) or a scratch directory; write outputs to a new `data/results_*/` directory (gitignored).
- To compare with the old rule, reconstruct it in a script only (global-mean deviation, keep if `|x − mean| ≥ window`, windows 0.1125 for MODIS and 0.1005 for S2/L8). Do not reintroduce it into `src/`.
- Judge against raw data and the NSRS ground sensors, not against the old output. The old output is the thing being questioned.
- If recommending a different filter, implement it as a new `SourceConfig` option with tests and keep `filter_outliers_sliding_window` working; do not silently change NSRS results (they are the validated case).

## 6. Deliverables

1. `docs/features/satellite-data-cleaning-audit-report.md`: findings per question above, with the figures and tables, and a clear recommendation.
2. A list of manuscript cells and sentences that change under the recommendation (Table 3 satellite rows, Table 4, Section 3.1–3.2, Fig S4–S6 captions, Section 2.4.1).
3. If the recommendation differs from the current code: the code change with tests, in a separate commit.
4. A statement of what was **not** verified.

## 7. Constraints and acceptance

- No hardcoded NSRS_3 factor anywhere (it is derived from the data).
- `python -m pytest -q` passes; NSRS outputs unchanged unless the report explains why.
- Cite only papers whose full text (or at least abstract) was read; mark which. Do not invent page numbers or DOIs.
- Do not edit the manuscript `.docx`.
- Do not push or open a PR without the author's go-ahead.
