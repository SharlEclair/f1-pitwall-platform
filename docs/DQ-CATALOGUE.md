# Data-quality catalogue

Generated from a measured run over 88 sessions (2023 to 2025) (validation took 74.9 s locally). Re-generate with `python -m validate.catalogue`.

## Reconciliation (raw = silver + quarantine)

| Endpoint | Raw rows | Silver | Quarantined |
|---|---|---|---|
| drivers | 1756 | 1756 | 0 |
| intervals | 1812781 | 1812781 | 0 |
| laps | 84140 | 84122 | 18 |
| pit | 2449 | 2449 | 0 |
| position | 37778 | 37778 | 0 |
| race_control | 7193 | 7193 | 0 |
| stints | 4472 | 4433 | 39 |
| weather | 12674 | 12674 | 0 |

All sessions balanced: True.

## Rules

| Code | Severity | Catches | Rows fired | Out of | Largest sessions | Review note |
|---|---|---|---|---|---|---|
| DQ-API-001 | reject | Row is missing a field the endpoint is expected to return | 0 | 1963243 rows | - |  |
| DQ-API-002 | warn | Row has a field that is not in the expected schema | 0 | 1963243 rows | - |  |
| DQ-LAP-001 | reject | Duplicate (session, driver, lap_number) | 0 | 84140 laps | - |  |
| DQ-LAP-002 | reject | Null lap_duration that is not lap 1, a red-flag lap or the driver's last recorded lap | 1 | 84140 laps | Suzuka 2024 (Race) 1 | Not an expected exception; reviewed individually, it is on the same lap as the DQ-LAP-004 flags in that race (the lap after a red-flag restart). |
| DQ-LAP-003 | flag | Null lap_duration on lap 1, a red-flag lap or the driver's last recorded lap | 302 | 84140 laps | Monte Carlo 2024 (Race) 20, Monza 2023 (Race) 20, Melbourne 2023 (Race) 13 | Expected nulls: lap 1, red-flag laps and retirement laps. Kept visible, not rejected. |
| DQ-LAP-004 | flag | Green-flag, non-pit lap slower than 1.3x the session median | 270 | 84140 laps | Monte Carlo 2023 (Race) 76, Spa-Francorchamps 2025 (Race) 60, Zandvoort 2023 (Race) 41 | Remaining flags are mostly one pattern: the lap after a red-flag restart, which no race-control message explains. Left flagged on purpose (no rule tuned to one race). Track status uses message timestamps, with one typical lap added after SC and restart messages. |
| DQ-LAP-005 | reject | Sector times differ from lap_duration by more than 0.05 s | 17 | 84140 laps | Las Vegas 2024 (Race) 17 | Concentrated in a single race with a near-constant gap, which points to a systematic timing artifact rather than random bad rows. Severity is reject; revisit if the ML target loses too many laps. |
| DQ-STINT-001 | reject | Stint ends before it starts, or leaves a gap or overlap with the previous stint | 38 | 4472 stints | Monte Carlo 2024 (Race) 16, Melbourne 2023 (Race) 8, Melbourne 2025 (Race) 6 | Zero-length stints created by tyre changes under a red flag. |
| DQ-STINT-002 | flag | Driver's last stint ends on a different lap from their last recorded lap | 211 | 4472 stints | Monza 2023 (Race) 19, Melbourne 2023 (Race) 10, Miami 2025 (Sprint) 9 | Final stint ends one lap away from the driver's last recorded lap, in both directions. |
| DQ-STINT-003 | reject | Compound is missing or not one of SOFT, MEDIUM, HARD, INTERMEDIATE, WET, UNKNOWN | 1 | 4472 stints | Austin 2025 (Sprint) 1 |  |
| DQ-STINT-004 | flag | Compound is UNKNOWN | 2 | 4472 stints | Lusail 2024 (Race) 2 |  |
| DQ-PIT-001 | flag | pit_duration over 60 s | 129 | 2449 pit stops | Interlagos 2025 (Sprint) 19, Suzuka 2024 (Race) 18, Mexico City 2023 (Race) 18 | Red-flag waits plus a few isolated long stops. Excluded from pit-loss estimates. |
| DQ-PIT-002 | warn | stop_duration is null | 1571 | 2449 pit stops | Zandvoort 2023 (Race) 101, Interlagos 2023 (Race) 67, Spielberg 2023 (Race) 63 | Stationary time is published only for the last races of 2024 (ADR 0004). |
| DQ-POS-001 | reject | Position is not a whole number from 1 to 22 | 0 | 37778 position rows | - |  |
| DQ-POS-002 | reject | More than one position row for the same driver at the same timestamp | 0 | 37778 position rows | - |  |
| DQ-POS-003 | reject | Driver number is not in the session's drivers | 0 | 37778 position rows | - |  |
| DQ-POS-004 | flag | Two or more drivers hold the same position for more than 10 s | 18 | 37778 position rows | Mexico City 2025 (Race) 18 | Calibrated on 2024: a first version flagged any duplicate at once; two updates for one overtake land seconds apart, so a short duplicate is normal. Only a duplicate lasting over 10 s is flagged. |
| DQ-INT-001 | reject | interval or gap_to_leader is not a number, null or text like '+1 LAP' | 0 | 1812781 interval rows | - |  |
| DQ-INT-002 | reject | interval or gap_to_leader is negative | 0 | 1812781 interval rows | - |  |
| DQ-INT-003 | flag | gap_to_leader is smaller than interval | 1297 | 1812781 interval rows | Singapore 2024 (Race) 510, Baku 2024 (Race) 487, Monza 2024 (Race) 33 | Not rounding: the differences are mostly tens of seconds and sit in two races (Baku, Singapore). Flagged and kept; gap-based analysis must treat flagged rows as unknown. |
| DQ-SESS-001 | reject | Driver number is mapped to more than one team in a session | 0 | 1756 driver rows | - |  |
| DQ-SESS-002 | warn | Endpoint returned no rows for a finished session | 13 | 88 sessions | Spa-Francorchamps 2025 (Sprint) 1, Interlagos 2024 (Sprint) 1, Austin 2024 (Sprint) 1 | Sprints with no pit stops; plausible rather than a data gap. |
| DQ-FRESH-001 | warn | Finished session has not been ingested after the allowed delay | n/a | 88 sessions | - |  |

DQ-FRESH-001 is evaluated by the scheduled validator against the sessions listing, not per session, so it has no row count here.
