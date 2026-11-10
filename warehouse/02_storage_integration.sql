-- NOT CURRENTLY USED: Snowflake could not assume the AWS role created for this integration, so
-- data is loaded through an internal stage instead (see docs/adr/0011-internal-stage-load.md).
-- Kept as the intended design in case the AWS-side block is resolved.
-- Run as ACCOUNTADMIN (or a role with CREATE INTEGRATION) after 01. Replace <AWS_ACCOUNT_ID> and
-- <RAW_BUCKET> (neither is a secret).
USE ROLE ACCOUNTADMIN;

-- Lets Snowflake assume the IAM role created by infra/template.yaml, read-only on silver/ and
-- quarantine/. No AWS access keys are involved.
CREATE STORAGE INTEGRATION IF NOT EXISTS S3_F1
  TYPE = EXTERNAL_STAGE STORAGE_PROVIDER = 'S3' ENABLED = TRUE
  STORAGE_AWS_ROLE_ARN = 'arn:aws:iam::<AWS_ACCOUNT_ID>:role/f1-pitwall-snowflake-reader'
  STORAGE_ALLOWED_LOCATIONS = ('s3://<RAW_BUCKET>/silver/', 's3://<RAW_BUCKET>/quarantine/');

GRANT USAGE ON INTEGRATION S3_F1 TO ROLE F1_ENGINEER;

-- Copy STORAGE_AWS_IAM_USER_ARN and STORAGE_AWS_EXTERNAL_ID from the result into the AWS role's
-- trust policy (sam deploy parameters SnowflakeIamUserArn / SnowflakeExternalId).
DESC INTEGRATION S3_F1;
