# ADR 0014: CI does not deploy to AWS because GitHub OIDC is blocked in this account

- Status: accepted (supersedes decision 6 in ADR 0001, "CI auth = GitHub OIDC")
- Date: 2026-11-11

## Context
The plan was to deploy from GitHub Actions to AWS with OpenID Connect (no stored keys). This needs an
IAM OpenID Connect identity provider for `token.actions.githubusercontent.com`. In this AWS account
(created through the new AWS experience, member of an AWS-managed Organization) both
`iam:ListOpenIDConnectProviders` and `iam:CreateOpenIDConnectProvider` returned AccessDenied with
"an explicit deny in a service control policy" (`p-fppd44xk`), even for the account's full-access role.
The policy text cannot be read from a member account.

## Options considered
1. GitHub OIDC - impossible here (explicit deny).
2. IAM user access keys stored as GitHub secrets - works, but breaks the project's no-stored-keys rule.
3. A standard (non-organization-managed) AWS account where OIDC is allowed - possible later, out of scope now.
4. CI without AWS access: lint, tests, offline `sam validate`, `dbt build` on the DuckDB fixture.
   Deploys are run by the maintainer from their machine with short-lived `aws login` credentials.

## Decision
Option 4. The GitHub workflow has no AWS credentials at all. The deploy path (`sam build`,
`sam deploy`) stays documented and is run locally.

## Consequences
- The definition-of-done item "deploy via OIDC" is not met and must be reported as blocked, not claimed.
- CI cannot catch deploy-time failures (permissions, quotas); only template validity.
- The same SCP is evidence of organization-level restrictions in this account; it may also relate to the
  unexplained Snowflake assume-role failure (ADR 0011), but that is not established.

## Evidence
Two AccessDenied responses naming a service control policy, quoted from the AWS CLI on 2026-11-11.
