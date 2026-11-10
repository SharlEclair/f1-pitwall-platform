-- Removes everything this project created in Snowflake. Run as ACCOUNTADMIN (run by the account administrator).
-- Dropping the database deletes all loaded and modelled data; the marts are exported to Parquet
-- first (python -m snowload.export_marts), and everything else can be rebuilt from S3 and the repo.
USE ROLE ACCOUNTADMIN;

DROP DATABASE IF EXISTS F1_PITWALL;
DROP WAREHOUSE IF EXISTS F1_WH;
DROP RESOURCE MONITOR IF EXISTS F1_MONITOR;
DROP INTEGRATION IF EXISTS S3_F1;   -- created but unused (ADR 0011)
DROP USER IF EXISTS F1_PIPELINE;
DROP ROLE IF EXISTS F1_ENGINEER;
