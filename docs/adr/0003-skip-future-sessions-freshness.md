# ADR 0003: Ingest skips sessions that have not finished; freshness is a rule

- Status: accepted
- Date: 2026-11-10

## Context
The OpenF1 `sessions` endpoint lists future sessions (2026 showed 25 race sessions, last on 2026-12-06, as of 2026-11-10). Fetching them would store empty or partial data and look like a data-quality failure.

## Decision
Ingest only sessions whose `date_end` is in the past. A completed session with no ingested data after N hours raises `DQ-FRESH-001` (warn). An off-season run does nothing and says so in the SNS summary. N is set in M1.

## Consequences
"Not yet run" and "missing data" are distinguishable. A session cursor is needed.

## Evidence
Observed in a live API call on 2026-11-10 (measured). Behaviour for corrected or late data is unverified; M1 samples it.
