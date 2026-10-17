# Manuscript v12 vs regenerated outputs

Compared `archive/Derhi_WoodyHerbaceous_FINAL_v12_TRACKED NL.docx` (deletions stripped) against `run_rh_ndvi.py` outputs in `auto` mode (factor 1.364) and with `--nsrs3-factor 1.4`.

**Decision (author):** align the research documents to the data-derived factor (1.36). The package derives the factor from the data and never hardcodes it.

## Matches under both factors

- **Table 2:** optimal factor 1.36, 1.4 as the comparison, RMSE 0.030 vs 0.033 at 1.4, R² 0.957, n = 296. Matches `auto` exactly.
- **Table 3:** all SoS, PoS and EoS dates and DOYs. The rows the manuscript omits (MODIS 2018, S2 2019, NSRS_x 2022, NSRS_2) are the degenerate seasons the marker filter skips. The Section 2.5 explanation for NSRS_2 (PoS→EoS gap of 3 days in 2020, SoS = PoS in 2022) matches the data.
- **Table 4:** woody and herbaceous rows, including n (86, 67, 18, 16, 11) and r (0.05, -0.48). "Woody ≈ 0.40 / 0.44" and "herbaceous peak ≈ 0.28 / 0.37" are right.

## NSRS_3 factor inconsistency

A fixed-1.4 run reproduces the manuscript's NSRS_3 numbers exactly, so Tables 3 and 4 were computed with ×1.4, while Table 2, Section 2.2.2, Fig S3 and the conclusions say ×1.36. Aligning to 1.36 changes:

| Item | Manuscript | At 1.364 |
|---|---|---|
| Table 3 NSRS_3 peak, 2020 | 0.76 | 0.75 |
| Table 3 NSRS_3 peak, 2021 | 0.74 | 0.72 |
| Table 4 MODIS full signal: MAE / RMSE / bias | 0.036 / 0.042 / -0.024 | 0.026 / 0.033 / -0.008 |
| Table 4 S2 full signal: MAE / RMSE / bias | 0.054 / 0.064 / +0.042 | 0.065 / 0.075 / +0.059 |

Correlations are unchanged. Section 3.2 quotes the MODIS and S2 MAE and RMSE, so those sentences need the same update.

## Smaller manuscript inconsistencies

- Section 3.1 gives MODIS PoS as DOY 40–64 and EoS 152–199; the data give 40–58 and 158–199 (64 and 152 belong to NSRS_3 and S2). Conclusion 3 says EoS 152–180, the abstract 158–180.
- MODIS dry-season minima are 0.390, 0.373, 0.374 vs the text's 0.39, 0.38, 0.38; the abstract says 0.38–0.39, Section 2.4.2 says 0.37–0.40.
- NSRS_1 dry-season minimum is 0.275 vs about 0.30 in the Fig S1 caption.
- NSRS gap is "April–October 2020" in Fig 7 and "May–October 2020" in Fig S1.
- Section 2.5 and the Fig 9–11 captions describe vertical SoS/PoS/EoS lines; the code draws points.
- Table 3's caption and Section 2.5 name Phenolopy; the code is a native Savitzky–Golay implementation.
- Section 2.4.0 gives the repo as `omrid/Lensky-py-lab` with `src/spectral_analysis/` modules and a `requirements.txt`. The actual repo is `omriderhi/lensky-py-lab`, layout `src/lensky_py_lab/`, and `requirements.txt` was removed.

## Not checked

Figures were not diffed; only CSV outputs and the tables/text were compared.

---

## Update: after the outlier-filter fix (supersedes the 1.364 figures above)

The 1.364 numbers above were computed with the old filter, which deleted ordinary NSRS data (see `v12-review-fixes.md`, change 9). With the sliding-window filter, from `data/results_sliding_window/` (outputs of `run_rh_ndvi.py`, default settings):

- **Table 2 / Fig 5 / Fig S3:** optimal factor **1.384** (not 1.36), RMSE raw 0.159, corrected 0.0405, 0.0409 at ×1.4, R² 0.899, n = 470 (not 296). The statement that ×1.4 is a worse fit now holds only marginally.
- **Table 3 NSRS rows** (SoS / PoS / EoS, peak NDVI after ×1.384):

| Sensor | Year | SoS | PoS | EoS | Peak |
|---|---|---|---|---|---|
| NSRS_1 | 2020 | 28 Dec 2019 | 29 Feb 2020 | not reached | 0.775 |
| NSRS_1 | 2021 | 28 Nov 2020 | 15 Feb 2021 | 19 Jul 2021 | 0.808 |
| NSRS_3 | 2020 | 6 Jan 2020 | 4 Mar 2020 | not reached | 0.757 |
| NSRS_3 | 2021 | 10 Nov 2020 | 16 Feb 2021 | 30 Jun 2021 | 0.729 |

  The 2020 EoS values were record ends (24 Apr), not senescence dates, so the text should say the 2020 season is truncated. NSRS_2 is not listed (excluded from Table 3); its 2020 PoS to EoS gap explanation in Section 2.5 needs rechecking, since 2020 EoS is now "not reached".
- **Section 3.1 EoS ranges and Table 4:** NSRS_3 and the satellite series changed, so the MODIS, S2 (and new L8) full-signal MAE / RMSE / bias, the woody and herbaceous rows, and Section 3.2 quotes must be recomputed. The satellite series use the same filter with untuned settings (MODIS peaks fall by 0.03 to 0.11, S2 2019 EoS moves 79 days), so **do not copy satellite numbers until `satellite-data-cleaning-audit.md` is done**.
- **Section 2.4.1:** the sliding-window sentence is now true as written. Add the settings: centred 7-observation running median, threshold 3 × 1.4826 × MAD (31-observation window) with a 0.02 NDVI floor.
- **Figs S1–S3:** regenerate; the clean panel is now continuous and the LOWESS curve reaches the last observation.
