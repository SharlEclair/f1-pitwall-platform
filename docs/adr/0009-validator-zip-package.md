# ADR 0009: Validator Lambda ships as a zip package, not a container image

- Status: accepted
- Date: 2026-11-10

## Context
The plan defaulted to a container image for the validator because Polars plus PyArrow can be large. The validator uses only Polars (Parquet is written by Polars itself, no PyArrow). A container image would need Docker running locally and an ECR repository, adding a resource to deploy and tear down.

## Options considered
1. Container image - no size limit worry; needs Docker Desktop, ECR repo and lifecycle policy.
2. Zip package via `sam build` - needs no Docker; must confirm Linux wheels are bundled and the package fits Lambda's 250 MB unzipped limit.

## Decision
Zip package. Both functions share one `src/` code package that includes `polars==2.1.0`.

## Consequences
No Docker or ECR. The ingest function also carries Polars on disk though it never imports it. If a later dependency pushes the package past the limit, switch the validator to a container image (new ADR).

## Evidence
`sam build` on Windows bundled a Linux `_polars_runtime.abi3.so` (no Windows `.pyd`); build directory 174 MB unzipped (measured). Not yet confirmed by invoking the deployed function.
