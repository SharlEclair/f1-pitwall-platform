# ADR 0002: Raw S3 keys use a content hash, not an ingest timestamp

- Status: accepted
- Date: 2026-11-10

## Context
The sketch put an ingest timestamp in the raw path. A re-run would then write new objects, contradicting "second run is a no-op". Raw must stay immutable and reprocessable.

## Options considered
1. Timestamp in key - simple, but every run adds objects; idempotency needs a separate check.
2. `raw/season=/session_key=/endpoint=/{content_sha256}.json` plus a manifest - unchanged content maps to the same key; corrected data becomes a new object.

## Decision
Option 2. A manifest per session records endpoint, hash, fetched-at and row count.

## Consequences
Re-runs are provably no-ops (tested). Corrected API data is detectable as a new hash. Slightly more code in the ingest step.

## Evidence
Design reasoning only; the no-op test in M1 is the proof.
