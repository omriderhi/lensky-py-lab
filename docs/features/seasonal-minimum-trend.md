# Woody series: straight line through the yearly NDVI minima (v20)

**Decision (Omri's supervisor, conveyed 10 Nov 2026; supersedes the 4 Nov interpolation draft):** *keep the linear regression of each seasonal-year minimum; take all the years of the observation and interpolate as one array.* This is the default of `decompose_woody_herbaceous()` and of `scripts/run_rh_ndvi.py` from manuscript v20.

## Method

Input: the LOWESS-smoothed NDVI of one satellite (`NDVI lowess MODIS`, `NDVI lowess S2`), indexed by unix timestamp.

1. **Local dates.** Seasonal years and every reported date use Asia/Jerusalem calendar dates. `TS` is local midnight of a machine in Israel, which is stored as 21:00 or 22:00 UTC of the previous day, so UTC dates would put an observation of 1 September into the old seasonal year (see `archive/eligibility-utc-issue.md`). With UTC dates the MODIS 2018 minimum would be the 1 Sep 2018 observation (0.4287) and the slope +0.00187 per year; the local-date values are in the tables below.
2. **Seasonal year** Y runs 1 September (Y−1) to 31 August Y.
3. **Yearly minimum.** Every seasonal year with at least one observation (`min_obs=1`) gives a point: the minimum smoothed NDVI of that year, at its own date (the first one if tied). The partial years at the two ends of the record count.
4. **One regression.** One ordinary least-squares line `NDVI = a + b·t` (t in unix seconds) through all those points. At least 2 seasonal years are needed; otherwise `decompose_woody_herbaceous` returns `(None, None)` with a warning.
5. **Woody series** `w(t) = a + b·t` at every date of the series: a straight line, no steps, no NaN, no values outside the series' own dates.
6. **Herbaceous component** `h(t) = NDVI(t) − w(t)`; **NDVI_H** of a seasonal year is the maximum of `h` in it.

Not used by this method: the June–August mean, the wet-season minimum rule, interpolation between dry seasons, the 16 July anchor and `min_dry_obs`.

## API and outputs

- `decompose_woody_herbaceous(series, method="seasonal_min_trend", min_obs=1, tz="Asia/Jerusalem")`.
- `seasonal_min_table(series, min_obs=1, tz=...)`: one row per seasonal year (`n_obs`, `first_date`, `last_date`, `partial`, `ndvi_min`, `ndvi_min_date`, `woody_at_min`, `NDVI_H`). The fit is in `df.attrs` (`a`, `b`, `slope_per_year`, `n_points`, and the line value and date at the first and last date of the series). `partial` is True only for the first / last seasonal year when the record starts more than 30 days after its 1 September / ends more than 30 days before its 31 August; sparse years in the middle of a record are not flagged.
- `run_rh_ndvi.py` writes, per satellite, `RH_NDVI_<sat>_decomposition.csv` (`TS`, `woody`, `herbaceous`; Table 4 reads this), `RH_NDVI_<sat>_seasonal_min.csv` and `RH_NDVI_<sat>_woody_trend.json`. `RH_NDVI_<sat>_helman_annual.csv` is written only with `--decomposition helman2015`.

## Reproducing earlier runs

| Run | Command (same inputs) |
|---|---|
| v20 (this method) | `python scripts/run_rh_ndvi.py` |
| interpolation draft (4 Nov) | `--decomposition helman2015` |
| v19 (Helman 2015 as published: steps + abrupt-loss rule) | `--decomposition helman2015 --woody-interp step --wet-min-rule` |
| v12 (calendar-year Jun–Aug regression) | `--decomposition linear_trend` |

`--woody-interp` and `--wet-min-rule` are errors with any other `--decomposition`. The earlier methods still assign dates in UTC, unchanged. `linear_trend` is a regression through the calendar-year mean of Jun–Aug, read at each date's calendar year.

## Results (`data/v20_run`, input `data/research_results`, local dates)

Yearly minima, partial flag, NDVI_H:

| Source | Seasonal year | ndvi_min | date | n_obs | partial | NDVI_H |
|---|---|---|---|---|---|---|
| MODIS | 2018 | 0.4290 | 2018-08-27 | 148 | yes | 0.1887 |
| MODIS | 2019 | 0.3927 | 2018-10-03 | 212 | no | 0.2209 |
| MODIS | 2020 | 0.4170 | 2020-07-25 | 221 | no | 0.2197 |
| MODIS | 2021 | 0.4178 | 2021-08-29 | 263 | no | 0.2388 |
| MODIS | 2022 | 0.4178 | 2022-08-24 | 212 | no | 0.1833 |
| S2 | 2019 | 0.4439 | 2019-08-19 | 19 | yes | 0.2953 |
| S2 | 2020 | 0.4295 | 2020-08-13 | 32 | no | 0.2705 |
| S2 | 2021 | 0.4108 | 2021-08-18 | 35 | no | 0.3860 |
| S2 | 2022 | 0.4310 | 2021-10-07 | 4 | yes | 0.0625 |

`partial` marks MODIS 2018 (the record starts 6 Jan 2018), S2 2019 (1 Jan 2019) and S2 2022 (7 Oct–11 Nov 2021, 4 dates before green-up: its NDVI_H is not a seasonal peak and is left out of the S2 range).

Trend: MODIS slope +0.0018 per year, line 0.4104 (6 Jan 2018) → 0.4188 (24 Aug 2022); S2 slope −0.0103 per year, line 0.4484 (1 Jan 2019) → 0.4190 (11 Nov 2021). The herbaceous component is below zero on 1.0 % of MODIS dates (lowest −0.019, 3 Oct 2018) and 8.9 % of S2 dates (lowest −0.011, 18 Aug 2021). The woody line changes by at most 0.00005 (MODIS) and 0.0018 (S2) between neighbouring dates.

Table 4:

| Satellite | Comparison | Reference | n | MAE | RMSE | r | bias |
|---|---|---|---|---|---|---|---|
| MODIS | Full signal | NSRS_3 | 371 | 0.042 | 0.052 | 0.97 | -0.018 |
| MODIS | Woody | NSRS_2 | 357 | 0.158 | 0.174 | -0.29 | -0.158 |
| MODIS | Herbaceous | NSRS_1 | 342 | 0.412 | 0.423 | 0.86 | -0.412 |
| S2 | Full signal | NSRS_3 | 46 | 0.039 | 0.048 | 0.96 | 0.027 |
| S2 | Woody | NSRS_2 | 46 | 0.151 | 0.165 | 0.08 | -0.151 |
| S2 | Herbaceous | NSRS_1 | 44 | 0.372 | 0.379 | 0.89 | -0.372 |

S2 woody / herbaceous n rises from 44 / 42 to 46 / 44 because the line has a value on every date (the Sep–Nov 2021 dates are no longer NaN). The full-signal rows are unchanged. As before, the components are defined differently from the NSRS layers, so these numbers measure agreement, not accuracy, and a correlation of the woody line with NSRS_2 is not expected to be high: a straight line barely varies.

Earlier methods on the same input (`data/results_interp_rerun/RH_NDVI_final_result.csv`), woody / herbaceous rows:

| Run | MODIS woody (n 357) MAE / RMSE / r | MODIS herb. (342) MAE / RMSE / r | S2 woody (44→46) MAE / RMSE / r | S2 herb. (42→44) MAE / RMSE / r |
|---|---|---|---|---|
| v19 (`data/helman_run`) | 0.140 / 0.156 / 0.34 | 0.429 / 0.439 / 0.88 | 0.154 / 0.166 / −0.00 | 0.377 / 0.383 / 0.89 |
| interpolation (`data/results_interp_rerun`) | 0.127 / 0.145 / 0.19 | 0.444 / 0.454 / 0.87 | 0.143 / 0.156 / −0.07 | 0.388 / 0.393 / 0.91 |
| v20 | 0.158 / 0.174 / −0.29 | 0.412 / 0.423 / 0.86 | 0.151 / 0.165 / 0.08 | 0.372 / 0.379 / 0.89 |

The numbers of the 4 Nov interpolation draft in `helman-decomposition-alignment.md` (MODIS woody r 0.18, RMSE 0.144; wet-season minimum on 2018-10-03) were computed in a cloud session; that session's dates are one day later than the local run's, which fits a machine in UTC (`TS` = midnight UTC; this was not checked, only the pattern). The local run in `data/results_interp_rerun` has `TS` at 21:00/22:00 UTC and gives r 0.19, RMSE 0.145 and 2018-10-02 (the UTC date of the same observation). Tables of this page come from `data/v20_run` with local dates.
