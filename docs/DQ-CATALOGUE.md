# Data-quality catalogue

Generated from a measured run over 30 sessions of 2024 (validation took 3.5 s locally). Re-generate with `python -m validate.catalogue`.

## Reconciliation (raw = silver + quarantine)

| Endpoint | Raw rows | Silver | Quarantined |
|---|---|---|---|
| laps | 29052 | 29034 | 18 |
| stints | 1469 | 1453 | 16 |
| pit | 865 | 865 | 0 |
| drivers | 599 | 599 | 0 |
| race_control | 2373 | 2373 | 0 |
| weather | 4161 | 4161 | 0 |

All sessions balanced: True.

## Rules

| Code | Severity | Catches | Rows fired | Out of | Largest sessions | Review note |
|---|---|---|---|---|---|---|
| DQ-API-001 | reject | Row is missing a field the endpoint is expected to return | 0 | 38519 rows | - |  |
| DQ-API-002 | warn | Row has a field that is not in the expected schema | 0 | 38519 rows | - |  |
| DQ-LAP-001 | reject | Duplicate (session, driver, lap_number) | 0 | 29052 laps | - |  |
| DQ-LAP-002 | reject | Null lap_duration that is not lap 1, a red-flag lap or the driver's last recorded lap | 1 | 29052 laps | Suzuka (Race) 1 | Not an expected exception; reviewed individually, it is on the same lap as the DQ-LAP-004 flags in that race (the lap after a red-flag restart). |
| DQ-LAP-003 | flag | Null lap_duration on lap 1, a red-flag lap or the driver's last recorded lap | 99 | 29052 laps | Monte Carlo (Race) 20, Interlagos (Sprint) 7, Baku (Race) 6 | Expected nulls: lap 1, red-flag laps and retirement laps. Kept visible, not rejected. |
| DQ-LAP-004 | flag | Green-flag, non-pit lap slower than 1.3x the session median | 23 | 29052 laps | Suzuka (Race) 17, Yas Marina Circuit (Race) 1, Interlagos (Race) 1 | Remaining flags are mostly one pattern: the lap after a red-flag restart, which no race-control message explains. Left flagged on purpose (no rule tuned to one race). Track status uses message timestamps, with one typical lap added after SC and restart messages. |
| DQ-LAP-005 | reject | Sector times differ from lap_duration by more than 0.05 s | 17 | 29052 laps | Las Vegas (Race) 17 | Concentrated in a single race with a near-constant gap, which points to a systematic timing artifact rather than random bad rows. Severity is reject; revisit if the ML target loses too many laps. |
| DQ-STINT-001 | reject | Stint ends before it starts, or leaves a gap or overlap with the previous stint | 16 | 1469 stints | Monte Carlo (Race) 16 | Zero-length stints created by tyre changes under a red flag. |
| DQ-STINT-002 | flag | Driver's last stint ends on a different lap from their last recorded lap | 53 | 1469 stints | Lusail (Race) 5, Spa-Francorchamps (Race) 5, Montreal (Race) 5 | Final stint ends one lap away from the driver's last recorded lap, in both directions. |
| DQ-STINT-003 | reject | Compound is missing or not one of SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN | 0 | 1469 stints | - |  |
| DQ-STINT-004 | flag | Compound is UNKNOWN | 2 | 1469 stints | Lusail (Race) 2 |  |
| DQ-PIT-001 | flag | pit_duration over 60 s | 55 | 865 pit stops | Suzuka (Race) 18, Interlagos (Race) 17, Monte Carlo (Race) 16 | Red-flag waits plus a few isolated long stops. Excluded from pit-loss estimates. |
| DQ-PIT-002 | warn | stop_duration is null | 714 | 865 pit stops | Suzuka (Race) 54, Silverstone (Race) 45, Spielberg (Race) 45 | Stationary time is published only for the last races of 2024 (ADR 0004). |
| DQ-SESS-001 | reject | Driver number is mapped to more than one team in a session | 0 | 599 driver rows | - |  |
| DQ-SESS-002 | warn | Endpoint returned no rows for a finished session | 3 | 30 sessions | Interlagos (Sprint) 1, Austin (Sprint) 1, Spielberg (Sprint) 1 | Sprints with no pit stops; plausible rather than a data gap. |
| DQ-FRESH-001 | warn | Finished session has not been ingested after the allowed delay | n/a | 30 sessions | - |  |

DQ-FRESH-001 is evaluated by the scheduled validator against the sessions listing, not per session, so it has no row count here.
