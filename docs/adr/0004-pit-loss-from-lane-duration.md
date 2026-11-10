# ADR 0004: Pit-loss analysis uses lane duration for 2024

- Status: accepted
- Date: 2026-11-10

## Context
In the `pit` endpoint `pit_duration` equals `lane_duration` (pit-lane transit). `stop_duration` (stationary time) is mostly null in 2024: across the full 2024 backfill it is set on 151 of 865 stops, only in Austin, Mexico City, Interlagos, Las Vegas, Lusail (race and sprint) and Yas Marina. It is populated in a 2025 session sampled (25 of 27). This ADR first said "null for every 2024 row" after sampling two races; the full backfill showed that was wrong. Under the Monaco 2024 red flag, `pit_duration` reached about 2390 s; 55 of 865 stops exceed 60 s (red-flag races plus single cases in Sakhir, Jeddah, Montreal and Shanghai).

## Decision
Pit loss is estimated from lane time and lap-time deltas for every race, so the series is consistent. Stationary time is used only as a supplementary measure for the late-2024 races that have it. Stops over 60 s are flagged (`DQ-PIT-001`) and excluded from loss estimates. `DQ-PIT-002` records null `stop_duration` as a warn. The README states this limitation.

## Consequences
Pit-loss estimates are lane-based and not comparable to stationary-time figures elsewhere. Widening to 2025 would add more stationary-time data.

## Evidence
Measured over all 30 ingested 2024 race and sprint sessions (data in the private S3 bucket); the 55-stop and 151-stop counts come from that run.
