# Feature: v12 reviewer fixes (Noam Levin round), pass of 2026-10-15 to 2026-10-17

**Branch:** `fix/p2-figure-readability` (base commit `57023ae`, "switch to Okabe-Ito colorblind-safe palette")
**Commits on top of base** (oldest first):

| Commit | Subject |
|---|---|
| `5a684b1` | derive NSRS_3 factor from data, share RMSE, ignore regen outputs |
| `8579d9b` | tighten degenerate-season filter, equalise decomposition y-span |
| `131bee5` | add NSRS_3 FOV crown-fraction helper (reviewer [18]) |
| `7025f5c` | list `fov_canopy_fraction.py` in CLAUDE.md |
| `5f92b75` | calibration panel A: plot observations with gap breaks, no resampling |

**Tests:** `python -m pytest -q` → 88 passed.
**Reviewer ask:** check that each change does what its *Intent* says, that nothing changes a published number without being listed under *Numeric impact*, and that the *Not changed (deliberately)* items were left alone.

---

## Context

The manuscript `Derhi_WoodyHerbaceous_FINAL_v12` got 31 review comments from Noam Levin. The comment IDs in brackets (e.g. `[37]`) refer to that review. Most figure-readability comments (`[30] [32] [33] [34] [37] [38]`) were handled earlier, in `3787f3e`, `ed1e30d` and `57023ae`. This pass regenerated every figure, fixed the defects the renders exposed, then acted on two code reviews of the working tree.

Anything that would change a scientific claim without a decision from the author is listed under *Not changed*.

---

## Changes

### 1. NSRS_3 sky-catch factor is derived from the data, and optional
**Files:** `sensors/nsrs_calibration.py`, `scripts/run_rh_ndvi.py`, `scripts/example_rh_ndvi.py`, `sensors/daily_graphs.py`, `tests/test_calibration.py`

**Intent:** no factor is hardcoded anywhere. It is the RMSE-minimising multiplier of NSRS_3 against the mean of NSRS_1 and NSRS_2, and using it is optional.

- `calibrate_nsrs3_sources(nsrs_sources)` processes nothing itself. It takes sources processed **without** `general_factor`, derives the factor from the merged raw NSRS_3 series, multiplies it into the NSRS_3 / NSRS_3_B LOWESS columns, and registers it (`set_active_factor` / `get_active_factor`).
- `apply_nsrs3_factor(sources, factor)` applies a fixed factor; applying twice raises `ValueError`.
- `clear_active_factor()` is called at the start of every `run()`, so no factor leaks between runs in one process.
- `run_rh_ndvi.py --nsrs3-factor auto|none|<number>` (default `auto`). Step 9 (validation figure and `calibration_statistics.csv`) only runs in `auto` mode.
- `get_logger_ndvi` (daily graphs) calibrates sensor 3 only if a factor was registered in the same process. `run_rh_ndvi.py` registers it before its daily-graph step. The standalone `scripts/run_daily_graphs.py` has the same `--nsrs3-factor auto|none|<number>` option; `auto` derives the factor from the NSRS CSVs in `--data-dir` / `RH_DATA_DIR`, and without them sensor 3 is left uncalibrated with a printed notice.
- `NSRS3_PUBLISHED_FACTOR = 1.4` survives **only** as the earlier hardcoded value, for comparison (`published_factor`, `published_factor_rmse`). It is never applied. The manuscript (v12) reports the optimum, 1.36, which the derived 1.364 reproduces.
- `apply_calibration(series, factor=None)` raises if no factor is given and none is registered.

**Numeric impact** (measured on `data/research_results/RH_NDVI`):

| | earlier code (1.4) | derived (1.364) |
|---|---|---|
| NSRS_3 values | reference | about 2.6 % lower (ratio 0.9737 to 0.9747) |
| Fig 5 panel C RMSE | 0.0329 | 0.0299 |
| raw RMSE / R² | 0.1494 / 0.957 | unchanged |
| other sources, all SoS/PoS/EoS dates | reference | unchanged |

*Measured before change 9 (outlier filter); superseded by its table.* With the old filter, `--nsrs3-factor 1.4` was **byte-identical** to the original code at `57023ae`. That is no longer reproducible, because the legacy filter was removed. To reproduce the pre-change outputs exactly, use that flag. The manuscript's Tables 3 and 4 were computed with ×1.4 while Table 2 and the text say ×1.36; the research documents are being aligned to the derived factor (see `manuscript-comparison.md`).

**Check:** `grep -rn "1\.4" src scripts` should show the thesis value only in `nsrs_calibration.py` (docs and comparison) and unrelated linewidths.

### 2. One shared RMSE implementation
**Files:** new `metrics.py`, `sensors/nsrs_calibration.py`, `phenology/decomposition_validation.py`

**Intent:** a single `metrics.rmse()` (NaN-aware) replaces the private copy in the calibration module and the inline formula in decomposition validation. Same numbers.

### 3. RMSE reporting no longer confuses optimal and published
**File:** `scripts/run_rh_ndvi.py`, `CLAUDE.md`

The console line used to print the RMSE at the optimal factor as "after". It now prints `RMSE raw: 0.1494  published ×1.4: 0.0329  (optimal ×1.364: 0.0299)`. CLAUDE.md quotes both values.

### 4. Phenology markers: stricter degenerate-season filter, with an opt-out
**File:** `visualization/phenology_markers.py`

**Intent:** hydrological years only partly covered by data yield nonsense markers (events piled within days, SoS == PoS). A row is drawn only if:
- the events present (SoS, PoS, EoS) are strictly increasing, which also catches partial rows with a missing date, and
- when all three exist: SoS→EoS ≥ 60 days (`MIN_SEASON_DAYS`) **and** PoS→EoS ≥ 14 days (`MIN_PEAK_TO_END_DAYS`).

`draw_phenology_markers(..., skip_degenerate=True, min_season_days=60, min_peak_to_end_days=14)`. Each suppressed season is logged once (`logger.warning`). `extract_phenology()` and `phenology_markers.csv` are unchanged, so Table 3 is unaffected.

**Seasons suppressed with the current data:** NSRS_1 2022, NSRS_2 2020, NSRS_2 2022, NSRS_3 2022, MODIS 2018, S2 2019. NSRS_2 2020 (PoS 22 Apr, EoS 25 Apr) is newly suppressed by the 14-day rule; NSRS_2 is excluded from Table 3 anyway.

**Check:** is 60 days a sensible floor, and is 14 days a sensible PoS→EoS floor, for Mediterranean herbaceous seasons?

### 5. Decomposition figure: equal y-span on all three panels
**File:** `visualization/figure_generator.py` (`plot_decomposition_comparative`, `_equalize_y_span`)

**Intent:** comment `[37]`. Panels A, B and C share one y-span, each centred on its own data. Panels with no plotted data are ignored when choosing the span, so an empty panel's default (0, 1) limits cannot flatten the rest. Axis limits only; no numbers change. Tests now assert panel A too, and the empty-panel case.

### 6. Calibration figure panel A: observations plotted with gap breaks
**File:** `sensors/nsrs_calibration.py` (`create_calibration_figure`)

**Intent:** panel A used to draw straight lines across the May to Oct 2020 NSRS gap. It now breaks lines at gaps over 60 days, as every other time-series figure does, but plots the **real observations** instead of resampling to 800 points. Raw and corrected NSRS_3 share one set of boundaries and so break together. The Panel D legend shows the optimal factor to three decimals. Styling is unchanged.

### 7. New script: NSRS_3 FOV canopy fraction (comment `[18]`)
**File:** `scripts/fov_canopy_fraction.py`, `tests/test_fov_canopy_fraction.py`

**Intent:** the share of a downward 180° cosine-response sensor's signal that comes from a crown, modelled as a horizontal disk (radius R, top at height h, horizontal offset d; sensor at height H).

- The azimuth integral is analytic, leaving a 1-D integral over the view zenith (about 200,000 points, negligible memory).
- For d = 0 it matches the closed form `R² / (R² + Δz²)`; tests also compare it against a brute-force 2-D grid.
- The three geometry inputs have **no silent defaults**: if any is omitted, the script prints a `!!!` banner naming the placeholder inputs and saying not to quote the result. It always prints the inputs used.
- Sanity values: sensor 6 m, crown top 5 m, diameter 6 m gives 90.0 % at offset 0 and 77.7 % at offset 2.

**Check:** is a horizontal disk an acceptable crown model, and is cosine weighting appropriate for the NSRS_3 sensor type?

### 8. Documentation and housekeeping
- `README.md`: the satellite table said `MODIS/061/MOD13Q1`; the code, data and cleaning config are `MODIS/061/MOD09GQ` (daily surface reflectance, b02/b01 NDVI).
- `CLAUDE.md`: repository-name note now states the real URL (`github.com/omriderhi/lensky-py-lab`); calibration section describes the data-derived factor; `fov_canopy_fraction.py` added to the scripts list.
- `.gitignore`: `data/results_*/` (regenerated review outputs; only `data/results/**` was ignored before).
- `phenology/phenolopy_integration.py` (docstring only): the Helman et al. (2015) reference now gives *Remote Sensing* 7(9):12314–12335, doi:10.3390/rs70912314, matching `Thesis_bib.bib → Helman2015`.

---

### 9. Outlier filter replaced by a real sliding-window rule; censored EoS
**Files:** `pipeline/cleaner.py`, `pipeline/processor.py`, `configs.py`, `constants.py`, `phenology/phenolopy_integration.py`, scripts, README/CLAUDE.md, `tests/test_outlier_filter.py`

**Intent:** make the code do what manuscript Section 2.4.1 says ("outlier detection using a sliding-window approach"). The old `filter_by_average_groups` compared each value with the **global** mean and kept only values at least `average_window` away from it, so it deleted ordinary data, left a bimodal series, trimmed series ends (NSRS_3 LOWESS stopped on 15 Apr 2020 although data runs to 24 Apr) and made SoS/EoS depend on the threshold (NSRS_1 2021 EoS moved by 3.5 months between 0.03 and 0.05). Raising the threshold or window cannot fix it (the group size was never used; a bigger threshold deletes more).

- New `filter_outliers_sliding_window`: remove a point if it deviates from the median of its centred `outlier_window` observations by more than `max(outlier_k × 1.4826 × MAD, outlier_min_threshold)` (window 7, k 3, floor 0.02, MAD window 31).
- `SourceConfig`: `average_window` removed, replaced by `outlier_window`, `outlier_k`, `outlier_min_threshold`, `outlier_scale_window`. `from_notebook_dict` raises on `average_window`. The legacy rule is gone.
- Satellites use the same filter with the same untuned settings; see `satellite-data-cleaning-audit.md`. Their numbers are provisional.
- `extract_phenology` adds `EoS_censored`: when the curve is still above the threshold on the last day of data, `EoS_date` / `EoS_value` / `EoS_doy` are NaT / NaN instead of the last day of data (NSRS 2020 EoS values of 24 Apr were record ends).

**Numeric impact** (`data/research_results/RH_NDVI`, derived factor, vs previous commit):

| | before | after |
|---|---|---|
| NSRS_3 derived factor | 1.364 | 1.384 |
| raw RMSE / optimal RMSE / RMSE at ×1.4 | 0.149 / 0.030 / 0.033 | 0.159 / 0.0405 / 0.0409 |
| R² / n co-observations | 0.957 / 296 | 0.899 / 470 |
| NSRS_1 2021 EoS | 4 Apr | 19 Jul |
| NSRS_3 2021 EoS | 2 Jun | 30 Jun |
| NSRS 2020 EoS | 10–24 Apr | not reached (censored) |
| NSRS peak values | | within 0.01 |
| MODIS peak values | 0.65–0.71 | 0.60–0.65 |

**Check:** NSRS LOWESS reaches the last observation; `EoS_censored` rows draw only SoS/PoS markers.

### 10. NSRS colour palette: green / brown / olive-brown
**Files:** `plot_config.py` (single source), fallback copies in `sensors/daily_graphs.py`, `sensors/nsrs_calibration.py`, `visualization/figure_generator.py`

NSRS_1 (herbaceous) is leaf green `#5BAA3C`, NSRS_2 (pine canopy) is dark brown `#6B3E1A`, NSRS_3 (mixed signal) is olive-brown `#7D7226`, between the two. The `_B` variants inherit them. NSRS_3 raw stays gray. The three differ in lightness as well as hue, to stay separable for colour-vision deficiency. As a side effect NSRS_1 no longer shares vermillion with the PoS marker (the colour clash in *Not changed* item 4 is resolved for NSRS_1; markers still carry no sensor identity). Colours only; no numbers change.

## Not part of the diff

- Regenerated outputs go to a `data/results_*/` directory (ignored). `data/results_regen_2026-10-15/` was produced in a different environment (timestamps up to 3 h off, values up to 4e-4 off) and is **not** a valid baseline for the current code.
- The orientation figures (`plot_pixel_size_comparison`, `plot_site_location`) do not regenerate without `contextily`; the run completes steps 1–11 and fails at step 12.
- `data/results/` (the author's existing outputs) was not modified and predates `57023ae`.

## Not changed (deliberately: need the author's decision)

1. **Woody baseline evaluated at integer calendar year.** `decompose_woody_herbaceous()` evaluates the linear trend at `times.year`, giving a staircase with steps on 1 Jan. Fractional time would be smoother but would shift Table 4.
2. **Herbaceous comparison mixes units.** Table 4 and decomposition panel C compare herbaceous ΔNDVI against NSRS_1's absolute NDVI (MAE 0.43, bias −0.43).
3. **NSRS_2 in phenology output and figures.** The manuscript excludes NSRS_2 from Table 3 as "near-constant", but the data show an ~0.2 NDVI seasonal swing.
4. **Markers carry no sensor identity.** The NSRS_1 / PoS colour clash was removed by change 10, but nothing links a marker to its sensor.
5. **In-figure titles** with internal names (`RH_NDVI — NSRS vs MODIS`).
6. **Phenology method naming.** The manuscript names Phenolopy, but the code is a native Savitzky–Golay + 20 % seasonal-amplitude implementation. Only the manuscript text needs to change.
7. **Manuscript edits.** The comparison against the regenerated outputs is done (`manuscript-comparison.md`); the manuscript itself has not been edited. Decision taken: the manuscript is aligned to the derived factor. After change 9 the derived factor is 1.384, not 1.36, so the comparison numbers in `manuscript-comparison.md` that were stated at 1.364 are superseded; see its second section.

## How to reproduce

```bash
# from repo root, Python >=3.10 with the package installed (pip install -e .) and pytest
python -m pytest -q                                  # 88 passed

# default: factor derived from the data
PYTHONPATH=src:. MPLBACKEND=Agg python scripts/run_rh_ndvi.py \
    --data-dir data/research_results/RH_NDVI \
    --ims-dir  data/research_results/IMS \
    --out-dir  data/results_review_check             # fails at step 12 without contextily

# fixed NSRS_3 factor, or no calibration:
#   add  --nsrs3-factor 1.4   or   --nsrs3-factor none

python scripts/fov_canopy_fraction.py --sensor-height 6 --crown-top 5 --crown-diameter 6
```

Expected calibration lines in `auto` mode: `NSRS_3 factor derived from data: 1.384 (thesis: 1.4)` and `RMSE raw: 0.1589  published ×1.4: 0.0409  (optimal ×1.384: 0.0405)`.

## Review checklist

- [ ] No literal 1.4 is applied anywhere in `src` or `scripts` (only `NSRS3_PUBLISHED_FACTOR`, for comparison)
- [ ] `--nsrs3-factor 1.4` applies exactly 1.4 to NSRS_3; `none` leaves NSRS_3 unscaled
- [ ] Marker filter (4) affects plotting only; `extract_phenology` and the CSV are unchanged
- [ ] Equal-span change (5) changes axis limits only, not data
- [ ] Panel A (6) plots every observation and breaks raw and corrected NSRS_3 at the same gaps
- [ ] `fov_canopy_fraction.py` prints the placeholder banner when inputs are omitted
- [ ] README/CLAUDE.md/docstring facts match the code and the git remote
- [ ] None of the *Not changed* items are touched
- [ ] Full test suite passes
