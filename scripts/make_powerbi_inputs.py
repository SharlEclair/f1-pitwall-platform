"""Flatten the dashboard's aggregated data into plain CSV tables that Power BI imports directly.

Reads dashboard/data (committed, aggregated; no row-level lap data) and writes
dashboard/powerbi/data/*.csv. Usage: python scripts/make_powerbi_inputs.py
"""

import json
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "dashboard" / "data"
TARGET = ROOT / "dashboard" / "powerbi" / "data"
METHODS = {"b0": "B0 persistence", "b1": "B1 linear physics", "gbm": "LightGBM"}


def main():
    TARGET.mkdir(parents=True, exist_ok=True)
    for name in ("mart_tyre_degradation", "mart_pit_loss", "mart_dq_health"):
        pl.read_parquet(SOURCE / f"{name}.parquet").write_csv(TARGET / f"{name}.csv")

    model = json.loads((SOURCE / "ml_results.json").read_text())
    results, effects = model["results"], model["effects"]

    pl.DataFrame([
        {"method": label, "mean_mae_s": results["race_mae"][key][0],
         "ci_low_s": results["race_mae"][key][1], "ci_high_s": results["race_mae"][key][2],
         "all_laps_mae_s": results["lap_mae"][key]}
        for key, label in METHODS.items()
    ]).write_csv(TARGET / "model_summary.csv")

    pl.DataFrame(results["folds"]).select(
        "session_key", "circuit_short_name", "n_laps", "mae_b0", "mae_b1", "mae_gbm"
    ).write_csv(TARGET / "model_by_race.csv")
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
    print("wrote", ", ".join(sorted(p.name for p in TARGET.glob("*.csv"))))


if __name__ == "__main__":
    main()
