# Data quality design (the differentiator)

Most graduate pipelines load data and hope. This project's edge is that bad data is detected,
coded, counted, quarantined and reported, with a test set proving the rules fire.
It applies the coded-rule approach of earlier validation work.

## Principles

1. **Never silently drop.** Every rejected or flagged row has a rule code and a reason.
2. **Flag vs reject.** Some conditions are information (Safety Car laps), not errors.
3. **Rules are data.** A registry with id, severity, description, rationale, and a human-readable message.
4. **Every rule has a golden test:** a hand-labelled bad row it must catch, and a good row it must not.
5. **Measure the rules.** Track rows fired per rule per run; review noisy rules (precision matters).
6. **Reconcile.** raw count = silver + quarantine + explained exclusions; silver = Snowflake rows.

## Rule registry shape (sketch)

| Field | Example |
|---|---|
| code | `DQ-LAP-003` |
| entity | `lap` |
| severity | `reject` / `flag` / `warn` |
| description | lap_duration missing on a lap that is not pit-in/out or lap 1 |
| rationale | missing durations bias degradation fits |
| test fixtures | `tests/golden/DQ-LAP-003_bad.json`, `_good.json` |

## Candidate rules to start from (validate against real data in planning)

- null `lap_duration` that is not an expected exception (pit-in, pit-out, lap 1, red-flag laps)
- `lap_duration` outside a plausible band for that circuit/session
- duplicate `(session_key, driver_number, lap_number)`
- overlapping or non-contiguous stints; stint `lap_end < lap_start`
- tyre age decreasing within a stint
- compound missing or not in the known set
- one driver number mapped to two teams within a session
- laps under Safety Car / VSC / red flag: **flag**, do not drop
- schema drift: unexpected or missing fields in an API response
- freshness: expected session present but not ingested after N hours

## Layers of checking

| Layer | Tool | Purpose |
|---|---|---|
| Ingest | response schema + HTTP checks | detect API changes and gaps |
| Silver | rule registry (Python) | row-level coded validation + quarantine |
| Warehouse | dbt tests | unique, not_null, relationships, accepted_values, custom |
| Cross-layer | reconciliation queries | no unexplained row loss |
| Ops | SNS + DQ summary table | someone is told when it breaks |

## Deliverables

- `docs/DQ-CATALOGUE.md` (generated or maintained): every code, what it catches, rows fired per season.
- A DQ health page in the dashboard (rules fired, rows quarantined, freshness).
- A golden test suite that runs in CI.

## Questions for planning

- Which rules are real in OpenF1 data (look at actual data before inventing rules)?
- Where does quarantine live (S3 only, or also a Snowflake table for dashboarding)?
- Reject vs flag decision for each rule.
