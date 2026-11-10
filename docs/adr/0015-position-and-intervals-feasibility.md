# ADR 0015: Ingest `position` and `intervals` for the undercut question (feasibility result)

- Status: proposed (accepted when the Phase 2 plan is approved)
- Date: 2026-11-11

## Context
Question 3 ("how often does an undercut work?") needs the race order at lap boundaries and the gap to the
car ahead. Neither endpoint is ingested yet. Before building anything, a sample was pulled for four 2024
races (Monza: no Safety Car; Melbourne: VSC only; Jeddah and Lusail: Safety Car) and checked against data
already in the platform. Raw responses stay outside the repository.

OpenF1's documentation describes `position` as "initial placement and subsequent changes" (an event
stream) and `intervals` as race-only, updated about every 4 seconds, with `interval` and `gap_to_leader`
that can be a number, null (race leader) or text such as "+1 LAP".

## What the sample showed (one logged run, 2026-11-11)
- **Size:** `position` 229 to 510 rows (26 to 58 KB) per race; `intervals` 20,242 to 21,328 rows
  (2.84 to 3.00 MB of JSON) per race. `intervals` is about 50 times larger than `position`.
- **Initial order:** in all four races the last event before lap 1 gives a clean permutation of 1..n for
  every driver who started (19 or 20 drivers).
- **Consistency:** no duplicate positions in 60-second wall-clock snapshots (0 of 75, 80, 81 and 91).
- **Independent check:** the position held at the start of a driver's next lap was compared with the
  order from cumulative lap times, for laps where both exist. They agree for 3,632 of 3,642 driver-laps
  (99.7%; per race 100%, 100%, 99.8%, 99.1%). The few disagreements were not investigated.
- **Retirements:** the stream stops for a retired car, which stays at the back; the official result has a
  null position for it.
- **Not the official classification:** for 5 classified finishers (3 in Melbourne, 2 in Jeddah) the last
  on-track position differs from `session_result`. Cause not investigated. Position is the on-track
  order, not the post-race classification.
- **Gap lookup:** at lap starts (3,774 lookups) an `intervals` value always existed before the lap start;
  41 (1.1%) were null for a car that was not leading, and 66 (1.7%) were older than 10 seconds.
- Per-driver `intervals` updates have a median spacing of 3.6 to 4.0 s but long gaps (maximum
  above 3,000 s) because the stream also covers the period before the race.
- Requests ran at 1 per second; no rate-limit responses were seen in 20 calls.

## Decision
1. Per-lap race order **can** be rebuilt from `position` and lap start times, and the gap to the car ahead
   from `intervals`. Proceed, with these rules: use `position` at the start of each lap as the order, use
   the latest `interval` within a stated maximum age as the gap, and treat missing or stale values as
   "gap unknown" (excluded from gap-based definitions, never imputed).
2. Add `position` and `intervals` to the ingest, with the same immutable content-hash storage, throttle and
   manifest as the other endpoints. Raw `intervals` is kept whole; later layers reduce it.
3. Keep the on-track order as the analysis basis and do not mix it with the official classification.
4. Measure again on the first full season before choosing the Lambda batch size: 2024's six-endpoint
   backfill took 583 s against a 900 s function limit, and `intervals` adds roughly 3 MB per session.

## Consequences
- Every layer (ingest, validation rules and golden tests, quarantine accounting, loader, dbt, CI fixture)
  changes. This is a milestone, not a column.
- The usable undercut sample is small. A rough, uncalibrated count of candidate pairs over the four sampled
  races found 9 to 11 depending on the gap threshold (2 to 3 per race, almost none in the two Safety Car
  races). This is not the frozen definition and not a rate.
- The sample covers four races of one season. Positions at red-flag restarts and during Safety Car
  periods were not examined beyond the above and are handled by exclusion in the undercut definition.

## Addendum: measured 2024 backfill (2026-11-11)
- **Ingest:** both endpoints added for all 30 sessions of 2024 on Lambda: 60 new raw objects in 202 s
  (wall time, including a cold start). A repeat run wrote 0 objects in 5 s. A local run of the same 60
  calls took 165.6 s, about 2.8 s per call, the same per-call rate as Phase 1's backfill (211 objects in
  583 s). A full season from scratch (30 sessions x 9 calls) is therefore estimated at about 750 s against
  the 900 s limit. This is an estimate, not a measurement. The handler now stops starting new sessions
  when under 90 s remain and reports `stopped_early`; completed sessions have manifests, so running it
  again finishes the rest.
- **Existing sessions:** a manifest written before an endpoint existed is completed by fetching only the
  missing endpoints; objects already stored are not refetched.
- **Storage:** the bucket went from 452 objects (17.4 MB) to 572 objects (111.4 MB), almost all of it
  `intervals`: 613,428 rows in 2024 against 11,930 for `position`.
- **Validation:** 30 of 30 sessions balance (raw = silver + quarantine, nothing quarantined for the
  new endpoints). The Lambda validator took 40.9 s and 213 MB (Phase 1: 16.7 to 19.0 s, 173 MB). The
  silver and quarantine Parquet from Lambda match a local run for all 270 files.
- **Rule calibration (the first versions were hypotheses):** DQ-POS-004 first flagged any duplicate
  position right after an update and fired on 166 rows, but all 87 such duplicates lasted under 5 s
  (two updates for one overtake arrive seconds apart); it now flags duplicates lasting over 10 s and
  fires on none. DQ-INT-003 (gap to leader below gap to the car ahead) fires on 1,106 of 613,428 rows,
  and 1,001 of them differ by more than 5 s, almost all in Baku and Singapore; they are flagged and kept,
  and gap-based analysis must treat them as unknown. The other new rules fired on no 2024 row.
- **Warehouse:** loaded through the internal stage (60 files); `POSITION` 11,930 and `INTERVALS` 613,428
  rows match the Parquet, and all nine tables reconcile. `dbt build` passes 75 of 75 on Snowflake and on
  DuckDB. Silver columns are named `race_position`, `interval_s` and `gap_to_leader_s` because POSITION
  and INTERVAL are SQL keywords. The DuckDB fixture for these two tables is synthetic, derived from the
  committed fixture laps, so no new row-level OpenF1 data is committed.
