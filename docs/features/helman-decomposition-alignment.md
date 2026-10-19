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

## Effect on the adopted run (`data/s2_adopted_run`)

Per seasonal year (`helman_annual_table`):

| Source | Seasonal year | NDVI_W | NDVI_H | min rule used |
|---|---|---|---|---|
| MODIS | 2018 / 2019 / 2020 / 2021 / 2022 | 0.457 / 0.393 / 0.448 / 0.428 / 0.422 | 0.143 / 0.240 / 0.186 / 0.227 / 0.180 | no / yes / yes / yes / yes |
| S2 | 2019 / 2020 / 2021 | 0.482 / 0.454 / 0.424 | 0.261 / 0.251 / 0.379 | no / no / no |

Table 4 (old `linear_trend` → new), MODIS then S2:

| Comparison | n | r | bias |
|---|---|---|---|
| MODIS woody vs NSRS_2 | 357 → 357 | 0.045 → 0.337 | −0.120 → −0.140 |
| MODIS herbaceous vs NSRS_1 | 342 → 342 | 0.863 → 0.884 | −0.449 → −0.429 |
| S2 woody vs NSRS_2 | 43 → 41 | −0.189 → 0.043 | −0.136 → −0.152 |
| S2 herbaceous vs NSRS_1 | 41 → 39 | 0.890 → 0.858 | −0.385 → −0.377 |

Full-signal rows are unchanged. S2 loses 4 dates (Sep–Nov 2021, a season with no dry season yet). The woody correlation with NSRS_2 rises for MODIS only because the woody series now varies from year to year, so it has something to correlate; it is not evidence that the decomposition got more accurate. The note under Table 4 (components are differently defined) still applies.

## Things to know

- The min rule fires in 4 of 5 MODIS seasonal years. In 2019 the minimum (0.393, Oct 2018) is 0.05 below the Jun–Aug mean. With a smoothed series and an evergreen site, ordinary autumn dips trigger a rule meant for fire or clearing, which lowers NDVI_W. This is the paper's rule applied as written. A tolerance would be a deviation from the paper, so none was added.
- Figures show the woody step as a short ramp between adjacent satellite dates (the plotting layer interpolates linearly).
- NDVI_W includes evergreen understory and soil (NSRS_1 Jun–Aug mean is about 0.48, close to the canopy sensor's 0.54), as at Mt. Carmel in the paper.

## Manuscript text to revisit (v17)

The abstract sentence "A linear regression through annual dry-season (June–August) mean NDVI defined the woody baseline", the corresponding methods text, Table 4, and the "stable woody baseline (NDVI ≈ 0.45)" claim. Per-year NDVI_W now ranges 0.39–0.48, so "stable" should be re-checked against `RH_NDVI_*_helman_annual.csv`.
