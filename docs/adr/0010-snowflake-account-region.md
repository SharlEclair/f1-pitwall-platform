# ADR 0010: Snowflake account choice: Sydney first, us-west-2 as the fallback

- Status: accepted (keeps decision 2 of ADR 0001; adds a fallback)
- Date: 2026-11-11

## Context
There were two Snowflake trial accounts: one in AWS ap-southeast-2 (Sydney) showing a 30-day trial, and one in us-west-2 created through Snowflake's student sign-up link showing $400 credits and 119 days remaining (screenshots). The student link's eligibility rules were not verified. An earlier draft of this ADR chose us-west-2 for the longer trial; it was then pointed out that Sydney is better now, because the student trial's clock runs in parallel and everything is reproducible from code.

## Options considered
1. Sydney first - co-located with S3, no cross-region transfer, matches ADR 0001. The 30-day trial ends in week 4 of the project with little buffer.
2. us-west-2 first - about 120 days, but cross-region reads and a trial whose eligibility is unverified.

## Decision
Use the Sydney account now. The us-west-2 account is untouched and still counting down, so it is a free fallback. Switch if dbt is not passing on Snowflake by about day 12 of the Sydney trial. Switching means re-running `warehouse/01` and `02`, redoing the IAM trust handshake (SAM parameters), changing `SNOWFLAKE_ACCOUNT`, and a `--full-refresh` load.

## Consequences
Marts must be exported to Parquet well before the trial ends so the dashboard and Streamlit app survive it. How long Snowflake retains data after a trial ends is unverified. If we switch, ADR 0010 gets a new entry and the README's architecture diagram shows the region split.

## Evidence
Screenshots of the account switcher and trial banners. Transfer pricing and the student-trial terms are unverified.
