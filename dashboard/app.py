"""Streamlit dashboard for a race strategist: strategy questions, each with answer and caveats.

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

st.set_page_config(page_title="F1 Pitwall: race strategy questions, 2023-2025", layout="wide")


@st.cache_data
def load():
    tables = {name: pl.read_parquet(DATA / f"{name}.parquet")
              for name in ("mart_tyre_degradation", "mart_pit_loss", "mart_dq_health")}
    model = json.loads((DATA / "ml_results.json").read_text())
    undercut = json.loads((DATA / "undercut_results.json").read_text())
    return tables, model, undercut


tables, model, undercut = load()
deg, pit, dq = (tables["mart_tyre_degradation"], tables["mart_pit_loss"], tables["mart_dq_health"])
results, effects = model["results"], model["effects"]

st.title("F1 Pitwall: strategy questions, 2023 to 2025 seasons")
st.caption(
    "Built from OpenF1 timing data for the 2023 to 2025 races and sprints, validated, modelled in "
    "dbt and evaluated honestly. Estimates are descriptive and conditional on the stated "
    "assumptions; caveats sit next to each number."
)
seasons = sorted(deg["season"].unique().to_list())
season_choice = st.radio("Season for the degradation, pit-cost and data-quality tabs",
                         ["All", *map(str, seasons)], horizontal=True)
if season_choice != "All":
    deg = deg.filter(pl.col("season") == int(season_choice))
    pit = pit.filter(pl.col("season") == int(season_choice))
    dq = dq.filter(pl.col("season") == int(season_choice))

tab_deg, tab_pit, tab_model, tab_under, tab_dq, tab_about = st.tabs([
    "1. Tyre degradation", "2. Pit-stop cost", "3. Lap-time model", "4. Undercut",
    "Data quality", "Limits"])

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
    spans_zero = [c for c in ("SOFT", "MEDIUM", "HARD")
                  if effects[f"age_slope_{c}"][1] <= 0 <= effects[f"age_slope_{c}"][2]]
    zero_note = (
        f"for {' and '.join(spans_zero)} those intervals include zero" if spans_zero
        else "none of those intervals includes zero"
    )
    st.warning(
        "Read with care: the fuel correction is an assumption (0.04 s per lap), and the corrected "
        "slope is largely the uncorrected slope plus that assumption. The lap-time model on the "
        f"next tab estimates tyre-age slopes jointly with the race-progress effect; {zero_note}. "
        "Use these slopes to compare races and compounds, not as precise rates."
    )
    chosen = st.multiselect("Compounds", ["SOFT", "MEDIUM", "HARD"], default=["MEDIUM", "HARD"])
    chart = (
        alt.Chart(fitted.filter(pl.col("compound").is_in(chosen)).with_columns(
            (pl.col("circuit_short_name") + " " + pl.col("season").cast(pl.Utf8)).alias("race"))
            .to_pandas())
        .mark_circle(opacity=0.8)
        .encode(
            x=alt.X("race:N", title=None, sort="-y"),
            y=alt.Y("slope_s_per_lap:Q", title="Degradation (s per lap of tyre age)"),
            color=alt.Color("compound:N", scale=COMPOUND_COLOURS),
            size=alt.Size("n_clean_laps:Q", title="Clean laps",
                          legend=alt.Legend(symbolFillColor="#9aa0a6")),
            tooltip=["race", "session_name", "compound", "n_clean_laps", "n_stints",
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
    per_season = (
        tables["mart_pit_loss"].filter(pl.col("median_pit_loss_s").is_not_null())
        .group_by("season", "track_status")
        .agg(pl.col("median_pit_loss_s").median().alias("median pit loss (s)"),
             pl.col("n_stops_with_loss").sum().alias("stops"), pl.len().alias("races"))
        .sort("season", "track_status")
        .with_columns(pl.col("median pit loss (s)").round(1))
    )
    st.warning(
        "Safety Car and VSC pit loss is not stable between seasons (table below, all seasons "
        "regardless of the filter above): a negative or larger-than-green value means the "
        "estimator is unreliable under neutralisation. Only the green-flag figure is steady."
    )
    st.dataframe(per_season, hide_index=True, width="stretch")
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
            tooltip=["circuit_short_name", "season", "track_status", "n_stops_with_loss",
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
        winner = "LightGBM" if gbm_vs_b1[2] < 0 else "The linear physics baseline"
        st.info(
            f"{winner} is better: the 95% interval ({gbm_vs_b1[1]:+.3f} to {gbm_vs_b1[2]:+.3f} s) "
            f"excludes zero, with LightGBM better in {results['races_gbm_better_than_b1']} of "
            f"{results['n_races']} races. The first season alone showed no detectable difference; "
            "the settings were fixed and not tuned. Circuits repeat across seasons, so see the "
            "stricter leave-one-season-out table below.")
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
    st.markdown("**Stricter check: hold out a whole season (s)**")
    st.dataframe(pl.DataFrame(results["by_season_out"]).with_columns(
        pl.col("mae_b0", "mae_b1", "mae_gbm").round(3)).rename(
        {"mae_b0": "B0", "mae_b1": "B1", "mae_gbm": "LightGBM"}),
        hide_index=True, width="stretch")
    st.markdown("**Race by race (worst first)**")
    st.dataframe(
        pl.DataFrame(results["folds"]).sort("mae_gbm", descending=True)
        .with_columns((pl.col("circuit_short_name") + " " + pl.col("season").cast(pl.Utf8))
                      .alias("race"))
        .select("race", "n_laps", "mae_b0", "mae_b1", "mae_gbm")
        .with_columns(pl.col("mae_b0", "mae_b1", "mae_gbm").round(3))
        .rename({"mae_b0": "B0", "mae_b1": "B1",
                 "mae_gbm": "LightGBM"}),
        hide_index=True, width="stretch")
    lap = effects["lap_slope"]
    st.markdown(
        f"**Fuel and race-progress effect, estimated from the data:** {lap[0]:+.3f} s per lap "
        f"(95% CI {lap[1]:+.3f} to {lap[2]:+.3f}) versus the assumed "
        f"{model['assumed_fuel_effect']:+.2f}. This is fuel burn plus track evolution, "
        "not fuel alone."
    )

with tab_under:
    st.subheader("How often does an undercut work?")
    primary = undercut["primary"]
    boot = undercut["bootstrap_over_races"]
    overall = next(r for r in undercut["by_scope"] if r["season_scope"] == "all")
    cols = st.columns(3)
    cols[0].metric("Success rate under the primary definition",
                   f"{100 * overall['success_rate']:.0f}%",
                   help=f"{overall['n_success']} successes, {overall['n_failure']} failures")
    cols[1].metric("Attempts (decided)", f"{overall['n_success'] + overall['n_failure']}")
    cols[2].metric("95% interval (bootstrap over races)",
                   f"{100 * boot['low']:.0f}% to {100 * boot['high']:.0f}%")
    st.info(
        f"Under this definition: car A stops with car B directly ahead and a known gap of at most "
        f"{primary['gap_threshold_s']:g} s; B stops within {primary['response_window_laps']} laps; "
        "no Safety Car, VSC or red flag; success means A is ahead of B two laps after B's stop. "
        "The definition was fixed before any outcome was computed. It is not the undercut rate."
    )
    grid = pl.DataFrame(undercut["grid"]).filter(
        pl.col("response_window_laps") == primary["response_window_laps"]
    )
    curve = (
        alt.Chart(grid.with_columns(
            pl.when(pl.col("exclude_neutralised")).then(pl.lit("neutralised laps excluded"))
            .otherwise(pl.lit("neutralised laps included")).alias("treatment")).to_pandas())
        .mark_line(point=True)
        .encode(x=alt.X("gap_threshold_s:Q", title="Largest starting gap allowed (s)"),
                y=alt.Y("success_rate:Q", title="Success rate", axis=alt.Axis(format="%"),
                        scale=alt.Scale(domain=[0, 1])),
                color="treatment:N",
                tooltip=["gap_threshold_s", "n_decided",
                         alt.Tooltip("success_rate:Q", format=".0%")])
        .properties(height=300)
    )
    st.altair_chart(curve, width="stretch")
    st.warning(
        "The starting gap moves the answer far more than anything else: the closer the two cars "
        "were, the more often A ended up ahead. The headline number is one point on this curve, "
        "not a stand-alone fact."
    )
    st.dataframe(pl.DataFrame(undercut["by_scope"]).select(
        "season_scope", "n_attempts", "n_success", "n_failure", "n_inconclusive", "n_sessions")
        .rename({"season_scope": "season"}), hide_index=True, width="stretch")
    st.caption(
        "Not controlled: pace difference between the cars, tyre compound and age, traffic, "
        "DRS and overtaking difficulty by circuit, team stop speed. A small sample. "
        "Full tables: docs/UNDERCUT-RESULTS.md in the repository."
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
        "- Three seasons (2023 to 2025); nothing here is a claim about other years or other "
        "regulations. Circuits repeat across seasons, which flatters leave-one-race-out.\n"
        "- The fuel effect (0.04 s per lap) is an assumption in the degradation figures.\n"
        "- Pit loss is an estimate; Safety Car and VSC figures use few stops and change sign "
        "between seasons.\n"
        "- The undercut rate is a frequency under one stated definition on a small sample; it "
        "depends strongly on the gap threshold and does not control for car pace.\n"
        "- Sessions whose stints disagree with their pit stops are left out of the tyre figures.\n"
        "- Track status comes from race-control message timestamps; edge laps are approximate.\n"
        "- Data come from the unofficial OpenF1 API; F1 and related marks belong to Formula One "
        "Licensing B.V. This project is not affiliated with Formula 1."
    )
