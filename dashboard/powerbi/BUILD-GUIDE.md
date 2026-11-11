# Power BI report: build guide

A seven page report over the same aggregated marts the Streamlit app uses. It reads only the CSVs in
`data/`, so it has no Snowflake or AWS connection and keeps working after the trial ends. The theme is
dark: page background `#0B0D12`, panels `#151922` with a `#262B36` border, text `#E8EAED`, one accent
red `#E10600`. Pages are a fixed 1280x720.

| Page | What it answers |
|---|---|
| Overview | The four headline numbers, each with how far to trust it |
| Tyres | Slope per compound, per season, and per race fit |
| Pit stops | Median pit loss by track status, and why SC and VSC are unstable |
| Undercut | The base rate under one stated definition, with a sensitivity matrix |
| Model | LightGBM against two baselines, and a whole-season hold-out |
| Data quality | Rows quarantined and flagged, per rule and per season |
| Limits | What each number rests on, and what it does not tell you |

## Build it

From the repository root, in PowerShell:

```powershell
.\.venv\Scripts\python.exe scripts\make_powerbi_inputs.py
.\.venv\Scripts\python.exe dashboard\powerbi\build_report.py
```

The first script writes the 17 input CSVs. The second writes `dashboard\powerbi\f1-pitwall\`, a PBIP
project: `f1-pitwall.pbip`, the report pages as PBIR JSON, and the semantic model as TMDL.

Open `dashboard\powerbi\f1-pitwall\f1-pitwall.pbip` in Power BI Desktop and click **Refresh**. A PBIP
project carries no data until it is refreshed, and a fresh open usually shows two banners, one for
calculated columns and one for data. Clear both.

## Point it at the data

`DataFolder` is a text parameter. The committed project sets it to the placeholder
`C:\data\f1-pitwall`, so nothing machine specific is published. Two ways to make a copy that refreshes:

- Rebuild with the real path: set `$env:PBI_DATA_FOLDER` to the absolute path of
  `dashboard\powerbi\data`, optionally `$env:PBI_OUT` to write the project somewhere outside the repo.
- Or open the committed project and edit the parameter in Desktop (Home, Transform data, Edit
  parameters). Do not save that change back into the repository.

## What the generator controls

`build_report.py` is the source of truth. Do not edit the generated `f1-pitwall\` folder by hand: the
next run overwrites it.

- `TABLES` and `MEASURES` define the model: 17 tables, 43 measures, 8 relationships.
- `chrome()` draws the header, page navigator, footer and the synced season slicer on every page.
- `build_pages()` lays out the seven pages.
- `theme()` defines the dark theme, registered as a custom theme so it applies on open.

Three environment variables help while iterating: `PBI_OUT` (output folder), `PBI_DATA_FOLDER` (data
path baked into the copy) and `PBI_NO_THEME=1` (build without the registered theme, to isolate a
rendering problem).

## Checking a build

Export the pages and read them rather than trusting the canvas:

1. `File > Export > Export to PDF`, then rasterise at 2x, or compare against
   `screenshots/page-1.png` to `page-7.png`.
2. Check the numbers against the tables in `BUILD-NOTES.md`. Those come from the CSVs, not from the
   report.
3. Watch for text that clips or grows a scrollbar. A text box needs roughly 1.7x its font size in
   height, and a scrollbar baked into an exported PDF means a box is too short.

## Saving a .pbix

Power BI Desktop will not write this report to a `.pbix`. `File > Save as` fails with
`'<path>' isn't a valid file path` for `.pbix` and for `.pbit`, in a clean folder and with a bare
filename. The cause is in the report definition rather than the path or the dialog. The PBIP project,
the PDF export and the per page PNGs are the published artefacts.
