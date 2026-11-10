# ML plan (baseline-first, evaluated honestly)

## Purpose

Show disciplined ML practice and MLflow experiment tracking, not chase a headline accuracy.
A model that does not beat its baseline is a valid, publishable finding.

## Task

Predict **clean race-lap time**. Exclude pit-in/out laps, lap 1, Safety Car / VSC / red-flag laps,
and rows quarantined by the DQ layer. (Definition to be confirmed in planning.)

## Baseline(s) first

- B0: per-driver, per-stint median lap time.
- B1: per-driver, per-stint linear degradation (lap time vs tyre age, fuel-corrected).
A model is only interesting if it beats B1.

## Candidate models

- Gradient boosting (LightGBM; familiar).
- Optional: simple mixed-effects model (random intercepts for driver/circuit) as an interpretable comparison.

## Features (to refine in planning)

tyre age, compound, fuel-load proxy (lap number / race laps), track temperature, air temperature,
circuit, driver, team, position/traffic proxy (stretch), stint number. Beware leakage: no feature may
use information from laps after the one being predicted.

## Validation

- **Leave-one-race-out cross-validation** (group by race). Never a random row split: laps within a
  race are highly correlated and a random split leaks.
- Metric: MAE in seconds, plus per-compound and per-circuit breakdown; report distribution across
  held-out races, not only the mean. Bootstrap CI over races.
- State the denominator (n races, n laps) in every reported number.

## MLflow

- Start with local file-based tracking (no cost, no infra). Optionally log artifacts to S3 later.
- Log: params, data version/hash (which sessions), metrics per fold, plots, feature importances.
- Keep a results table that one command regenerates.

## Link to the existing F1 Strategy Engine

- The platform's marts give the engine a reproducible data source.
- Stretch: compute the historical undercut base rate across races to provide the missing baseline
  for the Monza 53.77% claim. This needs lap timing joined to `position` data and is the fiddliest
  mart; do it last and be explicit about its assumptions.

## Known traps to document (from earlier work)

- **Fuel burn masks degradation:** old tyres look faster because the car is lighter. The earlier
  project used +0.04 s/lap; re-justify or estimate it from data here.
- **Right-censoring:** teams pit before the tyre cliff, so stint length is not tyre life.
  Do not treat every pit stop as a failure event.
- **Dirty air:** laps behind another car are slower for non-tyre reasons.

## Not in scope

Race-winner prediction, betting, deep learning, hyperparameter marathons.
