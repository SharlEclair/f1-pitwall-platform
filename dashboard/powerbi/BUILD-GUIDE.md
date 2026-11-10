# Power BI report: build guide

A five-page report with the same content as the Streamlit dashboard (`dashboard/app.py`). It uses
only the small aggregated tables in `data/` (regenerate them with
`python scripts/make_powerbi_inputs.py`); there is no row-level lap data and no Snowflake connection,
so the file keeps working after the Snowflake trial ends.

## 1. Load the data

Power BI Desktop (Windows, free): **Get data > Text/CSV**, one import per file in `data/`:

| Table | Grain | Key columns |
|---|---|---|
| `mart_tyre_degradation` | race x compound | circuit_short_name, compound, n_clean_laps, n_stints, slope_s_per_lap, slope_uncorrected, slope_pooled_s_per_lap, censored_stint_share |
| `mart_pit_loss` | race x track status | circuit_short_name, track_status, n_stops, n_stops_with_loss, median_lane_duration_s, median_pit_loss_s |
| `mart_dq_health` | race x rule x outcome | circuit_short_name, rule_code, outcome, n_rows |
| `model_summary` | method | mean_mae_s, ci_low_s, ci_high_s, all_laps_mae_s |
| `model_paired_differences` | comparison | mean_diff_s, ci_low_s, ci_high_s, races_better, n_races |
| `model_by_race`, `model_by_compound`, `model_by_horizon`, `model_effects` | breakdowns | see the CSV headers |

No relationships are needed; the tables are independent. Set number columns to Decimal and keep
`session_key` as text.

Keep the local path out of the saved file: before loading, create a text parameter `DataFolder`
(Home > Transform data > Manage parameters) and build each source path from it. Before saving the
final `.pbix`, set `DataFolder` to a placeholder such as `C:\data\f1-pitwall` (the embedded data is
unaffected; only refresh would need the real folder).

Apply the theme: **View > Themes > Browse for themes** and choose `f1-theme.json`.

## 2. Measures (DAX)

```
Slope HARD   = CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "HARD" )
Slope MEDIUM = CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "MEDIUM" )
Slope SOFT   = CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "SOFT" )
Races With Slope = COUNTROWS ( FILTER ( mart_tyre_degradation, NOT ISBLANK ( mart_tyre_degradation[slope_s_per_lap] ) ) )

Pit Loss GREEN = CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "GREEN" )
Pit Loss SC    = CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "SC" )
Pit Loss VSC   = CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "VSC" )
Stops With Loss = SUM ( mart_pit_loss[n_stops_with_loss] )
Lowest Race  = MIN ( mart_pit_loss[median_pit_loss_s] )
Highest Race = MAX ( mart_pit_loss[median_pit_loss_s] )

Quarantined Rows = CALCULATE ( SUM ( mart_dq_health[n_rows] ), mart_dq_health[outcome] = "quarantined" )
Flagged Rows     = CALCULATE ( SUM ( mart_dq_health[n_rows] ), mart_dq_health[outcome] = "flagged" )

Model Verdict =
VAR lo = MAX ( model_paired_differences[ci_low_s] )
VAR hi = MAX ( model_paired_differences[ci_high_s] )
RETURN IF ( lo <= 0 && hi >= 0,
    "No detectable difference between LightGBM and the linear baseline: the 95% interval includes zero.",
    "The 95% interval excludes zero: see the numbers." )
```

For the model verdict card, filter `model_paired_differences[comparison]` to "LightGBM minus B1".

## 3. Pages

1. **Tyre degradation.** Cards: Slope HARD, MEDIUM, SOFT (format `+0.000" s/lap"`) with
   Races With Slope in a tooltip. Scatter: X = circuit_short_name (sorted by slope, descending),
   Y = slope_s_per_lap (do not summarise), legend = compound, size = n_clean_laps, tooltip =
   slope_uncorrected and slope_pooled_s_per_lap. Compound slicer. Text box: *The fuel correction is an
   assumption (0.04 s per lap); the corrected slope is largely the uncorrected slope plus that
   assumption. For MEDIUM and HARD the lap-time model's tyre-age intervals include zero. Use these
   slopes to compare races and compounds, not as precise rates.*
2. **Pit-stop cost.** Cards: Pit Loss GREEN / SC / VSC (`0.0" s"`), each with Stops With Loss and the
   Lowest/Highest Race range in a tooltip. Scatter: X = track_status, Y = median_pit_loss_s,
   size = n_stops_with_loss, tooltip = circuit_short_name. Text box: *Pit loss is an estimate (in-lap
   plus out-lap minus two reference laps, only when both laps ran under the same track status; stops
   over 60 s excluded). Safety Car and VSC rest on few races; check the stop counts.*
3. **Lap-time model.** Card: mean_diff_s for "LightGBM minus B1" (`+0.000" s"`) with the Model Verdict
   text beneath. Clustered bar: Y = method, X = mean_mae_s, with error bars from ci_low_s / ci_high_s
   (Analytics pane). Tables: model_by_compound, model_by_horizon, model_by_race (sort by mae_gbm,
   descending), model_effects. Caption: *23 held-out races; each method sees only a driver's first 5
   clean laps of the held-out race.*
4. **Data quality.** Stacked bar: Y = rule_code, X = sum of n_rows, legend = outcome
   (quarantined red, flagged amber). Cards: Quarantined Rows, Flagged Rows.
5. **Limits.** Text only: one season; every circuit appears once; fuel effect assumed; pit loss
   estimated; the undercut base rate is not answered; track status from message timestamps; unofficial
   OpenF1 data, F1 marks belong to Formula One Licensing B.V., not affiliated.

## 4. Values the finished report must show

| Item | Expected |
|---|---|
| Slope HARD / MEDIUM / SOFT | +0.032 / +0.053 / +0.064 s/lap (23 / 28 / 16 races) |
| Pit Loss GREEN / SC / VSC | 23.2 / 10.7 / 14.9 s (619 / 108 / 24 stops) |
| Mean MAE B0 / B1 / LightGBM | 1.498 / 1.066 / 1.008 s |
| LightGBM minus B1 | -0.058 s, interval -0.166 to +0.043 |
| Quarantined rows (all rules) | 34 (laps 18, stints 16) |

## 5. Save and share

Save as `dashboard/powerbi/f1-pitwall.pbix`. Export one PNG per page to
`dashboard/powerbi/screenshots/` (`page-1.png` to `page-5.png`). Before committing the `.pbix`, check
it for author or sign-in details and for the local data path (File > Info and Options); screenshots
alone are enough if you would rather not publish the file. Publishing to the Power BI service needs a
licence and is not required.
