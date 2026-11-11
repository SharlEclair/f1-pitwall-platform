"""Flatten the dashboard's aggregated data into plain CSV tables that Power BI imports directly.

Reads dashboard/data (committed, aggregated; no row-level lap data) and writes
dashboard/powerbi/data/*.csv. Usage: python scripts/make_powerbi_inputs.py
"""

import json
import sys
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dashboard" / "data"
TARGET = ROOT / "dashboard" / "powerbi" / "data"
METHODS = {"b0": "B0 persistence", "b1": "B1 linear physics", "gbm": "LightGBM"}
sys.path.insert(0, str(ROOT / "src"))


def write_dimensions_and_extras(results):
    """Dimension tables, per-season pit loss, the undercut tables and rule descriptions."""
    from validate.rules import RULES

    sessions = pl.read_csv(ROOT / "dbt" / "seeds" / "sessions.csv").with_columns(
        pl.col("session_key").cast(pl.Utf8), pl.col("year").alias("season"))
    dim_race = sessions.select(
        "session_key", "season", "circuit_short_name", "session_name", "race_date"
    ).with_columns(
        (pl.col("circuit_short_name") + " " + pl.col("season").cast(pl.Utf8)
         + pl.when(pl.col("session_name") == "Sprint").then(pl.lit(" (Sprint)"))
         .otherwise(pl.lit(""))).alias("race_label")
    ).sort("race_date")
    dim_race.write_csv(TARGET / "dim_race.csv")
    pl.DataFrame({"season": sorted(dim_race["season"].unique().to_list())}).write_csv(
        TARGET / "dim_season.csv")
    pl.DataFrame([{"rule_code": r.code, "severity": r.severity, "entity": r.entity,
                   "description": r.description} for r in RULES]).write_csv(
        TARGET / "dim_rule.csv")

    pit = pl.read_parquet(SOURCE / "mart_pit_loss.parquet").filter(
        pl.col("median_pit_loss_s").is_not_null())
    pit.group_by("season", "track_status").agg(
        pl.col("median_pit_loss_s").median().alias("median_pit_loss_s"),
        pl.col("n_stops_with_loss").sum().alias("stops"), pl.len().alias("races"),
    ).sort("season", "track_status").write_csv(TARGET / "pit_loss_by_season.csv")

    undercut = json.loads((SOURCE / "undercut_results.json").read_text())
    pl.DataFrame(undercut["grid"]).with_columns(
        pl.when(pl.col("exclude_neutralised")).then(pl.lit("Neutralised laps excluded"))
        .otherwise(pl.lit("Neutralised laps included")).alias("treatment")
    ).write_csv(TARGET / "undercut_grid.csv")
    pl.DataFrame(undercut["by_scope"]).write_csv(TARGET / "undercut_by_season.csv")
    boot = undercut["bootstrap_over_races"]
    pl.DataFrame([{"gap_threshold_s": undercut["primary"]["gap_threshold_s"],
                   "response_window_laps": undercut["primary"]["response_window_laps"],
                   "rate": boot["rate"], "ci_low": boot["low"], "ci_high": boot["high"],
                   "n_races": boot["n_races"]}]).write_csv(TARGET / "undercut_primary.csv")


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in ("mart_tyre_degradation", "mart_pit_loss", "mart_dq_health"):
        pl.read_parquet(SOURCE / f"{name}.parquet").with_columns(
            pl.col("session_key").cast(pl.Utf8)).write_csv(TARGET / f"{name}.csv")

    model = json.loads((SOURCE / "ml_results.json").read_text())
    results, effects = model["results"], model["effects"]

    pl.DataFrame([
        {"method": label, "mean_mae_s": results["race_mae"][key][0],
         "ci_low_s": results["race_mae"][key][1], "ci_high_s": results["race_mae"][key][2],
         "all_laps_mae_s": results["lap_mae"][key]}
        for key, label in METHODS.items()
    ]).write_csv(TARGET / "model_summary.csv")

    pl.DataFrame(results["folds"]).select(
        "session_key", "season", "circuit_short_name", "n_laps", "mae_b0", "mae_b1", "mae_gbm"
    ).with_columns(pl.col("session_key").cast(pl.Utf8)).write_csv(TARGET / "model_by_race.csv")
    pl.DataFrame(results["by_season_out"]).write_csv(TARGET / "model_by_season_out.csv")
    pl.DataFrame(results["by_compound"]).write_csv(TARGET / "model_by_compound.csv")
    pl.DataFrame(results["by_horizon"]).write_csv(TARGET / "model_by_horizon.csv")

    pl.DataFrame([
        {"effect": name, "estimate_s_per_lap": value[0], "ci_low": value[1], "ci_high": value[2]}
        for name, value in effects.items() if name in
        ("lap_slope", "age_slope_SOFT", "age_slope_MEDIUM", "age_slope_HARD")
    ]).with_columns(
        pl.lit(model["assumed_fuel_effect"]).alias("assumed_fuel_effect_s_per_lap")
    ).write_csv(TARGET / "model_effects.csv")

    pl.DataFrame([
        {"comparison": "LightGBM minus B1", "mean_diff_s": results["diff_gbm_b1"][0],
         "ci_low_s": results["diff_gbm_b1"][1], "ci_high_s": results["diff_gbm_b1"][2],
         "races_better": results["races_gbm_better_than_b1"], "n_races": results["n_races"]},
        {"comparison": "LightGBM minus B0", "mean_diff_s": results["diff_gbm_b0"][0],
         "ci_low_s": results["diff_gbm_b0"][1], "ci_high_s": results["diff_gbm_b0"][2],
         "races_better": results["races_gbm_better_than_b0"], "n_races": results["n_races"]},
    ]).write_csv(TARGET / "model_paired_differences.csv")
    write_dimensions_and_extras(results)
    print("wrote", ", ".join(sorted(p.name for p in TARGET.glob("*.csv"))))


if __name__ == "__main__":
    main()
