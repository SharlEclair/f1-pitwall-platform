# ADR 0011: Load Snowflake from an internal stage because the S3 storage integration cannot assume its role

- Status: accepted (workaround; revisit if the AWS-side block is found)
- Date: 2026-11-11

## Context
The plan was an external stage on S3 through a storage integration (ADR 0001 / plan M3). The integration `S3_F1` and the IAM role `f1-pitwall-snowflake-reader` were created, the role's trust policy names Snowflake's IAM user and external ID (both verified equal to `DESC INTEGRATION`), but every `LIST` and `COPY INTO` on the external stage fails with "Error assuming AWS_ROLE ... not authorized to perform sts:AssumeRole". Ruled out: ARN/external-ID mismatch, IAM propagation (15+ minutes), the ExternalId condition (still failed with it removed temporarily), a permissions boundary. The AWS account belongs to an AWS-managed Organization (feature set ALL) whose policies are not readable from the member account; a restriction there is a hypothesis, not a finding. The 30-day Snowflake trial makes open-ended debugging costly.

## Options considered
1. Internal-stage load: the loader reads the Parquet that the validator wrote to S3 (via the maintainer's AWS login), `PUT`s it into a Snowflake internal stage, then runs the same `COPY INTO`. Works now; no AWS-to-Snowflake trust needed.
2. Keep debugging the AWS side (AWS support / re:Post). Could take days.
3. External stage with long-lived AWS access keys. Rejected: breaks the no-stored-keys rule.

## Decision
Option 1. The storage integration and IAM role stay in the repo (`warehouse/02_storage_integration.sql`, `infra/template.yaml`) as the intended design and a documented blocker; the external stages were dropped.

## Consequences
- The load runs from a machine that has both AWS and Snowflake credentials (a maintainer's machine, later CI), not from Snowflake pulling from S3. There is no Snowflake-side automation of the load.
- `PUT` with `OVERWRITE = FALSE` keeps COPY INTO idempotent (an identical file is not staged again, so load history skips it) but will not replace a changed file of the same name. After a rule change, run with `--full-refresh` (overwrite, truncate, forced copy). `reconcile` (Snowflake counts vs the Parquet) detects a stale load.
- The README must say the storage-integration route was built and blocked, not that it works.

## Evidence
Verified by running: integration and role values match; `LIST @RAW.SILVER_STAGE` failed with and without the ExternalId condition. Cause not established.
