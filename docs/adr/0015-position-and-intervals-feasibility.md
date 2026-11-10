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
