# ADR 0008: Dashboard stack and repo visibility

- Status: accepted
- Date: 2026-11-10

## Decision
Power BI Desktop on Snowflake produces a `.pbix` and screenshots (no publishing licence assumed). A Streamlit app on exported Parquet gives a public live link that survives the Snowflake trial. The repo is private until week 6, then made public by the maintainer under MIT. Only tiny fixtures are committed until OpenF1 data terms are checked.

## Consequences
Power BI cannot query Snowflake after the trial ends, so screenshots and exports are taken before it expires. OpenF1's licence and F1 trademark position are unverified for republishing data.

## Evidence
OpenF1 docs state it is unofficial and F1 marks belong to Formula One Licensing B.V. No data-reuse terms were found (unverified).
