#!/usr/bin/env python3
"""Generate the F1 Pitwall Power BI project (PBIP: PBIR report + TMDL semantic model).

Usage (repo root):
    python scripts/make_powerbi_inputs.py          # refresh the CSVs in dashboard/powerbi/data
    python dashboard/powerbi/build_report.py       # write dashboard/powerbi/f1-pitwall/

The project reads the CSVs through a text parameter `DataFolder`. By default it is a placeholder
(`C:\\data\\f1-pitwall`); set PBI_DATA_FOLDER to the real folder when building a copy you want to
refresh locally, or change the parameter in Power BI Desktop (Home > Transform data > Edit
parameters). Single source of truth for layout, measures and theme: edit here and re-run.
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("PBI_OUT", HERE / "f1-pitwall"))
DATA_FOLDER = os.environ.get("PBI_DATA_FOLDER", r"C:\data\f1-pitwall")

NAME = "f1-pitwall"
BASE_THEME = "CY26SU10"
CUSTOM_THEME = "F1 Pitwall"
REGISTER_THEME = os.environ.get("PBI_NO_THEME") != "1"

PBIR = "https://developer.microsoft.com/json-schemas/fabric/item/report/definition"
SCHEMA_REPORT = f"{PBIR}/report/3.2.0/schema.json"
SCHEMA_PAGE = f"{PBIR}/page/2.1.0/schema.json"
SCHEMA_VISUAL = f"{PBIR}/visualContainer/2.7.0/schema.json"
SCHEMA_PAGES = f"{PBIR}/pagesMetadata/1.0.0/schema.json"
SCHEMA_VERSION = f"{PBIR}/versionMetadata/1.0.0/schema.json"
SCHEMA_PBIR = ("https://developer.microsoft.com/json-schemas/fabric/item/report/"
               "definitionProperties/2.0.0/schema.json")
SCHEMA_PBISM = ("https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/"
                "definitionProperties/1.0.0/schema.json")
SCHEMA_PBIP = ("https://developer.microsoft.com/json-schemas/fabric/pbip/"
               "pbipProperties/1.0.0/schema.json")
VERSIONS = {"visual": "2.7.0", "page": "2.1.0", "report": "3.2.0"}

# --------------------------------------------------------------------------- #
# palette (dark, one red accent)
# --------------------------------------------------------------------------- #
PAGE_BG = "#0B0D12"
PANEL = "#151922"
BORDER = "#262B36"
TEXT = "#E8EAED"
MUTED = "#9AA0A6"
ACCENT = "#E10600"
SOFT, MEDIUM, HARD = "#E8002D", "#FFD12E", "#EBEBEB"
GREEN, SC, VSC = "#3DDC97", "#FFD12E", "#4C9BE8"
B0, B1, GBM = "#6B7280", "#4C9BE8", "#E10600"
FLAGGED, QUARANTINED = "#FFD12E", "#E10600"

# --------------------------------------------------------------------------- #
# model
# --------------------------------------------------------------------------- #
TEXT_T, I64, DBL, DATE = "string", "int64", "double", "dateTime"
MTEXT, MI64, MDBL, MDATE = "type text", "Int64.Type", "type number", "type date"
T, I, D, DT = (TEXT_T, MTEXT), (I64, MI64), (DBL, MDBL), (DATE, MDATE)

TABLES: dict[str, list[tuple[str, tuple[str, str]]]] = {
    "dim_season": [("season", I)],
    "dim_race": [("session_key", T), ("season", I), ("circuit_short_name", T),
                 ("session_name", T), ("race_date", DT), ("race_label", T)],
    "dim_rule": [("rule_code", T), ("severity", T), ("entity", T), ("description", T)],
    "mart_tyre_degradation": [
        ("session_key", T), ("season", I), ("circuit_short_name", T), ("session_name", T),
        ("compound", T), ("n_clean_laps", I), ("n_stints", I), ("slope_s_per_lap", D),
        ("slope_uncorrected", D), ("slope_pooled_s_per_lap", D), ("censored_stint_share", D)],
    "mart_pit_loss": [
        ("session_key", T), ("season", I), ("circuit_short_name", T), ("track_status", T),
        ("n_stops", I), ("n_stops_with_loss", I), ("median_lane_duration_s", D),
        ("n_stops_with_stationary_time", I), ("median_stop_duration_s", D),
        ("median_pit_loss_s", D)],
    "mart_dq_health": [
        ("session_key", T), ("season", I), ("circuit_short_name", T), ("session_name", T),
        ("rule_code", T), ("outcome", T), ("n_rows", I)],
    "pit_loss_by_season": [("season", I), ("track_status", T), ("median_pit_loss_s", D),
                           ("stops", I), ("races", I)],
    "undercut_grid": [
        ("grid_id", I), ("gap_threshold_s", D), ("response_window_laps", I),
        ("exclude_neutralised", T), ("is_primary", T), ("season_scope", T), ("n_attempts", I),
        ("n_success", I), ("n_failure", I), ("n_inconclusive", I), ("n_sessions", I),
        ("n_decided", I), ("success_rate", D), ("wilson_low", D), ("wilson_high", D),
        ("treatment", T)],
    "undercut_by_season": [
        ("season_scope", T), ("n_attempts", I), ("n_success", I), ("n_failure", I),
        ("n_inconclusive", I), ("n_sessions", I), ("success_rate", D), ("wilson_low", D),
        ("wilson_high", D)],
    "undercut_primary": [("gap_threshold_s", D), ("response_window_laps", I), ("rate", D),
                         ("ci_low", D), ("ci_high", D), ("n_races", I)],
    "model_summary": [("method", T), ("mean_mae_s", D), ("ci_low_s", D), ("ci_high_s", D),
                      ("all_laps_mae_s", D)],
    "model_paired_differences": [("comparison", T), ("mean_diff_s", D), ("ci_low_s", D),
                                 ("ci_high_s", D), ("races_better", I), ("n_races", I)],
    "model_by_season_out": [("season", I), ("n_laps", I), ("mae_b0", D), ("mae_b1", D),
                            ("mae_gbm", D)],
    "model_by_race": [("session_key", T), ("season", I), ("circuit_short_name", T),
                      ("n_laps", I), ("mae_b0", D), ("mae_b1", D), ("mae_gbm", D)],
    "model_by_compound": [("compound", T), ("n", I), ("err_b0", D), ("err_b1", D),
                          ("err_gbm", D)],
    "model_by_horizon": [("horizon", T), ("n", I), ("err_b0", D), ("err_b1", D), ("err_gbm", D)],
    "model_effects": [("effect", T), ("estimate_s_per_lap", D), ("ci_low", D), ("ci_high", D),
                      ("assumed_fuel_effect_s_per_lap", D)],
}

HIDDEN = {("mart_tyre_degradation", "session_key"), ("mart_pit_loss", "session_key"),
          ("mart_dq_health", "session_key"), ("model_by_race", "session_key"),
          ("mart_tyre_degradation", "season"), ("mart_pit_loss", "season")}

RELATIONSHIPS = [
    ("rel_tyre_race", "mart_tyre_degradation.session_key", "dim_race.session_key"),
    ("rel_pit_race", "mart_pit_loss.session_key", "dim_race.session_key"),
    ("rel_dq_race", "mart_dq_health.session_key", "dim_race.session_key"),
    ("rel_modelrace_race", "model_by_race.session_key", "dim_race.session_key"),
    ("rel_race_season", "dim_race.season", "dim_season.season"),
    ("rel_pitseason_season", "pit_loss_by_season.season", "dim_season.season"),
    ("rel_modelseason_season", "model_by_season_out.season", "dim_season.season"),
    ("rel_dq_rule", "mart_dq_health.rule_code", "dim_rule.rule_code"),
]

PCT = "0.0%"
S1 = '0.0" s"'
S3 = '+0.000" s";-0.000" s"'
SLOPE = '+0.000" s/lap";-0.000" s/lap"'

# (table, name, dax, format, folder, description)
MEASURES = [
    # tyre degradation
    ("mart_tyre_degradation", "Slope HARD",
     'CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "HARD" )',
     SLOPE, "Tyre degradation", "Median within-stint slope, assumed 0.04 s/lap fuel effect"),
    ("mart_tyre_degradation", "Slope MEDIUM",
     'CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "MEDIUM" )',
     SLOPE, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Slope SOFT",
     'CALCULATE ( MEDIAN ( mart_tyre_degradation[slope_s_per_lap] ), mart_tyre_degradation[compound] = "SOFT" )',
     SLOPE, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Slope Median",
     "MEDIAN ( mart_tyre_degradation[slope_s_per_lap] )", SLOPE, "Tyre degradation",
     "Median slope in the current filter context"),
    ("mart_tyre_degradation", "Slope Uncorrected Median",
     "MEDIAN ( mart_tyre_degradation[slope_uncorrected] )", SLOPE, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Fits HARD",
     'CALCULATE ( COUNTROWS ( FILTER ( mart_tyre_degradation, NOT ISBLANK ( mart_tyre_degradation[slope_s_per_lap] ) ) ), mart_tyre_degradation[compound] = "HARD" )',
     "0", "Tyre degradation", ""),
    ("mart_tyre_degradation", "Fits MEDIUM",
     'CALCULATE ( COUNTROWS ( FILTER ( mart_tyre_degradation, NOT ISBLANK ( mart_tyre_degradation[slope_s_per_lap] ) ) ), mart_tyre_degradation[compound] = "MEDIUM" )',
     "0", "Tyre degradation", ""),
    ("mart_tyre_degradation", "Fits SOFT",
     'CALCULATE ( COUNTROWS ( FILTER ( mart_tyre_degradation, NOT ISBLANK ( mart_tyre_degradation[slope_s_per_lap] ) ) ), mart_tyre_degradation[compound] = "SOFT" )',
     "0", "Tyre degradation", ""),
    ("mart_tyre_degradation", "Slope HARD Caption",
     '"HARD, median of " & [Fits HARD] & " race fits"', None, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Slope MEDIUM Caption",
     '"MEDIUM, median of " & [Fits MEDIUM] & " race fits"', None, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Slope SOFT Caption",
     '"SOFT, median of " & [Fits SOFT] & " race fits"', None, "Tyre degradation", ""),
    ("mart_tyre_degradation", "Fit Slope",
     "SELECTEDVALUE ( mart_tyre_degradation[slope_s_per_lap] )", "+0.000;-0.000",
     "Plot helpers", "One race and compound per point"),
    ("mart_tyre_degradation", "Fit Clean Laps",
     "SUM ( mart_tyre_degradation[n_clean_laps] )", "#,0", "Plot helpers", ""),
    # pit loss
    ("mart_pit_loss", "Pit Loss",
     "MEDIAN ( mart_pit_loss[median_pit_loss_s] )", S1, "Pit stop",
     "Median of per-race median pit loss in the current context"),
    ("mart_pit_loss", "Pit Loss GREEN",
     'CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "GREEN" )',
     S1, "Pit stop", ""),
    ("mart_pit_loss", "Pit Loss SC",
     'CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "SC" )',
     S1, "Pit stop", ""),
    ("mart_pit_loss", "Pit Loss VSC",
     'CALCULATE ( MEDIAN ( mart_pit_loss[median_pit_loss_s] ), mart_pit_loss[track_status] = "VSC" )',
     S1, "Pit stop", ""),
    ("pit_loss_by_season", "Green Range Text",
     'VAR lo = CALCULATE ( MIN ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "GREEN", ALL ( dim_season ) ) '
     'VAR hi = CALCULATE ( MAX ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "GREEN", ALL ( dim_season ) ) '
     'RETURN "Stable across seasons: " & FORMAT ( lo, "0.0" ) & " to " & FORMAT ( hi, "0.0" ) & " s"',
     None, "Pit stop", ""),
    ("pit_loss_by_season", "SC Range Text",
     'VAR lo = CALCULATE ( MIN ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "SC", ALL ( dim_season ) ) '
     'VAR hi = CALCULATE ( MAX ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "SC", ALL ( dim_season ) ) '
     'RETURN "Unstable by season: " & FORMAT ( lo, "0.0" ) & " to " & FORMAT ( hi, "0.0" ) & " s"',
     None, "Pit stop", ""),
    ("pit_loss_by_season", "VSC Range Text",
     'VAR lo = CALCULATE ( MIN ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "VSC", ALL ( dim_season ) ) '
     'VAR hi = CALCULATE ( MAX ( pit_loss_by_season[median_pit_loss_s] ), pit_loss_by_season[track_status] = "VSC", ALL ( dim_season ) ) '
     'RETURN "Unstable by season: " & FORMAT ( lo, "0.0" ) & " to " & FORMAT ( hi, "0.0" ) & " s"',
     None, "Pit stop", ""),
    ("pit_loss_by_season", "Pit Loss Season",
     "AVERAGE ( pit_loss_by_season[median_pit_loss_s] )", S1, "Pit stop",
     "Median pit loss for one season and status"),
    ("pit_loss_by_season", "Stops Season Status",
     "SUM ( pit_loss_by_season[stops] )", "#,0", "Pit stop", ""),
    # undercut
    ("undercut_grid", "Undercut Rate",
     'CALCULATE ( DIVIDE ( SUM ( undercut_grid[n_success] ), SUM ( undercut_grid[n_decided] ) ), undercut_grid[season_scope] = "all" )',
     "0%", "Undercut", "Success rate in the current grid cell(s), pooled over seasons"),
    ("undercut_grid", "Undercut Decided",
     'CALCULATE ( SUM ( undercut_grid[n_decided] ), undercut_grid[season_scope] = "all" )',
     "#,0", "Undercut", ""),
    ("undercut_primary", "Primary Rate", "AVERAGE ( undercut_primary[rate] )", "0.0%",
     "Undercut", "Primary definition (gap <= 3 s, 3-lap window, no neutralised laps)"),
    ("undercut_primary", "Primary Interval Text",
     '"95% interval over races: " & FORMAT ( AVERAGE ( undercut_primary[ci_low] ), "0%" ) & " to " & FORMAT ( AVERAGE ( undercut_primary[ci_high] ), "0%" )',
     None, "Undercut", ""),
    ("undercut_by_season", "Primary Decided",
     'CALCULATE ( SUM ( undercut_by_season[n_success] ) + SUM ( undercut_by_season[n_failure] ), undercut_by_season[season_scope] = "all" )',
     "#,0", "Undercut", ""),
    ("undercut_by_season", "Primary Attempts Text",
     'VAR a = CALCULATE ( SUM ( undercut_by_season[n_attempts] ), undercut_by_season[season_scope] = "all" ) '
     'VAR r = CALCULATE ( SUM ( undercut_by_season[n_sessions] ), undercut_by_season[season_scope] = "all" ) '
     'RETURN a & " attempts in " & r & " races"',
     None, "Undercut", ""),
    # model
    ("model_summary", "Mean MAE", "AVERAGE ( model_summary[mean_mae_s] )", "0.000", "Model", ""),
    ("model_summary", "CI Low", "MIN ( model_summary[ci_low_s] )", "0.000", "Model", ""),
    ("model_summary", "CI High", "MAX ( model_summary[ci_high_s] )", "0.000", "Model", ""),
    ("model_paired_differences", "Mean Diff",
     'CALCULATE ( MIN ( model_paired_differences[mean_diff_s] ), model_paired_differences[comparison] = "LightGBM minus B1" )',
     S3, "Model", "LightGBM minus linear baseline, mean MAE difference across races"),
    ("model_paired_differences", "Diff Interval Text",
     'VAR lo = CALCULATE ( MIN ( model_paired_differences[ci_low_s] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'VAR hi = CALCULATE ( MAX ( model_paired_differences[ci_high_s] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'RETURN "95% interval " & FORMAT ( lo, "+0.000;-0.000" ) & " to " & FORMAT ( hi, "+0.000;-0.000" ) & " s"',
     None, "Model", ""),
    ("model_paired_differences", "Races Better Text",
     'VAR k = CALCULATE ( MIN ( model_paired_differences[races_better] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'VAR n = CALCULATE ( MIN ( model_paired_differences[n_races] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'RETURN "LightGBM better in " & k & " of " & n & " races"',
     None, "Model", ""),
    ("model_paired_differences", "Model Verdict",
     'VAR lo = CALCULATE ( MIN ( model_paired_differences[ci_low_s] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'VAR hi = CALCULATE ( MAX ( model_paired_differences[ci_high_s] ), model_paired_differences[comparison] = "LightGBM minus B1" ) '
     'RETURN SWITCH ( TRUE (), hi < 0, "LightGBM beats the linear baseline: the 95% interval excludes zero.", '
     'lo > 0, "The linear baseline beats LightGBM: the 95% interval excludes zero.", '
     '"No detectable difference: the 95% interval includes zero." )',
     None, "Model", "Verdict is computed from the interval, not typed"),
    ("model_by_season_out", "MAE B0", "AVERAGE ( model_by_season_out[mae_b0] )", "0.000", "Model", ""),
    ("model_by_season_out", "MAE B1", "AVERAGE ( model_by_season_out[mae_b1] )", "0.000", "Model", ""),
    ("model_by_season_out", "MAE LightGBM", "AVERAGE ( model_by_season_out[mae_gbm] )", "0.000", "Model", ""),
    # data quality
    ("mart_dq_health", "Quarantined Rows",
     'CALCULATE ( SUM ( mart_dq_health[n_rows] ), mart_dq_health[outcome] = "quarantined" )',
     "#,0", "Data quality", ""),
    ("mart_dq_health", "Flagged Rows",
     'CALCULATE ( SUM ( mart_dq_health[n_rows] ), mart_dq_health[outcome] = "flagged" )',
     "#,0", "Data quality", ""),
    ("mart_dq_health", "DQ Rows", "SUM ( mart_dq_health[n_rows] )", "#,0", "Data quality", ""),
    ("mart_dq_health", "Rules Fired", "DISTINCTCOUNT ( mart_dq_health[rule_code] )", "0",
     "Data quality", "Rules that fired at least once in the current context"),
    ("dim_rule", "Rules Available", "COUNTROWS ( dim_rule )", "0", "Data quality",
     "Coded rules shipped with this project"),
]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def lit(value: str) -> dict:
    return {"expr": {"Literal": {"Value": value}}}


def solid(hex_colour: str) -> dict:
    return {"solid": {"color": lit(f"'{hex_colour}'")}}


def col(entity, prop, active=False):
    proj = {"field": {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                                 "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}
    if active:
        proj["active"] = True
    return proj


def meas(entity, prop):
    return {"field": {"Measure": {"Expression": {"SourceRef": {"Entity": entity}},
                                  "Property": prop}},
            "queryRef": f"{entity}.{prop}", "nativeQueryRef": prop}


def role(*projections):
    return {"projections": list(projections)}


def position(x, y, w, h, z=0, tab=None):
    p = {"x": x, "y": y, "z": z, "width": w, "height": h}
    if tab is not None:
        p["tabOrder"] = tab
    return p


def container(title_text=None, alt=None, size="12D"):
    """visualContainerObjects: optional title and alt text."""
    out: dict = {}
    if title_text:
        out["title"] = [{"properties": {
            "show": lit("true"), "text": lit(f"'{title_text}'"), "fontSize": lit(size),
            "bold": lit("true"), "fontColor": solid(TEXT)}}]
    if alt:
        out["general"] = [{"properties": {"altText": lit(f"'{alt}'")}}]
    return out or None


def dp_series(entity, prop, value, hex_colour):
    """Per-category colour via a scopeId equality selector."""
    return {"properties": {"fill": solid(hex_colour)}, "selector": {"data": [{"scopeId": {
        "Comparison": {"ComparisonKind": 0,
                       "Left": {"Column": {"Expression": {"SourceRef": {"Entity": entity}},
                                           "Property": prop}},
                       "Right": {"Literal": {"Value": f"'{value}'"}}}}}]}}


def dp_measure(entity, name, hex_colour):
    return {"properties": {"fill": solid(hex_colour)},
            "selector": {"metadata": f"{entity}.{name}"}}


def labels(show=True, fmt=None):
    props = {"show": lit("true" if show else "false"), "color": solid(TEXT),
             "fontSize": lit("10D")}
    if fmt:
        props["labelDisplayUnits"] = lit("1D")
    return [{"properties": props}]


def visual(name, pos, visual_type, *, query_state=None, objects=None, cont=None,
           needs_query=True, sync=None, sort=None):
    v: dict = {"visualType": visual_type}
    if needs_query:
        v["query"] = {"queryState": query_state or {}}
        if sort:
            v["query"]["sortDefinition"] = sort
    if objects:
        v["objects"] = objects
    if cont:
        v["visualContainerObjects"] = cont
    if sync:
        v["syncGroup"] = {"groupName": sync, "fieldChanges": True, "filterChanges": True}
    v["drillFilterOtherVisuals"] = True
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": pos, "visual": v,
            "filterConfig": {"filters": []}}


def card(name, pos, entity, measure, caption=None, alt=None):
    return visual(
        name, pos, "card", query_state={"Values": role(meas(entity, measure))},
        objects={"categoryLabels": [{"properties": {"show": lit("false")}}]},
        cont=container(caption, alt or caption))


def text_card(name, pos, entity, measure, size=11, colour=MUTED, alt=None):
    """A measure rendered as a small caption (a card with the value text styled down)."""
    return visual(
        name, pos, "card", query_state={"Values": role(meas(entity, measure))},
        objects={
            "categoryLabels": [{"properties": {"show": lit("false")}}],
            "labels": [{"properties": {"fontSize": lit(f"{size}D"),
                                       "color": solid(colour)}}],
        },
        cont={"background": [{"properties": {"show": lit("false")}}],
              "border": [{"properties": {"show": lit("false")}}],
              **(container(None, alt) or {})})


def table(name, pos, entity, columns, heading, sort=None, alt=None):
    return visual(name, pos, "tableEx",
                  query_state={"Values": role(*[col(entity, c) for c in columns])},
                  cont=container(heading, alt or heading, "11D"), sort=sort)


def sort_by(entity, prop, direction="Descending", measure=False):
    kind = "Measure" if measure else "Column"
    return {"sort": [{"field": {kind: {"Expression": {"SourceRef": {"Entity": entity}},
                                       "Property": prop}}, "direction": direction}],
            "isDefaultSort": True}


def textbox(name, pos, paragraphs, bold_first=False, box=False):
    """paragraphs: list of (text, size_pt, bold, colour)."""
    runs = []
    for text, size, bold, colour in paragraphs:
        style = {"fontSize": f"{size}pt", "fontFamily": "Segoe UI", "color": colour}
        if bold:
            style["fontWeight"] = "bold"
        runs.append({"textRuns": [{"value": text, "textStyle": style}],
                     "horizontalTextAlignment": "left"})
    v: dict = {"visualType": "textbox",
               "objects": {"general": [{"properties": {"paragraphs": runs}}]},
               "drillFilterOtherVisuals": True}
    # Chrome set explicitly: a theme wildcard otherwise adds a title bar, and a
    # textbox whose content overflows its box grows a scrollbar that the PDF keeps.
    on = lit("true")
    off = lit("false")
    v["visualContainerObjects"] = {
        "title": [{"properties": {"show": off}}],
        "background": [{"properties": {"show": on, "color": solid(PANEL),
                                       "transparency": lit("0D")}} if box
                       else {"properties": {"show": off}}],
        "border": [{"properties": {"show": on, "color": solid(BORDER),
                                   "radius": lit("6D")}} if box
                   else {"properties": {"show": off}}],
        "dropShadow": [{"properties": {"show": off}}],
    }
    return {"$schema": SCHEMA_VISUAL, "name": name, "position": pos, "visual": v,
            "filterConfig": {"filters": []}}


# --------------------------------------------------------------------------- #
# semantic model (TMDL)
# --------------------------------------------------------------------------- #
def m_query(table_name, cols):
    types = ", ".join(f'{{"{c}", {mt[1]}}}' for c, mt in cols)
    return ("let\n"
            f'    Source = Csv.Document(File.Contents(DataFolder & "\\{table_name}.csv"), '
            '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),\n'
            "    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars = true]),\n"
            f"    Typed = Table.TransformColumnTypes(Promoted, {{{types}}}, \"en-US\")\n"
            "in\n    Typed")


def tmdl_table(table_name, cols):
    out = [f"table {table_name}"]
    for cname, (dtype, _m) in cols:
        out += ["", f"\tcolumn {cname}", f"\t\tdataType: {dtype}"]
        if dtype == I64:
            out.append("\t\tformatString: 0")
        if dtype == DATE:
            out.append("\t\tformatString: yyyy-mm-dd")
        if (table_name, cname) in HIDDEN:
            out.append("\t\tisHidden")
        out += ["\t\tsummarizeBy: none", f"\t\tsourceColumn: {cname}"]
    for _t, mname, dax, fmt, folder, desc in [m for m in MEASURES if m[0] == table_name]:
        out.append("")
        if desc:
            out.append(f"\t/// {desc}")
        out.append(f"\tmeasure '{mname}' = {dax}")
        if fmt:
            out.append(f"\t\tformatString: {fmt}")
        out.append(f'\t\tdisplayFolder: "{folder}"')
    out += ["", f"\tpartition {table_name} = m", "\t\tmode: import", "\t\tsource ="]
    out += ["\t\t\t\t" + line for line in m_query(table_name, cols).split("\n")]
    out += ["", "\tannotation PBI_ResultType = Table"]
    return "\n".join(out) + "\n"


def emit_model(root: Path) -> None:
    sm = root / f"{NAME}.SemanticModel"
    write_json(sm / "definition.pbism", {"$schema": SCHEMA_PBISM, "version": "4.2",
                                         "settings": {}})
    d = sm / "definition"
    write_text(d / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
    model = ["model Model", "\tculture: en-US", "\tdefaultPowerBIDataSourceVersion: powerBI_V3",
             "\tdiscourageImplicitMeasures", "\tsourceQueryCulture: en-US", ""]
    model += [f"ref table {t}" for t in TABLES]
    write_text(d / "model.tmdl", "\n".join(model) + "\n")
    write_text(d / "expressions.tmdl",
               f'expression DataFolder = "{DATA_FOLDER}" '
               'meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
               "\n\tannotation PBI_ResultType = Text\n")
    rels = []
    for rname, frm, to in RELATIONSHIPS:
        rels += [f"relationship {rname}", f"\tfromColumn: {frm}", f"\ttoColumn: {to}", ""]
    write_text(d / "relationships.tmdl", "\n".join(rels))
    for table_name, cols in TABLES.items():
        write_text(d / "tables" / f"{table_name}.tmdl", tmdl_table(table_name, cols))


# --------------------------------------------------------------------------- #
# theme
# --------------------------------------------------------------------------- #
def theme() -> dict:
    def fc(c):
        return {"solid": {"color": c}}

    axis = [{"labelColor": fc(MUTED), "fontSize": 10, "titleColor": fc(MUTED),
             "gridlineColor": fc(BORDER), "showAxisTitle": True}]
    return {
        "name": CUSTOM_THEME,
        "dataColors": [ACCENT, "#FFD12E", "#EBEBEB", "#4C9BE8", "#3DDC97", "#B07AA1",
                       "#FF8A3D", "#76B7B2"],
        "background": PANEL, "foreground": TEXT, "tableAccent": ACCENT,
        "good": GREEN, "neutral": "#FFD12E", "bad": ACCENT,
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 14, "color": TEXT},
            "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": MUTED},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 30, "color": TEXT},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"color": fc(PANEL), "transparency": 0, "show": True}],
                "border": [{"show": True, "color": fc(BORDER), "radius": 6}],
                "title": [{"fontColor": fc(TEXT), "fontFamily": "Segoe UI Semibold",
                           "fontSize": 12}],
                "legend": [{"labelColor": fc(MUTED), "fontSize": 10}],
                "categoryAxis": axis, "valueAxis": axis,
                "labels": [{"color": fc(TEXT), "fontSize": 10}],
            }},
            "page": {"*": {
                "background": [{"color": fc(PAGE_BG), "transparency": 0}],
                "outspace": [{"color": fc(PAGE_BG), "transparency": 0}]}},
            "card": {"*": {"labels": [{"color": fc(TEXT), "fontSize": 28,
                                       "fontFamily": "Segoe UI Semibold"}]}},
            "tableEx": {"*": {
                "columnHeaders": [{"fontColor": fc(TEXT), "backColor": fc("#1C2230"),
                                   "fontSize": 10}],
                "values": [{"fontColor": fc(TEXT), "backColor": fc(PANEL),
                            "backColorPrimary": fc(PANEL), "backColorSecondary": fc("#181D28"),
                            "fontSize": 10}],
                "grid": [{"gridHorizontal": True, "gridHorizontalColor": fc(BORDER),
                          "gridVertical": False}]}},
            "pivotTable": {"*": {
                "columnHeaders": [{"fontColor": fc(TEXT), "backColor": fc("#1C2230")}],
                "rowHeaders": [{"fontColor": fc(TEXT), "backColor": fc(PANEL)}],
                "values": [{"fontColor": fc(TEXT), "backColor": fc(PANEL)}]}},
            "slicer": {"*": {"items": [{"fontColor": fc(TEXT), "background": fc(PANEL)}],
                             "header": [{"fontColor": fc(MUTED)}]}},
            "textbox": {"*": {"background": [{"show": False}], "border": [{"show": False}]}},
            "pageNavigator": {"*": {
                "background": [{"show": False}], "border": [{"show": False}]}},
        },
    }


# --------------------------------------------------------------------------- #
# pages
# --------------------------------------------------------------------------- #
PAGES = [("p0", "Overview"), ("p1", "Tyres"), ("p2", "Pit stops"), ("p3", "Undercut"),
         ("p4", "Model"), ("p5", "Data quality"), ("p6", "Limits")]

SEASON_SYNC = "season"


def chrome(page_id: str, title_text: str, subtitle: str, season_slicer=True) -> list[dict]:
    v = [
        textbox(f"{page_id}_title", position(24, 8, 900, 46, z=10),
                [(title_text, 18, True, TEXT)]),
        textbox(f"{page_id}_sub", position(24, 56, 1000, 28, z=10),
                [(subtitle, 10, False, MUTED)]),
        visual(f"{page_id}_nav", position(24, 86, 980, 34, z=20), "pageNavigator",
               needs_query=False, cont=container(None, "Page navigation")),
        textbox(f"{page_id}_foot", position(24, 670, 1232, 32, z=10),
                [("Unofficial OpenF1 data, 2023 to 2025. F1 and related marks are trademarks of "
                  "Formula One Licensing B.V.; this project is not affiliated with Formula 1. "
                  "github.com/SharlEclair/f1-pitwall-platform", 8, False, MUTED)]),
    ]
    if season_slicer:
        v.append(visual(
            f"{page_id}_season", position(1052, 74, 204, 36, z=30), "slicer",
            query_state={"Values": role(col("dim_season", "season", active=True))},
            objects={"data": [{"properties": {"mode": lit("'Dropdown'")}}]},
            cont=container(None, "Season filter"), sync=SEASON_SYNC))
    return v


def build_pages() -> dict[str, list[dict]]:
    TY, PI, UG, UP, US = ("mart_tyre_degradation", "mart_pit_loss", "undercut_grid",
                          "undercut_primary", "undercut_by_season")
    MS, MD, MO, DQ = "model_summary", "model_paired_differences", "model_by_season_out", "mart_dq_health"
    pages: dict[str, list[dict]] = {}

    # ----- p0 Overview ------------------------------------------------------
    v = chrome("p0", "F1 Pitwall: race strategy, measured",
               "Four strategy questions answered from three seasons of OpenF1 timing data, "
               "with how far to trust each answer.", season_slicer=False)
    xs = [24, 334, 644, 954]
    v += [
        card("p0_k1", position(xs[0], 124, 300, 112), TY, "Slope MEDIUM",
             "1. Tyre wear (MEDIUM, s/lap)"),
        card("p0_k2", position(xs[1], 124, 300, 112), PI, "Pit Loss GREEN",
             "2. Green-flag pit loss"),
        card("p0_k3", position(xs[2], 124, 300, 112), UP, "Primary Rate",
             "3. Undercut success rate"),
        card("p0_k4", position(xs[3], 124, 300, 112), MD, "Mean Diff",
             "4. LightGBM minus linear (MAE)"),
        textbox("p0_c1", position(xs[0], 244, 300, 78), [
            ("Weak. The fuel correction is assumed (0.04 s/lap), so the slope is mostly "
             "that assumption.", 10, False, MUTED)]),
        textbox("p0_c2", position(xs[1], 244, 300, 78), [
            ("Solid under green flags. Safety Car and VSC estimates are unstable.", 10, False,
             MUTED)]),
        textbox("p0_c3", position(xs[2], 244, 300, 78), [
            ("One definition, small sample; swings with the starting gap. Not a universal "
             "rate.", 10, False, MUTED)]),
        textbox("p0_c4", position(xs[3], 244, 300, 78), [
            ("Fixed settings, no tuning; checked across races and whole seasons.", 10, False,
             MUTED)]),
        visual("p0_chart", position(654, 336, 600, 330), "clusteredColumnChart",
               query_state={"Category": role(col("dim_season", "season", active=True)),
                            "Series": role(col("pit_loss_by_season", "track_status", active=True)),
                            "Y": role(meas("pit_loss_by_season", "Pit Loss Season"))},
               objects={"dataPoint": [dp_series("pit_loss_by_season", "track_status", "GREEN", GREEN),
                                      dp_series("pit_loss_by_season", "track_status", "SC", SC),
                                      dp_series("pit_loss_by_season", "track_status", "VSC", VSC)],
                        "labels": labels(),
                        "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                        "legend": [{"properties": {"showTitle": lit("false")}}]},
               cont=container("Pit loss by season: only green flag is steady",
                              "Median pit loss in seconds by season and track status")),
        textbox("p0_text", position(24, 336, 614, 330), [
            ("What to take from this", 14, True, TEXT),
            ("", 6, False, MUTED),
            ("Every figure is computed from validated data and reproducible from the "
             "repository. The page-by-page caveats matter as much as the numbers.", 11, False,
             MUTED),
            ("", 6, False, MUTED),
            ("\u2022  Tyres: wear slopes are descriptive; the assumed fuel effect dominates.", 11,
             False, TEXT),
            ("\u2022  Pit stops: green-flag loss is steady; Safety Car and VSC loss changes sign "
             "between seasons.", 11, False, TEXT),
            ("\u2022  Undercut: the rate depends mostly on the starting gap; car pace is not "
             "controlled.", 11, False, TEXT),
            ("\u2022  Model: LightGBM beats the linear baseline on three seasons, not on one.", 11,
             False, TEXT),
            ("\u2022  Data quality: 23 coded rules, quarantine, and reconciled counts "
             "end to end.", 11, False, TEXT),
        ], box=True),
    ]
    pages["p0"] = v

    # ----- p1 Tyres ---------------------------------------------------------
    v = chrome("p1", "Tyre degradation",
               "Median within-stint slope per compound, fuel-corrected with an assumed "
               "0.04 s/lap. Filter by season above.")
    for i, comp in enumerate(["HARD", "MEDIUM", "SOFT"]):
        v.append(card(f"p1_k{comp.lower()}", position(24 + i * 310, 124, 300, 100), TY,
                      f"Slope {comp}", f"{comp} slope"))
    for i, comp in enumerate(["HARD", "MEDIUM", "SOFT"]):
        v.append(text_card(f"p1_cap_{comp.lower()}", position(24 + i * 310, 226, 300, 24),
                           TY, f"Slope {comp} Caption"))
    v.append(textbox("p1_cav", position(954, 124, 300, 126), [
        ("Read with care", 11, True, TEXT),
        ("The corrected slope is the uncorrected one plus the 0.04 s/lap assumption. Use "
         "these to compare compounds and seasons, not as precise rates.", 10, False, MUTED)],
        box=True))
    v.append(visual(
        "p1_season_chart", position(24, 262, 610, 424), "clusteredColumnChart",
        query_state={"Category": role(col("dim_season", "season", active=True)),
                     "Series": role(col(TY, "compound", active=True)),
                     "Y": role(meas(TY, "Slope Median"))},
        objects={"dataPoint": [dp_series(TY, "compound", "SOFT", SOFT),
                               dp_series(TY, "compound", "MEDIUM", MEDIUM),
                               dp_series(TY, "compound", "HARD", HARD)],
                 "labels": labels(False),
                 "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                 "legend": [{"properties": {"showTitle": lit("false")}}]},
        cont=container("Median slope by season and compound",
                       "Median degradation slope in seconds per lap, by season and compound")))
    v.append(visual(
        "p1_scatter", position(654, 262, 600, 424), "scatterChart",
        query_state={"Category": role(col("dim_race", "race_label", active=True)),
                     "Series": role(col(TY, "compound", active=True)),
                     "X": role(meas(TY, "Fit Clean Laps")),
                     "Y": role(meas(TY, "Fit Slope"))},
        objects={"dataPoint": [dp_series(TY, "compound", "SOFT", SOFT),
                               dp_series(TY, "compound", "MEDIUM", MEDIUM),
                               dp_series(TY, "compound", "HARD", HARD)]},
        cont=container("Each dot is one race fit: small samples scatter most",
                       "Slope against number of clean laps for each race and compound")))
    pages["p1"] = v

    # ----- p2 Pit stops -----------------------------------------------------
    v = chrome("p2", "Pit-stop cost by track status",
               "In-lap plus out-lap minus two reference laps. Stops over 60 s (red-flag waits) "
               "are excluded.")
    for i, (st, m, rng) in enumerate([("GREEN", "Pit Loss GREEN", "Green Range Text"),
                                      ("SC", "Pit Loss SC", "SC Range Text"),
                                      ("VSC", "Pit Loss VSC", "VSC Range Text")]):
        v.append(card(f"p2_k{st.lower()}", position(24 + i * 310, 124, 300, 100), PI, m,
                      {"GREEN": "Green flag", "SC": "Safety Car", "VSC": "Virtual Safety Car"}[st]))
        v.append(text_card(f"p2_r{st.lower()}", position(24 + i * 310, 226, 300, 26),
                           "pit_loss_by_season", rng,
                           colour=GREEN if st == "GREEN" else "#FF8A3D"))
    v.append(textbox("p2_cav", position(954, 124, 300, 128), [
        ("Why two of these are not numbers to quote", 11, True, TEXT),
        ("Under neutralisation the estimator breaks down: the Safety Car value changes sign "
         "between seasons. Only the green-flag figure is stable.", 10, False, MUTED)],
        box=True))
    v.append(visual(
        "p2_chart", position(24, 264, 610, 422), "clusteredColumnChart",
        query_state={"Category": role(col("dim_season", "season", active=True)),
                     "Series": role(col("pit_loss_by_season", "track_status", active=True)),
                     "Y": role(meas("pit_loss_by_season", "Pit Loss Season"))},
        objects={"dataPoint": [dp_series("pit_loss_by_season", "track_status", "GREEN", GREEN),
                               dp_series("pit_loss_by_season", "track_status", "SC", SC),
                               dp_series("pit_loss_by_season", "track_status", "VSC", VSC)],
                 "labels": labels()},
        cont=container("Median pit loss by season and status (s)",
                       "Median pit loss in seconds by season and track status")))
    v.append(table("p2_table", position(654, 264, 600, 422), "pit_loss_by_season",
                   ["season", "track_status", "median_pit_loss_s", "stops", "races"],
                   "Season, status, stops and races behind each figure"))
    pages["p2"] = v

    # ----- p3 Undercut ------------------------------------------------------
    v = chrome("p3", "How often does an undercut work?",
               "A frequency under one stated definition, not a universal rate. "
               "The definition was fixed before any outcome was computed.", season_slicer=False)
    v.append(card("p3_krate", position(24, 124, 300, 100), UP, "Primary Rate",
                  "Primary definition: success rate"))
    v.append(card("p3_kn", position(334, 124, 300, 100), US, "Primary Decided",
                  "Decided attempts"))
    v.append(text_card("p3_kn_cap", position(334, 226, 300, 26), US, "Primary Attempts Text"))
    v.append(text_card("p3_krate_cap", position(24, 226, 300, 26), UP, "Primary Interval Text"))
    v.append(textbox("p3_def", position(654, 124, 600, 128), [
        ("Primary definition", 11, True, TEXT),
        ("Car A stops with car B directly ahead and a known gap of at most 3 s; B stops "
         "within 3 laps; no Safety Car, VSC or red flag. Success: A is ahead of B two laps "
         "after B's stop.", 10, False, MUTED)], box=True))
    v.append(visual(
        "p3_line", position(24, 264, 610, 422), "lineChart",
        query_state={"Category": role(col(UG, "gap_threshold_s", active=True)),
                     "Series": role(col(UG, "response_window_laps", active=True)),
                     "Y": role(meas(UG, "Undercut Rate"))},
        objects={"labels": labels(False),
                 "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                 "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                 "legend": [{"properties": {"showTitle": lit("false")}}]},
        cont=container("Success rate against the largest starting gap allowed (s)",
                       "Undercut success rate by starting gap threshold and response window")))
    v.append(visual(
        "p3_matrix", position(654, 264, 600, 210), "pivotTable",
        query_state={"Rows": role(col(UG, "gap_threshold_s", active=True)),
                     "Columns": role(col(UG, "response_window_laps", active=True)),
                     "Values": role(meas(UG, "Undercut Rate"))},
        cont=container("Sensitivity: success rate by gap (rows) and window (laps)",
                       "Sensitivity matrix of undercut success rate", "11D")))
    v.append(table("p3_table", position(654, 478, 600, 208), US,
                   ["season_scope", "n_attempts", "n_success", "n_failure", "n_inconclusive",
                    "success_rate"], "Primary definition by season"))
    pages["p3"] = v

    # ----- p4 Model ---------------------------------------------------------
    v = chrome("p4", "Lap-time model: LightGBM against the baselines",
               "Held-out races; every method sees only a driver's first five clean laps of "
               "the race. Fixed settings, no tuning.", season_slicer=False)
    v.append(card("p4_kdiff", position(24, 124, 300, 100), MD, "Mean Diff",
                  "LightGBM minus linear baseline (MAE)"))
    v.append(text_card("p4_kdiff_cap", position(24, 226, 300, 26), MD, "Diff Interval Text"))
    v.append(textbox("p4_verdict_label", position(346, 126, 200, 32), [
        ("Verdict", 11, True, TEXT)]))
    v.append(text_card("p4_kbetter", position(346, 162, 600, 26), MD, "Races Better Text",
                       size=14, colour=TEXT))
    v.append(text_card("p4_verdict", position(346, 196, 890, 56), MD, "Model Verdict",
                       size=14, colour=TEXT))
    v.append(visual(
        "p4_bar", position(24, 264, 400, 422), "clusteredBarChart",
        query_state={"Category": role(col(MS, "method", active=True)),
                     "Y": role(meas(MS, "Mean MAE"))},
        objects={"dataPoint": [dp_series(MS, "method", "B0 persistence", B0),
                               dp_series(MS, "method", "B1 linear physics", B1),
                               dp_series(MS, "method", "LightGBM", GBM)],
                 "labels": labels()},
        cont=container("Mean absolute error across races (s)",
                       "Mean absolute error in seconds for each method")))
    v.append(visual(
        "p4_season", position(436, 264, 410, 422), "clusteredColumnChart",
        query_state={"Category": role(col("dim_season", "season", active=True)),
                     "Y": role(meas(MO, "MAE B0"), meas(MO, "MAE B1"), meas(MO, "MAE LightGBM"))},
        objects={"dataPoint": [dp_measure(MO, "MAE B0", B0), dp_measure(MO, "MAE B1", B1),
                               dp_measure(MO, "MAE LightGBM", GBM)],
                 "labels": labels(),
                 "valueAxis": [{"properties": {"showAxisTitle": lit("false")}}]},
        cont=container("Stricter check: hold out a whole season (s)",
                       "Mean absolute error when each season is held out whole")))
    v.append(table("p4_race", position(858, 264, 396, 422), "model_by_race",
                   ["circuit_short_name", "season", "mae_b1", "mae_gbm"],
                   "By race, worst first (LightGBM)",
                   sort=sort_by("model_by_race", "mae_gbm")))
    pages["p4"] = v

    # ----- p5 Data quality --------------------------------------------------
    v = chrome("p5", "Data quality: what the rules caught",
               "Bad rows are never dropped silently: quarantined rows are kept apart with a "
               "reason, flagged rows stay with a marker.")
    v.append(card("p5_kq", position(24, 124, 300, 100), DQ, "Quarantined Rows",
                  "Quarantined rows"))
    v.append(card("p5_kf", position(334, 124, 300, 100), DQ, "Flagged Rows", "Flagged rows"))
    v.append(card("p5_kr", position(644, 124, 300, 100), "dim_rule", "Rules Available",
                  "Rules available"))
    v.append(textbox("p5_note", position(954, 124, 300, 128), [
        ("Reconciliation", 11, True, TEXT),
        ("For every session raw rows = silver rows + quarantined rows, checked in S3 and "
         "again after loading into Snowflake.", 10, False, MUTED)], box=True))
    v.append(visual(
        "p5_bar", position(24, 264, 700, 422), "barChart",
        query_state={"Category": role(col(DQ, "rule_code", active=True)),
                     "Series": role(col(DQ, "outcome", active=True)),
                     "Y": role(meas(DQ, "DQ Rows")),
                     "Tooltips": role(col("dim_rule", "description"))},
        objects={"dataPoint": [dp_series(DQ, "outcome", "flagged", FLAGGED),
                               dp_series(DQ, "outcome", "quarantined", QUARANTINED)],
                 "labels": labels(),
                 "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                 "legend": [{"properties": {"showTitle": lit("false")}}]},
        cont=container("Rows by rule and outcome (hover for the rule)",
                       "Rows quarantined or flagged by each data quality rule")))
    v.append(visual(
        "p5_season", position(744, 264, 510, 422), "columnChart",
        query_state={"Category": role(col(DQ, "season", active=True)),
                     "Series": role(col(DQ, "outcome", active=True)),
                     "Y": role(meas(DQ, "DQ Rows"))},
        objects={"dataPoint": [dp_series(DQ, "outcome", "flagged", FLAGGED),
                               dp_series(DQ, "outcome", "quarantined", QUARANTINED)],
                 "labels": labels(),
                 "categoryAxis": [{"properties": {"showAxisTitle": lit("false")}}],
                 "legend": [{"properties": {"showTitle": lit("false")}}]},
        cont=container("Rows by season and outcome",
                       "Flagged and quarantined rows by season")))
    pages["p5"] = v

    # ----- p6 Limits --------------------------------------------------------
    v = chrome("p6", "Method and limits",
               "What each number rests on and what it does not tell you.",
               season_slicer=False)
    cards = [
        ("Assumptions", ["The fuel effect is assumed at 0.04 s per lap.",
                         "Track status comes from message timestamps, so edge laps are "
                         "approximate."]),
        ("Estimates", ["Pit loss is an estimate from lap times, not stationary time.",
                       "Safety Car and VSC pit loss is unreliable and changes between seasons."]),
        ("Sample and scope", ["Three seasons; nothing here is a claim about other years or "
                              "regulations.",
                              "Circuits repeat across seasons, so a whole-season check is shown "
                              "as well."]),
        ("Not controlled", ["Undercut: pace difference between cars, tyres, traffic, DRS and "
                            "circuit.",
                            "Position is the on-track order, not the official classification."]),
        ("Data and licence", ["Unofficial OpenF1 data; its reuse terms are not stated.",
                              "Only aggregated tables are shared; F1 marks belong to Formula One "
                              "Licensing B.V."]),
        ("Blocked or unexplained", ["GitHub OIDC deploys are blocked by an organisation policy.",
                                    "The Snowflake storage integration never worked; data loads "
                                    "through an internal stage."]),
    ]
    for i, (head, bullets) in enumerate(cards):
        x, y = 24 + (i % 3) * 414, 124 + (i // 3) * 286
        paras = [(head, 13, True, TEXT), ("", 6, False, MUTED)]
        paras += [(f"\u2022  {b}", 11, False, MUTED) for b in bullets]
        v.append(textbox(f"p6_c{i}", position(x, y, 400, 270), paras, box=True))
    pages["p6"] = v
    return pages


# --------------------------------------------------------------------------- #
# report
# --------------------------------------------------------------------------- #
def emit_report(root: Path) -> None:
    rep = root / f"{NAME}.Report"
    write_json(rep / "StaticResources" / "RegisteredResources" / f"{CUSTOM_THEME}.json", theme())
    write_json(rep / "definition.pbir", {
        "$schema": SCHEMA_PBIR, "version": "4.0",
        "datasetReference": {"byPath": {"path": f"../{NAME}.SemanticModel"}}})
    d = rep / "definition"
    write_json(d / "version.json", {"$schema": SCHEMA_VERSION, "version": "2.0.0"})

    theme_collection = {"baseTheme": {"name": BASE_THEME, "reportVersionAtImport": VERSIONS,
                                      "type": "SharedResources"}}
    packages = [{"name": "SharedResources", "type": "SharedResources",
                 "items": [{"name": BASE_THEME, "path": f"BaseThemes/{BASE_THEME}.json",
                            "type": "BaseTheme"}]}]
    if REGISTER_THEME:
        theme_collection["customTheme"] = {"name": CUSTOM_THEME,
                                           "reportVersionAtImport": VERSIONS,
                                           "type": "RegisteredResources"}
        packages.append({"name": "RegisteredResources", "type": "RegisteredResources",
                         "items": [{"name": CUSTOM_THEME, "path": f"{CUSTOM_THEME}.json",
                                    "type": "CustomTheme"}]})
    write_json(d / "report.json", {
        "$schema": SCHEMA_REPORT, "themeCollection": theme_collection,
        "objects": {"section": [{"properties": {"verticalAlignment": lit("'Top'")}}]},
        "resourcePackages": packages,
        "settings": {"allowChangeFilterTypes": True, "useStylableVisualContainerHeader": True,
                     "exportDataMode": "AllowSummarized", "defaultDrillFilterOtherVisuals": True,
                     "useEnhancedTooltips": True, "useDefaultAggregateDisplayName": True}})
    page_defs = build_pages()
    write_json(d / "pages" / "pages.json", {
        "$schema": SCHEMA_PAGES, "pageOrder": [p for p, _ in PAGES],
        "activePageName": PAGES[0][0]})
    for pname, display in PAGES:
        write_json(d / "pages" / pname / "page.json", {
            "$schema": SCHEMA_PAGE, "name": pname, "displayName": display,
            "displayOption": "FitToPage", "height": 720, "width": 1280,
            "filterConfig": {"filters": []},
            "objects": {
                "background": [{"properties": {"color": solid(PAGE_BG),
                                               "transparency": lit("0D")}}],
                "outspace": [{"properties": {"color": solid(PAGE_BG),
                                             "transparency": lit("0D")}}]}})
        for vis in page_defs[pname]:
            write_json(d / "pages" / pname / "visuals" / vis["name"] / "visual.json", vis)


def main() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    write_json(OUT / f"{NAME}.pbip", {
        "$schema": SCHEMA_PBIP, "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAME}.Report"}}],
        "settings": {"enableAutoRecovery": True}})
    emit_model(OUT)
    emit_report(OUT)
    n_vis = sum(len(v) for v in build_pages().values())
    print(f"wrote {OUT}")
    print(f"  tables={len(TABLES)} measures={len(MEASURES)} relationships={len(RELATIONSHIPS)}")
    print(f"  pages={len(PAGES)} visuals={n_vis}")


if __name__ == "__main__":
    main()
