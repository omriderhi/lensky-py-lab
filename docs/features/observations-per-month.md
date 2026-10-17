# Feature: observations per sensor per month (Table S1, reviewer comment [29])

**For:** the coding agent working in `lensky-py-lab`. **Base:** `c239347` (branch with PRs #11–#13).
**Reviewer ask (Noam Levin, v12 comment [29], on the Figure 7 caption):** "Summarize in a supplementary table how many data images/points for each sensor in each month."
**Author decisions (17 Oct 2026):** one count per cell, NSRS window only, reusable code that runs with every pipeline run.
**After this lands:** the paper agent inserts the CSV as Table S1 in v15 and cites it from §2.4.1 and §3.3. This feature only produces the table.

---

## 1. What the table is

| Item | Definition |
|---|---|
| Cell value | Number of **distinct calendar dates** with a **kept** observation for that source in that month. Kept = non-null `NDVI clean` (after the extreme-value filter and the outlier filter, i.e. what LOWESS is fitted to). |
| Rows | Calendar months of the NSRS reference window, oldest first. With the current data: **Oct 2019 to Nov 2021 = 26 rows**. |
| Columns | `NSRS_1`, `NSRS_2`, `NSRS_3`, `MODIS`, `S2`, `L8` in that order. |
| NSRS replacement files | `NSRS_x` and `NSRS_x_B` count as **one** sensor: a date counts once if either file has a kept value on it (same rule as `_merge_processed_for_plot` in `scripts/run_rh_ndvi.py`: primary first, `_B` only on dates the primary lacks). |
| L8 | Included even though it is excluded from the analysis; its column header is `L8 (excluded)` when `source_eligibility.csv` says `in_analysis == False`. Same-date scenes are already averaged on load (`average_same_date`), so each date counts once. |
| Months with no data | `0`, not blank (e.g. NSRS May–Sep 2020, the collection gap). |
| Summary rows (after the month rows) | `Total` (sum over the window) and one row per complete peak season inside the window, labelled `Dec 2019 – Mar 2020` and `Dec 2020 – Mar 2021` (sum of Dec–Mar). |

Not in the table: raw counts before filtering, months outside the NSRS window, VENuS/PLANET, IMS.

## 2. Window

Use the existing `pipeline.eligibility.reference_window(nsrs_sources)` (first and last timestamp at which any NSRS source has a LOWESS value). Expand it to whole calendar months: every month from the month of the first day to the month of the last day, inclusive. Count only dates inside the window itself (not the whole first/last month), so the `Total` row agrees with the eligibility counts.

## 3. Dates: use the `DATE` column, not the timestamp

`io.csv_loader.load_source_csv` builds the index with `datetime.timestamp(dt)` on a **naive** datetime, so the unix timestamp depends on the machine's timezone. On the author's Windows machine (Asia/Jerusalem) a date's timestamp is 21:00 or 22:00 UTC of the **previous** day, and `pd.to_datetime(ts, unit="s")` therefore returns the previous calendar date (this is the "may be one day off" note in `satellite-data-products.md`).

- The new code must take the calendar date from the `DATE` column of `processed` (`.dt.normalize()`), and the month from that.
- Use timestamps only to apply the window bounds.
- Add a test that would fail if month assignment came from the UTC timestamp: an observation on the 1st of a month must count in that month (see §6).

Related issue found while writing this spec (do **not** fix in this feature, report it): `check_source_eligibility` derives months and the Dec–Mar season boundaries from `pd.to_datetime(index, unit="s")`, so on the author's machine every date is shifted one day back. Distinct-date totals are unaffected; month coverage and peak-season counts can move by one observation at month or season edges. Open a separate issue: "eligibility months/seasons should come from DATE, not UTC timestamp", and say in the PR whether any RH verdict or number would change (MODIS 523 / 1.00 / 59, S2 64 / 0.885 / 8, L8 42 / 0.769 / 2).

## 4. Code

### 4.1 New module `src/lensky_py_lab/pipeline/observation_counts.py`

```python
def observations_per_month(
    sources: Dict[str, "DataSource"],          # processed sources, keys as in run_rh_ndvi (NSRS_1, NSRS_1_B, ..., MODIS, S2, L8)
    window: Tuple[int, int],                    # from reference_window(nsrs_sources)
    order: Sequence[str] = ("NSRS_1", "NSRS_2", "NSRS_3", "MODIS", "S2", "L8"),
    excluded: Iterable[str] = (),               # sources to label "(excluded)"
    field: str = NDVI_CLEAN_FIELD,              # kept observations; NDVI_FILTERED_FIELD gives the pre-outlier count
    peak_season: Tuple[int, int] = (12, 3),     # Dec..Mar, same as eligibility rule 3
) -> pd.DataFrame:
    """Wide table: one row per calendar month of the window plus Total and peak-season rows,
    one column per source (``_B`` replacement files merged into their primary), integer counts."""
```

- Merge `X` and `X_B` inside the function (a date counts once). Do not import from `scripts/`. If a helper is needed in both places, move `_merge_processed_for_plot` into the package (e.g. `pipeline/processor.py`) and have the script import it, as a pure move with no behaviour change.
- Sources named in `order` but missing from `sources` are skipped with a `warnings.warn`, not an error.
- Index: a string label column `month` (`"2019-10"`, …, then `"Total"`, `"Dec 2019 – Mar 2020"`, …). Values: `int`.
- The `field` parameter exists so tests (and anyone checking) can reproduce the eligibility date counts with `NDVI_FILTERED_FIELD`. The pipeline uses the default.
- Export it from `lensky_py_lab.pipeline.__init__`.

### 4.2 Pipeline step in `scripts/run_rh_ndvi.py`

- Right after the eligibility block (`elig.to_csv(out_dir / "source_eligibility.csv")`, about line 276), call `observations_per_month` on **all** processed sources (before excluded satellites are dropped from `sat_sources`), with `excluded=excluded`.
- Write `out_dir / "observations_per_month.csv"` (`index=False`), and print one line: `→ observations_per_month.csv (26 months × 6 sources)`.
- No change to any other output. The run must still produce byte-identical `RH_NDVI_final_result.csv`, `phenology_markers.csv`, `source_eligibility.csv` and `calibration_statistics.csv`.

## 5. Acceptance checks (run on `data/research_results/RH_NDVI`, default settings)

1. Shape: 26 month rows + 1 `Total` + 2 peak-season rows; 6 source columns; L8's header ends in `(excluded)`.
2. Months Oct 2019 to Nov 2021 inclusive, no gaps in the month list.
3. NSRS months May–Sep 2020 are 0 for all three sensors; no satellite column is 0 in every month.
4. **Cross-check with eligibility** (call with `field=NDVI_FILTERED_FIELD`): the `Total` row equals `valid_dates_in_window` in `source_eligibility.csv` for MODIS, S2 and L8 (523, 64, 42). The peak-season rows' minimum equals `min_dates_in_peak_season` (59, 8, 2), or differs by at most one per season because of §3. Report any difference and its cause in the PR, rather than "fixing" it to match.
5. With the default `field`, every cell is ≤ the corresponding `NDVI_FILTERED_FIELD` cell.
6. The run log's kept counts are for the whole record (MODIS 1,056, S2 90, L8 59), so the window `Total` must be ≤ those.
7. Full test suite passes (`python -m pytest -q`, currently 88 tests + new ones).

Put the numbers from checks 1–6 in the PR description (a short table) so the paper agent can quote them.

## 6. Tests (`tests/test_observation_counts.py`)

Build synthetic `processed` frames, as `tests/test_eligibility.py` does, but with a real `DATE` column:

- **Month assignment from DATE:** one observation dated 2020-03-01 whose index timestamp is 2020-02-29 21:00 UTC counts in `2020-03`, not `2020-02`.
- **`_B` merge:** primary and `_B` share one date and each has one unique date → 3, not 4.
- **Distinct dates:** two rows on the same date → 1.
- **Null handling:** a row with null `NDVI clean` but non-null `NDVI filtered` counts with `field=NDVI_FILTERED_FIELD` only.
- **Window:** dates outside the window are not counted; months of the window with no data are 0.
- **Summary rows:** `Total` = sum of month rows; Dec–Mar row = sum of Dec, Jan, Feb, Mar of that season; a season not wholly inside the window gets no row.
- **Excluded label:** `excluded=["L8"]` gives column `L8 (excluded)`.
- **Missing source:** a name in `order` that is absent raises a warning and is skipped.

## 7. Docs to update in the same PR

- `README.md`: one line under outputs listing `observations_per_month.csv` and what a cell means.
- `CLAUDE.md`: add the module to the architecture tree.
- `docs/features/satellite-data-products.md` §6/§7 and `paper-rewrite-brief.md` §6: note that Table S1 now comes from `observations_per_month.csv`.

## 8. Out of scope

- Inserting the table into the manuscript (paper agent, after this PR).
- Changing eligibility (report the §3 issue only).
- A figure version of the table (Figure 7 already shows availability).
- Any change to filters, LOWESS, phenology, calibration or figure styling.
