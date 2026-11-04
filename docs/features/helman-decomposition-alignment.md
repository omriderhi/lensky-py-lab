# Aligning the woody/herbaceous decomposition with Helman et al. (2015)

## Update Nov 2026: no minimum rule, woody interpolated between dry seasons

**Decision (Omri and his supervisor, 4 Nov 2026), used from manuscript v20:**

1. NDVI_W of each seasonal year is the mean of the smoothed NDVI over June–August. Helman et al. (2015)'s wet-season minimum (abrupt-loss) rule is **not applied**.
2. Each NDVI_W is placed at 16 July, the middle of its dry season, and the woody series is **interpolated linearly between successive dry seasons**. It no longer steps on 1 September.
3. Both Helman behaviours stay available as options: `woody_interp="step"` / `--woody-interp step` and `wet_min_rule=True` / `--wet-min-rule`.

**Why.** v19 (below) applied both, and the woody series looked like stairs. The rule fired in 4 of 5 MODIS seasonal years on the ordinary early-October low of an evergreen site, not on a fire or clearing. In 2019 the low of 0.393 (3 Oct 2018) replaced a June–August mean of 0.447, giving jumps of up to 0.05–0.06 every 1 September. Without the rule, the MODIS June–August means (seasonal years 2018–2022) are 0.457, 0.447, 0.455, 0.444 and 0.464; consecutive values differ by at most 0.020. Interpolation turns those differences into gradual slopes, a slowly varying woody level as assumed by Lu et al. (2003), and the herbaceous component (NDVI − woody) no longer jumps on 1 September either. Helman & Mussery (2020) used the June–August mean alone; they do not mention the rule.

**Reproducing v19:** `python scripts/run_rh_ndvi.py <same inputs> --woody-interp step --wet-min-rule`. On the repo's `data/research_results` CSVs this reproduces the v19 decomposition and annual tables exactly.

**Edges.** Before the first and after the last 16 July anchor the woody value is held at the nearest NDVI_W, but only inside seasonal years that have an NDVI_W; dates outside that span are NaN (S2 from 1 September 2021). A missing seasonal year between two others is bridged by the interpolation.

Per seasonal year, v20 (`RH_NDVI_<sat>_helman_annual.csv`; NDVI_W = `dry_mean`, rule off):

| Source | Seasonal year | NDVI_W | NDVI_H | rule would fire | wet-season min (date) |
|---|---|---|---|---|---|
| MODIS | 2018 | 0.457 | 0.142 | no | 0.479 (2018-04-30) |
| MODIS | 2019 | 0.447 | 0.181 | yes | 0.393 (2018-10-03) |
| MODIS | 2020 | 0.455 | 0.182 | yes | 0.448 (2019-10-10) |
| MODIS | 2021 | 0.444 | 0.207 | yes | 0.428 (2020-10-18) |
| MODIS | 2022 | 0.464 | 0.146 | yes | 0.422 (2021-10-14) |
| S2 | 2019 | 0.472 | 0.272 | no | 0.685 (2019-01-21) |
| S2 | 2020 | 0.454 | 0.247 | yes | 0.448 (2019-10-13) |
| S2 | 2021 | 0.425 | 0.375 | no | 0.444 (2020-10-07) |

S2 seasonal year 2022 has no dry-season dates and so no NDVI_W.

Table 4, v19 → v20 (full-signal rows unchanged: MODIS n 371, MAE 0.042, RMSE 0.052, r 0.97, bias −0.018; S2 n 46, 0.039, 0.048, 0.96, +0.027):

| Comparison | n | MAE | RMSE | r | bias |
|---|---|---|---|---|---|
| MODIS woody vs NSRS_2 | 357 | 0.140 → 0.127 | 0.156 → 0.144 | 0.34 → 0.18 | −0.140 → −0.125 |
| MODIS herbaceous vs NSRS_1 | 342 | 0.429 → 0.444 | 0.439 → 0.454 | 0.88 → 0.87 | −0.429 → −0.444 |
| S2 woody vs NSRS_2 | 44 | 0.154 → 0.143 | 0.166 → 0.156 | −0.00 → −0.07 | −0.154 → −0.143 |
| S2 herbaceous vs NSRS_1 | 42 | 0.377 → 0.388 | 0.383 → 0.393 | 0.89 → 0.91 | −0.377 → −0.388 |

The sections below describe the v19 alignment (October 2026) and are kept as the record of that step.


## What changed

`decompose_woody_herbaceous()` previously regressed a straight line through calendar-year Jun–Aug means. Helman et al. (2015, Sec. 2.3) does not do that. It works per seasonal year (Sep–Aug):

| Step | Helman 2015 | Now | Before |
|---|---|---|---|
| Year | seasonal year Sep→Aug | same | calendar year (Sep–Dec samples took the *previous* summer's value) |
| NDVI_W | Jun–Aug mean; the Oct–Apr minimum if lower | same | linear regression through the annual means |
| NDVI_Seas | NDVI − NDVI_W | same | NDVI − trend |
| NDVI_H | yearly max of NDVI_Seas | `helman_annual_table()` | not produced |

Choices not set by the paper (judgment calls): a seasonal year needs at least `min_dry_obs = 2` dry-season dates, otherwise woody and herbaceous are NaN (a record that ends in December gets no extrapolated woody value); the abrupt-loss rule searches Oct–Apr only, as the paper defines the wet season, so the September dry-season tail does not trigger it. `method="linear_trend"` keeps the old behaviour for reproducing earlier numbers.

SoS / PoS / EoS (`extract_phenology`) are unaffected: that function reads the LOWESS series directly and never calls the decomposition.

## Effect on the full pipeline run

`python scripts/run_rh_ndvi.py` on the local CSVs (`data/research_results`, current `S2.csv`: 90 dates, 2018-12-31 to 2021-11-10), output in `data/helman_run`. Earlier runs such as `data/s2_adopted_run` used an older `S2.csv`, so only compare like with like. MODIS, NSRS and all phenology markers other than S2 are identical to that run; S2 markers differ only because of the newer S2 file.

Per seasonal year (`RH_NDVI_<sat>_helman_annual.csv`):

| Source | Seasonal year | NDVI_W | NDVI_H | min rule used |
|---|---|---|---|---|
| MODIS | 2018 / 2019 / 2020 / 2021 / 2022 | 0.457 / 0.393 / 0.448 / 0.428 / 0.422 | 0.143 / 0.240 / 0.186 / 0.227 / 0.180 | no / yes / yes / yes / yes |
| S2 | 2019 / 2020 / 2021 | 0.472 / 0.448 / 0.425 | 0.272 / 0.259 / 0.387 | no / yes / no |

Table 4, `linear_trend` (old) → `helman2015` (new), both computed on the same data:

| Comparison | n | r | bias |
|---|---|---|---|
| MODIS woody vs NSRS_2 | 357 → 357 | 0.045 → 0.337 | −0.120 → −0.140 |
| MODIS herbaceous vs NSRS_1 | 342 → 342 | 0.863 → 0.884 | −0.449 → −0.429 |
| S2 woody vs NSRS_2 | 46 → 44 | −0.219 → −0.001 | −0.138 → −0.154 |
| S2 herbaceous vs NSRS_1 | 44 → 42 | 0.917 → 0.893 | −0.385 → −0.377 |

Full-signal rows are unchanged (MODIS n = 371, r = 0.974; S2 n = 46, r = 0.956). S2 loses 2 dates in each decomposed row: the Sep–Nov 2021 dates fall in a seasonal year with no dry season yet, so they get NaN where the old method extrapolated. The MODIS woody correlation with NSRS_2 rises only because the woody series now varies from year to year, so it has something to correlate; it is not evidence that the decomposition got more accurate. S2 woody stays near zero (−0.001). The note under Table 4 (the components are defined differently from the NSRS layers) still applies.

## How the approach changed while building this

1. **Minimum over the wet season only.** The first version searched every non-dry-season month (September to May) for the abrupt-loss minimum. That fired almost every year, mostly on September values (the dry-season tail, before green-up). The paper defines the wet season as October–April, so the search now uses `wet_months = (10, ..., 4)`. Taking the minimum over the whole seasonal year would be wrong for a different reason: it contains the dry-season values, so it is always below their mean.
2. **S2 numbers re-measured.** The first comparison used the older `S2.csv` from `s2_adopted_run`. The numbers above come from the full pipeline run on the current file (S2 woody n 43 → 41 became 46 → 44), and the old method was recomputed on the same data.
3. **Fallback tolerance rejected.** The min rule still fires in most MODIS years (see below). A tolerance would depart from the paper, so none was added.

## Things to know

- The min rule would fire in 4 of 5 MODIS seasonal years (and 1 of 3 for S2). In 2019 the minimum (0.393, Oct 2018) is 0.05 below the Jun–Aug mean. With a smoothed series and an evergreen site, ordinary autumn dips trigger a rule meant for fire or clearing. In v19 it was applied as written; since Nov 2026 it is off by default (`wet_min_rule=False`) and only reported (`wet_min_below_mean`).
- In v19 the figures showed each woody step as a short ramp between adjacent satellite dates. Since Nov 2026 the woody series is itself interpolated between dry seasons, so there are no steps or ramps; with `--woody-interp step` the ramps return.
- NDVI_W includes evergreen understory and soil (NSRS_1 Jun–Aug mean is about 0.48, close to the canopy sensor's 0.54), as at Mt. Carmel in the paper.

## Manuscript text to revisit (v17)

The abstract sentence "A linear regression through annual dry-season (June–August) mean NDVI defined the woody baseline", the corresponding methods text, Table 4, and the "stable woody baseline (NDVI ≈ 0.45)" claim. Per-year NDVI_W now ranges 0.39–0.48, so "stable" should be re-checked against `RH_NDVI_*_helman_annual.csv`.
