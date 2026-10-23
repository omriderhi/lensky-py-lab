# Aligning the woody/herbaceous decomposition with Helman et al. (2015)

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

- The min rule fires in 4 of 5 MODIS seasonal years (and 1 of 3 for S2). In 2019 the minimum (0.393, Oct 2018) is 0.05 below the Jun–Aug mean. With a smoothed series and an evergreen site, ordinary autumn dips trigger a rule meant for fire or clearing, which lowers NDVI_W. This is the paper's rule applied as written. A tolerance would be a deviation from the paper, so none was added.
- Figures show the woody step as a short ramp between adjacent satellite dates (the plotting layer interpolates linearly).
- NDVI_W includes evergreen understory and soil (NSRS_1 Jun–Aug mean is about 0.48, close to the canopy sensor's 0.54), as at Mt. Carmel in the paper.

## Manuscript text to revisit (v17)

The abstract sentence "A linear regression through annual dry-season (June–August) mean NDVI defined the woody baseline", the corresponding methods text, Table 4, and the "stable woody baseline (NDVI ≈ 0.45)" claim. Per-year NDVI_W now ranges 0.39–0.48, so "stable" should be re-checked against `RH_NDVI_*_helman_annual.csv`.
