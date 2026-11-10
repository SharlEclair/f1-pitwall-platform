# ADR 0005: Data-quality severities: reject, flag, warn

- Status: accepted (severities provisional until precision is measured in M2)
- Date: 2026-11-10

## Context
Some anomalies are errors; others are real race events (red flag, pit-out laps, retirements).

## Decision
- **reject**: row cannot be trusted (duplicate key, schema drift, sector sum mismatch, stint gap). Goes to quarantine with rule code, reason and raw pointer.
- **flag**: row kept in silver with a flag column (red-flag lap 1 null duration, over-long pit duration, truncated final stint). Never silently dropped.
- **warn**: reported in the run summary only (null `stop_duration`, freshness).
Starter rules are in `docs/PLAN.md`, each tied to a real observation or marked "guard". Every rule needs a good and a bad golden fixture.

## Consequences
The ML target excludes quarantined and flagged rows, so rule changes affect the target; counts and a sensitivity check are reported.

## Evidence
Observations from Monza and Monaco 2024 samples. Rule precision across 24 races is not yet measured.
