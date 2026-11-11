# ADR 0017: Widen the data to 2023 to 2025 and what changed

- Status: accepted
- Date: 2026-11-11

## Context
The first release covered one season, so every circuit appeared once and some conclusions rested on a
handful of races. 2023 and 2025 were added with the same pipeline (races and sprints, eight endpoints).
Completed 2026 sessions are not part of the analysis (the weekly schedule does ingest and validate the
current year into S3, but nothing loads or models them).

## Decisions
1. **Ingest:** 28 sessions for 2023 (the cancelled Imola race is skipped by `is_cancelled`), 30 for 2024
   and 30 for 2025, 88 in total. A full season on Lambda takes close to the 900 s limit: 2023 took 853 s
   in one invocation; 2025 took 866 s for 28 sessions and stopped early by design, and a second
   invocation finished the last 2 sessions in 40 s. Repeat runs wrote 0 objects in 5 to 6 s.
2. **Reconciliation:** all 88 sessions balance (raw = silver + quarantine). The bucket holds 1,678 objects,
   328.7 MB. Snowflake row counts equal the Parquet for all nine tables, and a repeat load staged and
   loaded 0 files. The Parquet written by the Lambda validator is identical to a local run for all 792
   silver and quarantine files.
3. **Stints and pit stops must agree (new, found on the wider data).** An existing dbt test failed on
   five 2025 sessions where fewer than 90% of ordinary pit stops fall on the last lap of a stint: Miami
   race (17%) and sprint (10%), Spa (77%), Monaco (88%) and the Lusail sprint (67% of 3 stops). In Miami
   several drivers share identical stint boundaries although their pit laps differ, so the stints
   endpoint looks wrong there; the cause was not investigated further. Every 2023 and 2024 session
   matched at least 94%. A session with at least 5 ordinary stops and under 90% matching is now left
   out of clean laps (`int_session_stint_check`); with fewer stops there is too little evidence, so the
   Lusail sprint is kept. The test now warns instead of failing, so the problem stays visible.
4. **Deprecated fields:** `pit.pit_duration` and `drivers.country_code` are documented as removed after the
   2026 season. They are optional in the schema check, and the long-stop rule uses `lane_duration`,
   so their removal would not quarantine every row.
5. **Model evaluation:** the same fixed settings were re-run on the pooled seasons, and a stricter
   leave-one-season-out check was added because circuits now repeat across seasons.

## Results that changed or need care (all from logged runs)
- **Lap-time model:** on 66 held-out races LightGBM beats the linear baseline by 0.150 s (95% interval
  -0.265 to -0.047), better in 47 of 66 races. The first season alone showed no detectable
  difference (23 races). Leave-one-season-out agrees in direction for all three seasons (LightGBM minus
  linear: -0.026, -0.018 and -0.130 s), but only the 2025 margin is large. Persistence still beats the
  linear baseline at Spielberg and Imola (2024 and 2025) and beats LightGBM at Imola 2024 and 2025 and
  Interlagos 2025; the cause is not investigated.
- **Degradation:** the fuel-corrected within-stint medians stay close to the assumed 0.04 s/lap:
  pooled SOFT +0.053, MEDIUM +0.045, HARD +0.028 s/lap, still mostly the assumption (the uncorrected
  medians are +0.013, +0.005 and -0.012).
- **Pit loss under Safety Car and VSC is not stable across seasons.** Medians of per-race medians: SC
  10.7 s (2024), 4.2 s (2025) and -3.9 s (2023); VSC 14.9 s, 10.4 s and 32.2 s. Green flag is stable
  at 22.9 to 23.2 s. A negative or larger-than-green value shows the estimator (in-lap plus out-lap
  minus two reference laps) is unreliable under neutralisation, so SC and VSC figures must be read as
  rough.
- **Stationary time (`stop_duration`)** is available for 721 of 842 stops in 2025 (none in 2023, 150 of
  810 in 2024).
- The pooled SC pit-loss figure mixes the seasons above and should not be quoted without them.

## Consequences
- The README and dashboard must report per-season and pooled figures, with these caveats.
- 2026 sessions are stored by the weekly schedule but not loaded or analysed. Nothing here is a claim
  about other regulations.
