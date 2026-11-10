# Cost and safety guardrails

> Figures below come from secondary sources and conflict in places. **Verify on official
> pages (AWS Free Tier, Snowflake trial/pricing, OpenF1 docs) during planning.**

## AWS

- New accounts reportedly get a Free plan with credits (sources say $100-$200) that ends at the
  credit limit or after 6 months, and the account closes rather than billing. Confirm in the
  console. Consequence: everything must be reproducible from the repo.
- Always-free tiers (Lambda, SNS, DynamoDB) have limits; S3's treatment on new plans is unclear.
- Before building anything: MFA on root, stop using root, create an admin IAM identity,
  set an AWS Budget alert (~US$5) with email.
- Avoid by default: NAT gateways, always-on RDS/EC2, large Glue jobs, Kinesis, cross-region transfer.
- Add S3 lifecycle rules; keep buckets private; block public access.

## Snowflake

- Trial: 30 days / ~$400 credits per official page (verify). Region, cloud and edition fixed at signup.
- Create the trial when week 3 starts, not before.
- XS warehouse, `AUTO_SUSPEND = 60`, `AUTO_RESUME = TRUE`, a resource monitor with a low credit cap
  and suspend action, before loading any data.
- Plan for the trial ending: export marts to Parquet and take dashboard screenshots before then;
  CI uses the DuckDB fixture.

## OpenF1

- Historical (2023+) free, no auth, per the official docs. Real-time is paid and out of scope.
- Reported rate limit ~3 req/s and ~30 req/min on a free tier (unconfirmed): throttle, back off on 429,
  and cache raw responses so each session is fetched once.
- Check the terms of use before publishing derived data in a public repo (commit only small fixtures).

## Secrets and keys

- Never commit or print secrets. `.env` is git-ignored; provide `.env.example` with names only.
- CI has no AWS credentials at all (GitHub OIDC is blocked in this account: ADR 0014).
- Snowflake credentials go in GitHub Actions secrets or a local env var, never in code.
- Prefer key-pair or SSO auth for Snowflake over a plain password where practical.

## Teardown

- `sam delete` removes AWS resources; a `scripts/teardown` routine documents anything outside SAM
  (S3 buckets with content, Snowflake objects).
- Test teardown and re-deploy once before calling the project done.
- Record actual spend (AWS Cost Explorer, Snowflake usage) for the README cost table.

