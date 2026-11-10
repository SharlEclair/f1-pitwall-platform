-- Run once as ACCOUNTADMIN, after 01_account_setup.sql. After this the pipeline role
-- (F1_ENGINEER, used by scripts/dbt through the key-pair user) can do the remaining setup itself.
-- Deliberately NOT granted: ACCOUNTADMIN, control of the resource monitor, or user management.
USE ROLE ACCOUNTADMIN;

-- Needed once, to create the S3 storage integration (02). It is an account-level privilege that
-- covers any integration type, so it is the most powerful grant here.
GRANT CREATE INTEGRATION ON ACCOUNT TO ROLE F1_ENGINEER;

-- Lets the role change warehouse settings (e.g. switch query acceleration off). Note it could also
-- resize the warehouse or change auto-suspend; the resource monitor remains the hard cost cap.
GRANT MODIFY ON WAREHOUSE F1_WH TO ROLE F1_ENGINEER;

-- Lets the role read the monitor's quota and credits used (read-only).
GRANT MONITOR ON RESOURCE MONITOR F1_MONITOR TO ROLE F1_ENGINEER;
