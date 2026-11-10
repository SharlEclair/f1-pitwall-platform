# ADR 0019: What was tried on the two unexplained cloud blocks

- Status: accepted (no fix; causes still unproven)
- Date: 2026-11-11

## Context
Two problems from the first release were never explained: Snowflake could not assume the AWS role for a
storage integration (ADR 0011), and GitHub OIDC deploys are blocked by a service control policy (ADR
0014). A third, a `sam deploy` that once exited silently, did not recur.

## What was tried
- **CloudTrail:** event history for `AssumeRole` since 2026-11-09 was read in ap-southeast-2, us-east-1 and
  us-west-2. It holds 1,000 events, all made by AWS services or by this account's own sessions; there is
  **no AssumeRole event from an external account and no AccessDenied** for any of them. The failed
  Snowflake attempts therefore left no trace in this account's history. That is consistent with the
  denial being recorded only on the caller's side or never being evaluated by IAM, but it does not
  identify the cause and does not confirm or rule out an organisation policy.
- **Organisation policy:** cannot be read from a member account, so the service-control-policy
  explanation stays unproven.
- **Second Snowflake account:** not tried. It needs the owner's second account and a new integration there,
  and it would only show whether the failure is specific to one Snowflake account.
- **`sam deploy` silent exit:** the one `sam deploy` run since (a code-only update) succeeded once its
  parameters were passed correctly. Unexplained, and one run is too few to call it not recurring.
- **Failure alert on the rebuilt stack:** the validator was invoked with an invalid year. It raised, after
  its SNS publish call returned without error, so the publish path works on the current stack. Receipt of
  the email by the owner was not confirmed by this check. (An earlier test with a year that has no data
  did not fail: it published an "OK, 0 sessions" summary instead.)

## Decision
Keep the internal-stage load and the CI without AWS credentials. Do not claim either block is explained.

## Consequences
- The README keeps both items under "things that did not work", with this ADR as the record of what was
  tried.
- Anyone with a standard (non-organisation-managed) AWS account can test the storage integration and OIDC
  there; that is the cheapest way to find out whether the cause is the account or the design.
