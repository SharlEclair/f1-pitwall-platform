# ADR 0018: How OpenF1 data is used and shared

- Status: accepted
- Date: 2026-11-11

## Context
OpenF1's documentation says historical data is free and needs no authentication, but states no rate
limit and no terms for reusing or redistributing the data. The OpenF1 source repository carries a
Creative Commons Attribution-NonCommercial-ShareAlike 4.0 licence file; whether that licence is meant to
cover the data the API serves is not stated. F1 and related marks belong to Formula One Licensing B.V.

## Decision
1. Treat the data as non-commercial and attribution-required until the maintainers say otherwise. This
   project is a non-commercial portfolio piece and keeps the non-affiliation and attribution notice.
2. Do not commit full row-level OpenF1 data. The repository holds small aggregated tables (per race and
   compound, and per sensitivity-grid cell), generated results, and a small DuckDB test fixture for CI.
3. The fixture's lap, stint, pit, driver, race-control, weather and quarantine tables for three races are
   real rows (about 100 KB); its position and interval tables are synthetic, derived from the lap
   timing, and the undercut golden events are hand-built. No new row-level OpenF1 data was added when
   the pipeline widened to three seasons and two more endpoints.
4. Keep requests to at most one per second with backoff and keep the raw responses (content-hash keys), so
   each page is fetched once.
5. The owner asks the maintainers on their public discussion board whether the data may be
   redistributed in a small test fixture and in aggregated form (not yet asked when this was written).
   If the answer is no, the real-row fixture tables are replaced with synthetic ones.

## Consequences
- The README states the licence finding and the position above.
- The aggregated Parquet used by the live dashboard is derived data; if the maintainers object it can be
  regenerated from a private copy of the raw data.
