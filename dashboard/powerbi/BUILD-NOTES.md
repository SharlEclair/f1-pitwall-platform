# Power BI report: build notes

What is published, what was checked in Power BI Desktop, and where the report departs from the
guide. Numbers here come from the generated CSVs, not from the report.

## What is here

| Path | What it is |
|---|---|
| `f1-pitwall/` | The report as a Power BI project: PBIR pages plus a TMDL model. Open `f1-pitwall/f1-pitwall.pbip`. |
| `f1-pitwall.pdf` | Seven page export of the finished report. |
| `screenshots/page-1.png` … `page-7.png` | One image per page, rendered from that export at 2x. |
| `BUILD-GUIDE.md` | How the report is generated, how to point it at the data, how to check a build. |
| `build_report.py` | The generator: model, theme and every page. |

The project holds 17 tables, 43 measures, 8 relationships, 7 pages and 87 visuals. `DataFolder` is the
placeholder `C:\data\f1-pitwall`, so no local path is published.

## Verified in Desktop

The project opened without errors, refreshed, and every page rendered. Values read off the exported
pages, on the All-seasons view:

| Page | Check | Result |
|---|---|---|
| Overview | MEDIUM slope, green pit loss, undercut rate, LightGBM minus linear | +0.045 s/lap, 23.1 s, 44.8%, -0.150 s |
| Tyres | HARD / MEDIUM / SOFT slope, race fits | +0.028 / +0.045 / +0.053, captions 65 / 79 / 50 |
| Pit stops | GREEN / SC / VSC, per-season SC | 23.1 / 2.9 / 20.9 s; SC 10.7 (2024), 4.2 (2025), -3.9 (2023); both unstable ranges labelled |
| Undercut | rate, interval, decided, attempts, matrix | 44.8%, 35% to 54%, 163 decided, 164 attempts in 49 races, matrix filled |
| Model | mean diff, interval, races better, season out | -0.150 s, -0.265 to -0.047 s, 47 of 66, verdict present |
| Data quality | quarantined, flagged, rules | 57, 2,229, 23 available |
| Limits | six cards | no overflow |

The season dropdown filters Tyres, Pit stops and Data quality together, and is absent from Overview,
Undercut, Model and Limits as intended.

## Where the report departs from the guide

**The laps-treatment slicer was removed from the Undercut page.** It rendered its raw field name as a
title and its dropdown clipped inside the 66 px slot. The page now shows the default treatment, which
is "All", so the numbers are unchanged.

**Data labels are off on two charts.** On Tyres, the 2023 per-season slopes are 0.045, 0.046 and
0.045, so three labels landed on the same pixel row and overlapped. The values remain in the tooltip
and in the three KPI cards. On Undercut, the five response-window series have similar collisions at
gap 1 s, and the sensitivity matrix beside the chart carries every number.

**Axis and legend titles are hidden on four charts.** They were rendering as raw field names
(`gap_threshold_s`, `response_window_laps`, `rule_code`, `outcome`, `track_status`, `compound`,
`season`). Units and meaning moved into the panel titles, for example "Success rate against the
largest starting gap allowed (s)".

**The verdict panel on Model lost its border.** The label and the two text cards overlapped when the
label shared a bordered text box, so the label is now its own element and the panel border is gone.
The page reads as a heading with two statements.

**"Rules available" shows 23, not 11.** `dim_rule` holds 23 coded rules; 11 of them fire on this data
and the bar chart shows those. Both numbers are real; the card states availability, which is what the
guide asks for.

## Known residuals

- Table headers show source column names (`mae_b1`, `mae_gbm`, `n_attempts`, `median_pit_loss_s`).
  Renaming them means renaming model columns, which would touch every measure and visual; left as is.
- The season dropdown is labelled "season" by the field name.
- The by-race table on Model lists 66 races and scrolls; it does not overflow its panel.
- The "What to take from this" panel on Overview is taller than its text.

## The .pbix

Power BI Desktop 2.159 will not save this report to a `.pbix`. `File > Save as` reports
`'<path>' isn't a valid file path`, and it did so for four combinations: the project folder and an
outside folder, `.pbix` and `.pbit`, a full path typed into the name box and a bare filename after
navigating the dialog to an empty folder. Since a template export fails the same way, the path and the
extension are not the cause; something in the report definition is. The likely candidates are the
custom theme registered from `StaticResources/RegisteredResources` and the `scopeId` data point
selectors used for series colours, but neither has been isolated.

The PBIP project, the PDF and the per page PNGs are the published artefacts. If a `.pbix` is required
later, the next step is a bisect: rebuild with `PBI_NO_THEME=1`, try the save, then drop the
selectors.
