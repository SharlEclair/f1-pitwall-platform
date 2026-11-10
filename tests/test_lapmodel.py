import numpy as np
import polars as pl

from ml.lapmodel import (
    N_CAL,
    bootstrap_ci,
    build_examples,
    fit_b1,
    predict_b1,
    run_loro,
)


def synthetic_laps(n_races=5, drivers=3, laps=30, seed=0, noise=0.0):
    rng = np.random.default_rng(seed)
    rows = []
    for race in range(n_races):
        base = 80.0 + 3 * race
        for driver in range(drivers):
            for lap in range(2, laps + 2):
                age = lap - 1
                time = base + 0.05 * age - 0.03 * lap + rng.normal(0, noise)
                rows.append((race, f"C{race}", driver, lap, 1, "MEDIUM", age, time, 30.0, 25.0,
                             laps + 1))
    columns = ["session_key", "circuit_short_name", "driver_number", "lap_number", "stint_number",
               "compound", "tyre_age", "lap_duration", "track_temperature", "air_temperature",
               "race_laps"]
    return pl.DataFrame(rows, schema=columns, orient="row")


def test_calibration_laps_are_not_targets_and_use_only_first_laps():
    laps = synthetic_laps()
    examples = build_examples(laps)
    first = laps.filter((pl.col("session_key") == 0) & (pl.col("driver_number") == 0))
    calibration_laps = first.sort("lap_number").head(N_CAL)
    targets = examples.filter((pl.col("session_key") == 0) & (pl.col("driver_number") == 0))
    assert set(calibration_laps["lap_number"]).isdisjoint(set(targets["lap_number"]))
    assert targets["cal_median"][0] == calibration_laps["lap_duration"].median()


def test_changing_a_later_lap_does_not_change_calibration_stats():
    laps = synthetic_laps()
    changed = laps.with_columns(
        pl.when(pl.col("lap_number") == 25).then(500.0).otherwise(pl.col("lap_duration"))
        .alias("lap_duration")
    )
    a = build_examples(laps).sort(["session_key", "driver_number", "lap_number"])
    b = build_examples(changed).sort(["session_key", "driver_number", "lap_number"])
    assert a["cal_median"].to_list() == b["cal_median"].to_list()
    assert a["cal_age"].to_list() == b["cal_age"].to_list()


def test_b1_recovers_known_slopes_on_noiseless_data():
    examples = build_examples(synthetic_laps())
    coefficients = fit_b1(examples)
    assert abs(coefficients["age_slope_MEDIUM"] + coefficients["lap_slope"] - 0.02) < 1e-6
    predictions = predict_b1(coefficients, examples)
    assert np.abs(predictions - examples["lap_duration"].to_numpy()).max() < 1e-6


def test_loro_never_trains_on_the_held_out_race_and_b0_is_persistence():
    examples = build_examples(synthetic_laps(noise=0.05))
    folds, predictions = run_loro(examples)
    assert folds["session_key"].n_unique() == 5
    b0 = predictions.join(
        examples.select("session_key", "driver_number", "lap_number", "cal_median"),
        on=["session_key", "driver_number", "lap_number"],
    )
    assert (b0["pred_b0"] == b0["cal_median"]).all()
    # a trending signal must beat persistence on held-out races
    assert (folds["mae_b1"] < folds["mae_b0"]).all()


def test_bootstrap_is_deterministic_and_brackets_the_mean():
    values = [1.0, 2.0, 3.0, 4.0, 10.0]
    first = bootstrap_ci(values, seed=1)
    assert first == bootstrap_ci(values, seed=1)
    mean, low, high = first
    assert low <= mean <= high
