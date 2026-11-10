# ADR 0007: dbt version pins and DuckDB portability policy

- Status: accepted (M0 install test passed 2026-11-10 on Python 3.13.2: dbt-core 1.12.6, dbt-snowflake 1.12.5, dbt-duckdb 1.11.1; `dbt debug` OK on DuckDB. Snowflake connection untested until M3. dbt printed a notice that dbt Core v2 exists and is the default for new installs; we stay on v1.12.x deliberately because the adapters are v1.)
- Date: 2026-11-10

## Context
PyPI on 2026-11-10: dbt-core 1.12.6, dbt-snowflake 1.12.5 (needs dbt-core >=1.10,<2.0), dbt-duckdb 1.11.1 (needs dbt-core >=1.8). Local Python is 3.13.2; all three declare support for >=3.10. Python 3.13 compatibility of the full set is not yet tested.

## Decision
Install the latest of each into the project `.venv` in M0, run `dbt debug` against DuckDB, then pin exact versions in a requirements lock. If 3.13 fails, use Python 3.12. SQL is written portable first; Snowflake-only constructs go behind adapter macros and are listed in the docs. CI runs DuckDB; Snowflake `dbt build` is manual or nightly.

## Consequences
Small dialect differences are accepted if documented and the CI fixture still exercises every model.

## Evidence
Versions read from PyPI metadata (measured). Compatibility is unverified until M0.
