# dbt project

Models on Snowflake (`--target snowflake`) and on DuckDB over a committed fixture
(`--target duckdb`, the default, used by CI). Run from this folder:

```powershell
..\.venv\Scripts\dbt.exe deps --profiles-dir .
..\.venv\Scripts\dbt.exe build --profiles-dir . --target duckdb
```

Snowflake needs `SNOWFLAKE_ACCOUNT`, `SNOWFLAKE_USER` and `SNOWFLAKE_PRIVATE_KEY_PATH` set locally
(key-pair login, no password in any file).

## Layers

| Layer | Models | Rule |
|---|---|---|
| staging (views) | `stg_*` | 1:1 with the loaded tables, no business logic |
| intermediate (views) | `int_stints_aligned`, `int_lap_context` | joins and alignment only |
| marts (tables) | `fct_laps`, `fct_stints`, `fct_pit_stops`, `mart_tyre_degradation`, `mart_pit_loss`, `mart_dq_health` | tested, each tied to a question |

`mart_tyre_degradation` answers question 1, `mart_pit_loss` question 2, `fct_laps.is_clean_lap` is
the base for question 4 (the lap-time model), `mart_dq_health` feeds the dashboard's data-quality
page. Question 3 (undercut base rate) is deferred.

## Snowflake and DuckDB differences (kept small on purpose)

- `dq_flags` is a Snowflake ARRAY and a DuckDB LIST: the macros `has_flag` and `no_flags` in
  `macros/portability.sql` are the only place that differs.
- DuckDB reads sources from `fixtures/raw/*.parquet` through the `external_location` source
  setting; Snowflake reads schema `RAW`. The model SQL is identical.
- No `ASOF JOIN` (syntax differs): weather is matched with a join plus `QUALIFY row_number()`.
- Shared constructs that behave the same on both: `median`, `covar_samp`, `var_samp`, `QUALIFY`,
  `avg(...) over (partition by ...)`.
- Named windows (`WINDOW w AS (...)` / `OVER w`) work on DuckDB but not on Snowflake: spell the
  window out in each expression. A DuckDB-only CI would not have caught this.
- Timestamps display in UTC on DuckDB; the Python loader pins Snowflake sessions to UTC. dbt on
  Snowflake does not set a session timezone, so avoid date arithmetic that depends on it.

## Assumptions and limits (read before quoting any number)

- **Fuel effect is an assumption.** `fuel_effect_s_per_lap = 0.04` (dbt_project.yml) is carried
  over from earlier work. The fuel-corrected degradation slope is largely the uncorrected slope
  plus that assumption, so the corrected values say little until the effect is estimated from data
  (planned in M5). The uncorrected slope is the data's own evidence.
- **Stint boundaries are aligned per race** (ADR 0012). A test fails if a race still has fewer
  than 90% of ordinary pit stops landing on a stint end.
- **Pit loss is an estimate** (in-lap + out-lap minus two reference laps) and is only computed when
  both laps share a track status. Stops over 60 s are excluded from the mart.
- **Track status** comes from race-control timestamps with an added typical lap after SC and
  restart messages (see the validator); edge laps are approximate.
- Degradation slopes need at least 10 clean laps and 3 distinct tyre ages; sparse groups
  (for example one soft-tyre stint) are not reported.
- **Estimator.** `slope_s_per_lap` is a within-stint (fixed-effects) fit; `slope_pooled_s_per_lap`
  is the simpler pooled fit. Across 2024 they differ by more than 0.02 s/lap in 18 of 67
  race-compound fits, so the choice matters as much as the fuel assumption. On Monza the pooled
  fit equals an earlier independent project's (MEDIUM 0.0234, HARD 0.0423 s/lap with the same
  laps and the same 0.04 assumption).
- The lap-time model (`docs/ML-RESULTS.md`) estimates tyre-age and lap-number effects jointly: the
  lap-number effect is -0.038 s per lap (95% CI -0.052 to -0.027), close to the assumed 0.04, but
  the MEDIUM and HARD tyre-age slopes have intervals that include zero. Treat the mart's slopes
  as descriptive, not as precise per-compound degradation rates.
- Both slopes are still conditional on the fuel assumption; some races (Monaco) show negative
  slopes because the track gets faster as rubber is laid down, which a per-stint fit does not model.

## Verified on 2026-11-11

`dbt build` passed on both targets: 63 of 63 (1 seed, 16 models, 46 data tests), on Snowflake in
about 35 seconds. The Monza degradation values in the mart match a separate hand computation on the
same laps. Snowflake credits used in total so far (loads, builds, checks): 0.12 of the 10 allowed.
