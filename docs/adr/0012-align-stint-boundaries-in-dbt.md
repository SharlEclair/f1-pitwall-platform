# ADR 0012: Align stint boundaries in dbt using each race's own pit stops

- Status: accepted
- Date: 2026-11-11

## Context
In the OpenF1 pit endpoint `lap_number` is always the in-lap (the next lap is the out-lap; true for
all 27 sessions with pit stops, apart from one stop in Las Vegas). The stints endpoint is not consistent: in most races a stint ends on the pit lap, but in
Melbourne, Montreal and Monaco 2024 the next stint starts on the pit lap. Unhandled, tyre age is
one lap too high in those races and pit-ended (right-censored) stints are missed. dbt's own tests
passed anyway; the problem showed up only when comparing marts across races.

## Options considered
1. Hard-code the affected races - brittle and invisible when new races are added.
2. Detect the convention per race from its pit stops and shift stint boundaries in dbt.
3. Reject or flag the affected stints in the validator - discards good data and does not fix tyre age.

## Decision
Option 2 (`int_stints_aligned`), with a test (`assert_pit_laps_match_stint_ends`) that fails if any
race has fewer than 90% of ordinary pit stops landing on a stint end after alignment. The original
boundaries are kept in `fct_stints` as `source_lap_start` / `source_lap_end`.

## Consequences
New races are handled automatically, and a third convention would fail the test instead of passing
silently. A validator warn rule for this inconsistency would make it visible in the DQ catalogue;
not built yet. The detection assumes a race mostly follows one convention.

## Evidence
Measured over all 30 ingested 2024 sessions: detection selected exactly Melbourne, Montreal and
Monaco, and the test passes for all sessions on Snowflake. Not verified against other seasons.
