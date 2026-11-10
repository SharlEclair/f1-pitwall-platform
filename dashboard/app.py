"""Streamlit dashboard for a race strategist: four questions, each with its answer and caveats.

Reads only small aggregated tables in dashboard/data (no row-level lap data). Every number shown is
computed from those files; the text around it is qualitative.
Run: streamlit run dashboard/app.py
"""

import json
from pathlib import Path

import altair as alt
import polars as pl
import streamlit as st

DATA = Path(__file__).parent / "data"
COMPOUND_COLOURS = alt.Scale(domain=["SOFT", "MEDIUM", "HARD"],
                             range=["#d62728", "#e6a817", "#7f7f7f"])
METHODS = {"b0": "B0 persistence", "b1": "B1 linear physics", "gbm": "LightGBM"}

st.set_page_config(page_title="F1 Pitwall: 2024 race strategy questions", layout="wide")


@st.cache_data
def load():
    tables = {name: pl.read_parquet(DATA / f"{name}.parquet")
              for name in ("mart_tyre_degradation", "mart_pit_loss", "mart_dq_health")}
    model = json.loads((DATA / "ml_results.json").read_text())
    return tables, model


tables, model = load()
deg, pit, dq = (tables["mart_tyre_degradation"], tables["mart_pit_loss"], tables["mart_dq_health"])
results, effects = model["results"], model["effects"]

st.title("F1 Pitwall: four strategy questions, 2024 season")
st.caption(
    "Built from OpenF1 timing data for the 2024 races and sprints, validated, modelled in dbt and "
    "evaluated honestly. Estimates are descriptive and conditional on the stated assumptions; "
    "caveats sit next to each number."
)

tab_deg, tab_pit, tab_model, tab_dq, tab_about = st.tabs([
    "1. Tyre degradation", "2. Pit-stop cost", "3. Lap-time model", "Data quality", "Limits"])

with tab_deg:
    st.subheader("How fast does each compound degrade, after correcting for fuel burn?")
    fitted = deg.filter(pl.col("slope_s_per_lap").is_not_null())
    summary = (
        fitted.group_by("compound")
        .agg(pl.len().alias("races"),
             pl.col("slope_s_per_lap").median().alias("corrected"),
             pl.col("slope_pooled_s_per_lap").median().alias("pooled"),
             pl.col("slope_uncorrected").median().alias("uncorrected"))
        .sort("compound")
    )
    cols = st.columns(len(summary))
    for col, row in zip(cols, summary.iter_rows(named=True), strict=False):
        col.metric(f"{row['compound']} (median over {row['races']} races)",
                   f"{row['corrected']:+.3f} s/lap",
                   help="Within-stint fit, fuel-corrected with the assumed effect.")
    st.warning(
        "Read with care: the fuel correction is an assumption (0.04 s per lap), and the corrected "
        "slope is largely the uncorrected slope plus that assumption. The lap-time model on the "
        "next tab estimates tyre-age slopes jointly with the race-progress effect, and for MEDIUM "
        "and HARD those intervals include zero. Use these slopes to compare races and compounds, "
        "not as precise rates."
    )
    chosen = st.multiselect("Compounds", ["SOFT", "MEDIUM", "HARD"], default=["MEDIUM", "HARD"])
    chart = (
        alt.Chart(fitted.filter(pl.col("compound").is_in(chosen)).to_pandas())
        .mark_circle(opacity=0.8)
        .encode(
            x=alt.X("circuit_short_name:N", title=None, sort="-y"),
            y=alt.Y("slope_s_per_lap:Q", title="Degradation (s per lap of tyre age)"),
            color=alt.Color("compound:N", scale=COMPOUND_COLOURS),
            size=alt.Size("n_clean_laps:Q", title="Clean laps",
                          legend=alt.Legend(symbolFillColor="#9aa0a6")),
            tooltip=["circuit_short_name", "session_name", "compound", "n_clean_laps", "n_stints",
                     alt.Tooltip("slope_s_per_lap:Q", format="+.3f"),
                     alt.Tooltip("slope_uncorrected:Q", format="+.3f"),
                     alt.Tooltip("slope_pooled_s_per_lap:Q", format="+.3f")],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, width="stretch")
    st.caption(
        "Each dot is one race (or sprint) and compound with enough clean laps and tyre-age spread. "
        "Negative values are real in the data (track evolution can outweigh wear, e.g. Monaco)."
    )
    st.dataframe(
        summary.with_columns(pl.col("corrected", "pooled", "uncorrected").round(3)).rename(
            {"corrected": "median corrected (assumed fuel)", "pooled": "median pooled fit",
             "uncorrected": "median uncorrected"}),
        hide_index=True, width="stretch")

with tab_pit:
    st.subheader("What does a pit stop cost, normally and under Safety Car or VSC?")
    by_status = (
        pit.filter(pl.col("median_pit_loss_s").is_not_null())
        .group_by("track_status")
        .agg(pl.col("n_stops_with_loss").sum().alias("stops"),
             pl.len().alias("races"),
             pl.col("median_pit_loss_s").median().alias("loss"),
             pl.col("median_pit_loss_s").min().alias("lowest"),
             pl.col("median_pit_loss_s").max().alias("highest"),
             pl.col("median_lane_duration_s").median().alias("lane"))
        .sort("track_status")
    )
    cols = st.columns(len(by_status))
    for col, row in zip(cols, by_status.iter_rows(named=True), strict=False):
        col.metric(f"{row['track_status']}: median pit loss", f"{row['loss']:.1f} s",
                   help=f"Median of per-race medians over {row['races']} races, "
                        f"{row['stops']} stops.")
        col.caption(f"{row['races']} races, {row['stops']} stops; per-race medians range "
                    f"from {row['lowest']:.1f} to {row['highest']:.1f} s")
    st.info(
        "Pit loss is an estimate: in-lap plus out-lap time minus two reference laps, and only when "
        "both laps ran under the same track status. Stops over 60 s (red-flag waits) are "
        "excluded. Safety Car and VSC figures rest on far fewer stops than green flag; check the "
        "stop counts before relying on them."
    )
    strip = (
        alt.Chart(pit.filter(pl.col("median_pit_loss_s").is_not_null()).to_pandas())
        .mark_circle(opacity=0.8)
        .encode(
            x=alt.X("track_status:N", title="Track status at the stop",
                    sort=["GREEN", "VSC", "SC"]),
            y=alt.Y("median_pit_loss_s:Q", title="Median pit loss in the race (s)"),
            size=alt.Size("n_stops_with_loss:Q", title="Stops",
                          legend=alt.Legend(symbolFillColor="#9aa0a6")),
            color=alt.Color("track_status:N", legend=None),
            tooltip=["circuit_short_name", "track_status", "n_stops_with_loss",
                     alt.Tooltip("median_pit_loss_s:Q", format=".1f"),
                     alt.Tooltip("median_lane_duration_s:Q", format=".1f")],
        )
        .properties(height=360)
    )
    st.altair_chart(strip, width="stretch")
    st.dataframe(
        by_status.with_columns(pl.col("loss", "lowest", "highest", "lane").round(1)).rename(
            {"loss": "median pit loss (s)", "lowest": "lowest race (s)",
             "highest": "highest race (s)", "lane": "median lane time (s)"}),
        hide_index=True, width="stretch")

with tab_model:
    st.subheader("Can a model forecast later clean-lap times better than simple baselines?")
    gbm_vs_b1 = results["diff_gbm_b1"]
    st.metric("LightGBM minus linear baseline (mean MAE difference across races)",
              f"{gbm_vs_b1[0]:+.3f} s",
              help=f"95% interval {gbm_vs_b1[1]:+.3f} to {gbm_vs_b1[2]:+.3f}")
    if gbm_vs_b1[1] <= 0 <= gbm_vs_b1[2]:
        st.info(
            f"No detectable difference between LightGBM and the linear physics baseline: the 95% "
            f"interval ({gbm_vs_b1[1]:+.3f} to {gbm_vs_b1[2]:+.3f} s) includes zero. Both beat "
            "simply repeating the driver's early pace. Published as measured, not tuned.")
    else:
        st.info("The paired interval excludes zero; see the numbers below.")
    mae = [{"method": label, "mae": results["race_mae"][key][0],
            "low": results["race_mae"][key][1], "high": results["race_mae"][key][2]}
           for key, label in METHODS.items()]
    base = alt.Chart(alt.Data(values=mae)).encode(
        y=alt.Y("method:N", title=None, sort=list(METHODS.values())))
    st.altair_chart(
        (base.mark_bar(opacity=0.7).encode(
            x=alt.X("mae:Q", title="Mean absolute error across races (s), 95% CI over races"))
         + base.mark_rule(color="#e8eaed", strokeWidth=2).encode(x="low:Q", x2="high:Q")
         ).properties(height=180),
        width="stretch")
    st.caption(
        f"{results['n_races']} held-out races, {results['n_laps']:,} predicted laps. Each method "
        "sees only a driver's first 5 clean laps of the held-out race; the model also learns from "
        "the other races. Errors grow with the number of laps ahead (table below)."
    )
    left, right = st.columns(2)
    with left:
        st.markdown("**Error by compound (s)**")
        st.dataframe(pl.DataFrame(results["by_compound"]).with_columns(
            pl.col("err_b0", "err_b1", "err_gbm").round(3)).rename(
            {"err_b0": "B0", "err_b1": "B1", "err_gbm": "LightGBM"}),
            hide_index=True, width="stretch")
    with right:
        st.markdown("**Error by laps since calibration (s)**")
        st.dataframe(pl.DataFrame(results["by_horizon"]).with_columns(
            pl.col("err_b0", "err_b1", "err_gbm").round(3)).rename(
            {"err_b0": "B0", "err_b1": "B1", "err_gbm": "LightGBM"}),
            hide_index=True, width="stretch")
    st.markdown("**Race by race (worst first)**")
    st.dataframe(
        pl.DataFrame(results["folds"]).sort("mae_gbm", descending=True)
        .select("circuit_short_name", "n_laps", "mae_b0", "mae_b1", "mae_gbm")
        .with_columns(pl.col("mae_b0", "mae_b1", "mae_gbm").round(3))
        .rename({"circuit_short_name": "race", "mae_b0": "B0", "mae_b1": "B1",
                 "mae_gbm": "LightGBM"}),
        hide_index=True, width="stretch")
    lap = effects["lap_slope"]
    st.markdown(
        f"**Fuel and race-progress effect, estimated from the data:** {lap[0]:+.3f} s per lap "
        f"(95% CI {lap[1]:+.3f} to {lap[2]:+.3f}) versus the assumed "
        f"{model['assumed_fuel_effect']:+.2f}. This is fuel burn plus track evolution, "
        "not fuel alone."
    )

with tab_dq:
    st.subheader("Is the data trustworthy? Rows quarantined and flagged, by rule")
    st.write(
        "Bad rows are never dropped silently. **Quarantined** rows fail a hard rule and are kept "
        "apart with a reason; **flagged** rows stay in the data with a marker, and the clean-lap "
        "definition excludes them."
    )
    by_rule = (dq.group_by("rule_code", "outcome").agg(pl.col("n_rows").sum().alias("rows"))
               .sort("rule_code"))
    chart = (
        alt.Chart(by_rule.to_pandas()).mark_bar().encode(
            x=alt.X("rows:Q", title="Rows"), y=alt.Y("rule_code:N", title=None, sort="-x"),
            color=alt.Color("outcome:N", scale=alt.Scale(
                domain=["quarantined", "flagged"], range=["#d62728", "#e6a817"])),
            tooltip=["rule_code", "outcome", "rows"])
        .properties(height=300)
    )
    st.altair_chart(chart, width="stretch")
    st.dataframe(by_rule, hide_index=True, width="stretch")
    st.caption("Rule meanings and per-race counts are in docs/DQ-CATALOGUE.md in the repository.")

with tab_about:
    st.subheader("What this does not tell you")
    st.markdown(
        "- One season (2024); each circuit appears once, so nothing here generalises to unseen "
        "circuits or other years.\n"
        "- The fuel effect (0.04 s per lap) is an assumption in the degradation figures.\n"
        "- Pit loss is an estimate, and Safety Car / VSC figures use few stops.\n"
        "- The undercut base rate (is an undercut likely to work?) is not answered here.\n"
        "- Track status comes from race-control message timestamps; edge laps are approximate.\n"
        "- Data come from the unofficial OpenF1 API; F1 and related marks belong to Formula One "
        "Licensing B.V. This project is not affiliated with Formula 1."
    )
