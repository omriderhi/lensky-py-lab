# Raw Data Directory

Place input CSV files here before running any analysis scripts.

## Expected File Structure

```
data/raw/
├── RH/                          # Ramat Hanadiv site
│   ├── MODIS.csv
│   ├── S2.csv
│   ├── L8.csv
│   ├── VENuS.csv
│   ├── PLANET.csv
│   ├── NSRS_1.csv
│   ├── NSRS_2.csv
│   ├── NSRS_3.csv
│   └── NSRS_3_B.csv             # backup sensor (optional)
└── IMS/                         # Israeli Meteorological Service
    ├── RH_rainfall_1.csv
    └── RH_temp_1.csv
```

## CSV Format

All satellite and NSRS sensor files must have:

| Column | Format | Example |
|--------|--------|---------|
| `DATE` | `%b %d, %Y` or `%d/%m/%Y` | `Jan 15, 2020` or `15/01/2020` |
| `NDVI_RAW` | float, –1.0 to 1.0 | `0.4523` |

IMS files must have:

| Column | Format |
|--------|--------|
| `DATE` | same as above |
| `RAINFALL` | float, mm |
| `TEMP` | float, °C |

## Data Sources

Data was originally stored on Google Drive at:
`OMRI_RESEARCH_RESULTS/{site_name}/{source}.csv`

Export these files and place them here following the structure above.
