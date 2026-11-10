-- Run once as ACCOUNTADMIN in a Snowsight worksheet (run by the account administrator; no secrets in this file).
-- Order matters: the resource monitor and the small warehouse exist before anything loads.
USE ROLE ACCOUNTADMIN;

-- Cost guard: 10 credits per month, notify at 75%, suspend at 100%, stop running queries at 110%.
CREATE RESOURCE MONITOR IF NOT EXISTS F1_MONITOR
  WITH CREDIT_QUOTA = 10 FREQUENCY = MONTHLY START_TIMESTAMP = IMMEDIATELY
  TRIGGERS ON 75 PERCENT DO NOTIFY
           ON 100 PERCENT DO SUSPEND
           ON 110 PERCENT DO SUSPEND_IMMEDIATE;

CREATE WAREHOUSE IF NOT EXISTS F1_WH
  WAREHOUSE_SIZE = XSMALL AUTO_SUSPEND = 60 AUTO_RESUME = TRUE INITIALLY_SUSPENDED = TRUE
  ENABLE_QUERY_ACCELERATION = FALSE
  RESOURCE_MONITOR = F1_MONITOR;
-- (If the warehouse already exists, run: ALTER WAREHOUSE F1_WH SET ENABLE_QUERY_ACCELERATION = FALSE;)

-- A working role that owns this project's objects, so we never run the pipeline as ACCOUNTADMIN.
CREATE ROLE IF NOT EXISTS F1_ENGINEER;
GRANT USAGE, OPERATE ON WAREHOUSE F1_WH TO ROLE F1_ENGINEER;
CREATE DATABASE IF NOT EXISTS F1_PITWALL;
GRANT ALL PRIVILEGES ON DATABASE F1_PITWALL TO ROLE F1_ENGINEER;

-- Service user for scripts and dbt; key-pair login only (no password).
-- Replace the placeholder with the PUBLIC key body printed by scripts/make_snowflake_keypair.py.
CREATE USER IF NOT EXISTS F1_PIPELINE
  TYPE = SERVICE DEFAULT_ROLE = F1_ENGINEER DEFAULT_WAREHOUSE = F1_WH
  RSA_PUBLIC_KEY = '<PASTE PUBLIC KEY BODY HERE>';
GRANT ROLE F1_ENGINEER TO USER F1_PIPELINE;

-- Check: the monitor is attached and the warehouse suspends after 60 seconds.
SHOW RESOURCE MONITORS LIKE 'F1_MONITOR';
SHOW WAREHOUSES LIKE 'F1_WH';
