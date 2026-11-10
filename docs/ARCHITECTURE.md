# Rough target architecture

> Starting point from a pre-planning conversation. **Not final.** The planning session should
> challenge it, verify the facts it relies on, and record changes as ADRs.

```
OpenF1 API (historical, 2023+, free, no auth)
   |  Lambda #1 "ingest"  - EventBridge weekly schedule + manual backfill
   v
S3 raw/          immutable JSON, partitioned season/session_key/endpoint, ingest timestamp in path
   |  Lambda #2 "validate" (container image: Polars + rule registry)
   v
S3 silver/       Parquet, typed, validated
S3 quarantine/   failing rows + rule code + reason + source pointer
   |                         \
   |                          SNS email: run summary + any failures
   v
Snowflake        external stage via IAM storage integration, COPY INTO raw tables
   v
dbt              staging -> intermediate -> marts   (tests on every layer)
   v                                  \
Power BI dashboard                     MLflow (experiments; local tracking first)
(+ optional Streamlit on exported Parquet for a free public live link)
```

## Region and accounts

- AWS: ap-southeast-2 (Sydney). Snowflake: AWS ap-southeast-2 so the stage is co-located
  (Snowflake's region is fixed at signup and cannot be changed).
- Infrastructure as code: **AWS SAM** (one template; `sam delete` tears it down).
- CI auth to AWS: **GitHub OIDC**, no long-lived keys.

## Data scope

- Seasons 2023 onward (OpenF1 historical coverage). Start with 2024 race sessions (~24), widen later.
- Endpoints: `meetings`, `sessions`, `drivers`, `laps`, `stints`, `pit`, `weather`, `race_control`;
  `position` only for the stretch undercut mart.
- Excluded: `car_data`, `location` (huge, not needed).

## Layer contracts (to be formalised in planning)

| Layer | Grain | Rule |
|---|---|---|
| raw | one API response | never edited; reprocessable |
| silver | one typed row per entity | passes schema + rules, or is quarantined |
| quarantine | one failing row | rule code, severity, reason, pointer to raw |
| staging (dbt) | cleaned/typed 1:1 with source | no business logic |
| intermediate (dbt) | lap context (compound, tyre age, track status) | joins only |
| marts (dbt) | analytical facts | tested, documented, answers a question |

## Candidate marts

- `fct_laps`, `fct_stints`, `fct_pit_stops` (pit-loss estimate)
- `mart_tyre_degradation` (fuel-corrected; +0.04 s/lap from earlier F1 work is a
  *documented assumption*, to be re-justified; stints ended by a pit stop flagged as censored)
- `mart_undercut_events` (STRETCH: needs lap timing joined with `position`; do last)

## Idempotency and re-runs

Ingest keyed by session; re-run is a no-op unless the source changed. Loads use Snowflake
`COPY INTO` load history; dbt incremental models keyed by session. An off-season scheduled run
should do nothing and say so.

## CI that outlives the Snowflake trial

dbt runs in CI against `dbt-duckdb` over a small committed fixture (2-3 races), so the repo stays
verifiable after the 30-day trial ends. Keep SQL portable where feasible; document any dialect
differences. Snowflake `dbt build` is manual or nightly to save credits.

## Suggested repo layout (for the real repo; created during implementation)

```
infra/        SAM template, IAM policies
ingest/       Lambda 1 + tests
validate/     Lambda 2, rules/ registry + tests
warehouse/    idempotent Snowflake setup SQL
dbt/          models, tests, seeds, fixtures
ml/           training, evaluation, MLflow config
dashboard/    Power BI file, exported screenshots, optional streamlit/
docs/         architecture, ADRs, DQ catalogue, runbook, cost, limitations
.github/workflows/
```
