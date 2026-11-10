"""Leave-one-race-out evaluation of clean-lap-time forecasts.

Task: for a held-out race, every method may use each driver's FIRST `N_CAL` clean laps (the
calibration window) and nothing else from that race, and must predict that driver's later clean
laps. Baselines and model therefore get identical information about the held-out race; the model
can additionally use what it learned from the other races.

  B0  persistence: predict the driver's calibration median for every later lap.
  B1  linear physics baseline: calibration median plus compound offsets, a per-compound tyre-age
      slope and a lap-number slope, fitted by least squares on the training races.
  GBM LightGBM on the same relative target (lap time minus calibration median).

Choices fixed before looking at any result: N_CAL, MIN_TARGETS, GBM_PARAMS, bootstrap settings.
"""

import numpy as np
import polars as pl
from lightgbm import LGBMRegressor

N_CAL = 5
MIN_TARGETS = 8
COMPOUNDS = ("SOFT", "MEDIUM", "HARD")
KEY = ["session_key", "driver_number"]

GBM_FEATURES = [
    "age_diff", "lap_diff", "tyre_age", "lap_number", "lap_frac", "stint_number",
    "track_temperature", "air_temperature", "cal_age", "cal_lap", "cal_median",
    "compound_code", "cal_compound_code",
]
GBM_PARAMS = dict(
    objective="regression_l1", n_estimators=300, learning_rate=0.05, num_leaves=15,
    min_child_samples=100, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
    reg_lambda=5.0, random_state=0, verbosity=-1, n_jobs=1, deterministic=True,
    force_row_wise=True,
)


def build_examples(laps, n_cal=N_CAL, min_targets=MIN_TARGETS):
    """One row per target lap, carrying statistics of that driver's calibration laps only."""
    ranked = laps.sort([*KEY, "lap_number"]).with_columns(
        pl.int_range(pl.len()).over(KEY).alias("rank")
    )
    calibration = (
        ranked.filter(pl.col("rank") < n_cal)
        .group_by(KEY)
        .agg(
            pl.col("lap_duration").median().alias("cal_median"),
            pl.col("lap_number").mean().alias("cal_lap"),
            pl.col("tyre_age").mean().alias("cal_age"),
            pl.col("compound").first().alias("cal_compound"),
            pl.len().alias("n_cal"),
        )
        .filter(pl.col("n_cal") == n_cal)
    )
    examples = ranked.filter(pl.col("rank") >= n_cal).join(calibration, on=KEY, how="inner")
    examples = examples.filter(pl.len().over(KEY) >= min_targets)
    return examples.with_columns(
        (pl.col("lap_duration") - pl.col("cal_median")).alias("delta"),
        (pl.col("tyre_age") - pl.col("cal_age")).alias("age_diff"),
        (pl.col("lap_number") - pl.col("cal_lap")).alias("lap_diff"),
        (pl.col("lap_number") / pl.col("race_laps")).alias("lap_frac"),
        pl.col("compound").replace_strict({c: i for i, c in enumerate(COMPOUNDS)}).alias(
            "compound_code"),
        pl.col("cal_compound").replace_strict({c: i for i, c in enumerate(COMPOUNDS)}).alias(
            "cal_compound_code"),
    )


def b1_design(examples):
    """Columns: target-compound intercepts, calibration-compound offsets, per-compound age slope,
    and one lap-number slope."""
    def flag(column, value):
        return (examples[column] == value).cast(pl.Float64).to_numpy()

    age = examples["age_diff"].to_numpy()
    names, columns = [], []
    for c in COMPOUNDS:
        names.append(f"intercept_{c}")
        columns.append(flag("compound", c))
    for c in COMPOUNDS[:-1]:
        names.append(f"cal_offset_{c}")
        columns.append(flag("cal_compound", c))
    for c in COMPOUNDS:
        names.append(f"age_slope_{c}")
        columns.append(flag("compound", c) * age)
    names.append("lap_slope")
    columns.append(examples["lap_diff"].to_numpy())
    return names, np.column_stack(columns)


def fit_b1(examples):
    names, design = b1_design(examples)
    coefficients, *_ = np.linalg.lstsq(design, examples["delta"].to_numpy(), rcond=None)
    return dict(zip(names, coefficients.tolist(), strict=True))


def predict_b1(coefficients, examples):
    names, design = b1_design(examples)
    return design @ np.array([coefficients[n] for n in names]) + examples["cal_median"].to_numpy()


def fit_gbm(examples):
    model = LGBMRegressor(**GBM_PARAMS)
    model.fit(examples.select(GBM_FEATURES).to_numpy(), examples["delta"].to_numpy())
    return model


def predict_gbm(model, examples):
    delta = model.predict(examples.select(GBM_FEATURES).to_numpy())
    return delta + examples["cal_median"].to_numpy()


def run_loro(examples):
    """Return (per-race results, per-lap predictions); the held-out race is never trained on."""
    races = sorted(examples["session_key"].unique().to_list())
    predictions = []
    for race in races:
        train = examples.filter(pl.col("session_key") != race)
        test = examples.filter(pl.col("session_key") == race)
        assert race not in set(train["session_key"].to_list())
        b1 = fit_b1(train)
        gbm = fit_gbm(train)
        predictions.append(test.select(
            "session_key", "season", "circuit_short_name", "driver_number", "lap_number",
            "compound",
            "lap_diff", pl.col("lap_duration").alias("actual"),
            pl.col("cal_median").alias("pred_b0"),
            pl.Series("pred_b1", predict_b1(b1, test)),
            pl.Series("pred_gbm", predict_gbm(gbm, test)),
        ))
    predictions = pl.concat(predictions)
    folds = (
        predictions.group_by("session_key", "season", "circuit_short_name")
        .agg(
            pl.len().alias("n_laps"),
            *[(pl.col(f"pred_{m}") - pl.col("actual")).abs().mean().alias(f"mae_{m}")
              for m in ("b0", "b1", "gbm")],
        )
        .sort("session_key")
    )
    return folds, predictions


def run_leave_one_season_out(examples):
    """Stricter check: train on all other seasons, score the held-out season (circuits repeat
    across seasons, so leave-one-race-out lets the model see the same circuit in another year).
    Returns one row per season; with only a few seasons no interval is meaningful."""
    rows = []
    for season in sorted(examples["season"].unique().to_list()):
        train = examples.filter(pl.col("season") != season)
        test = examples.filter(pl.col("season") == season)
        assert season not in set(train["season"].to_list())
        b1, gbm = fit_b1(train), fit_gbm(train)
        actual = test["lap_duration"].to_numpy()
        preds = {"b0": test["cal_median"].to_numpy(), "b1": predict_b1(b1, test),
                 "gbm": predict_gbm(gbm, test)}
        rows.append({"season": season, "n_laps": test.height,
                     **{f"mae_{m}": float(np.abs(p - actual).mean()) for m, p in preds.items()}})
    return pl.DataFrame(rows)


def bootstrap_ci(values, n_boot=2000, seed=0, alpha=0.05):
    """Mean and percentile interval when resampling the values (races) with replacement."""
    values = np.asarray(values, dtype=float)
    rng = np.random.default_rng(seed)
    means = values[rng.integers(0, len(values), size=(n_boot, len(values)))].mean(axis=1)
    low, high = np.quantile(means, [alpha / 2, 1 - alpha / 2])
    return float(values.mean()), float(low), float(high)


def estimate_effects(examples, n_boot=500, seed=0):
    """Fit B1 on resampled races: the lap-number slope (net of tyre age) and tyre-age slopes.

    The lap-number slope is fuel burn plus track evolution plus anything else that changes with
    race progress, not fuel alone.
    """
    races = np.array(sorted(examples["session_key"].unique().to_list()))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        chosen = rng.choice(races, size=len(races), replace=True)
        sample = pl.concat([examples.filter(pl.col("session_key") == r) for r in chosen])
        draws.append(fit_b1(sample))
    point = fit_b1(examples)
    return {
        name: (point[name], *np.quantile([d[name] for d in draws], [0.025, 0.975]).tolist())
        for name in point
    }
