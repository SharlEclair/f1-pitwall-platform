# ADR 0006: Quarantine lives in S3 and is mirrored to Snowflake

- Status: accepted
- Date: 2026-11-10

## Decision
S3 `quarantine/` is the source of truth (rule code, severity, reason, source pointer). A Snowflake quarantine table is loaded with `COPY INTO` so the dashboard's DQ page can show rules fired and rows quarantined.

## Consequences
Reconciliation covers raw = silver + quarantine + explained exclusions, and silver = Snowflake rows. One more table to load and keep after the trial ends (exported to Parquet for Streamlit).

## Evidence
Design choice, no external facts involved.
