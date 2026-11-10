# ADR 0001: Decisions made before planning

- Status: accepted (open to challenge in the planning session; supersede with a new ADR if changed)
- Date: 2026-11-10

These were settled before planning started. The planning session tested them rather than silently
overwriting them; later ADRs supersede some of them (noted below).

| # | Decision | Reason |
|---|---|---|
| 1 | Cloud = **AWS** | Mature serverless building blocks (S3, Lambda, EventBridge, SNS, IAM) and a free plan suited to a small project |
| 2 | Warehouse = **Snowflake** on AWS Sydney | Free trial; region is fixed at signup, so co-locate with S3 (revised by ADR 0010) |
| 3 | Data source = **OpenF1** historical (2023+) | Free, no authentication, covers the 2024 season |
| 4 | IaC = **AWS SAM** | One template, easy teardown, lighter than Terraform |
| 5 | Transform/test = **dbt Core** | Standard, free, SQL plus testing |
| 6 | CI auth = **GitHub OIDC** | No stored AWS keys (found blocked in this account: ADR 0014) |
| 7 | CI warehouse = **dbt-duckdb on a committed fixture** | Keeps CI green after the Snowflake trial ends; doubles as a regression set |
| 8 | ML tracking = **MLflow, local first** | Free; tracks experiments without infrastructure |
| 9 | Validation = **coded rule registry + quarantine + golden tests** | A visible data-quality layer is the core idea of the project |
| 10 | Evaluation = **baseline first, leave-one-race-out** | Avoids leakage; honest evaluation is a design principle |
| 11 | BI = **Power BI**, Streamlit live link optional | Power BI is widely used for stakeholder reporting; a live link beats a screenshot |
| 12 | Out of scope: Kafka, Airflow, Kubernetes, Terraform, streaming, `car_data`/`location` | Not needed for the questions asked, and costly to learn and run |

## Known risks to these decisions

- OpenF1 terms, limits and endpoint set are from secondary sources: verify.
- AWS free-plan behaviour (credit expiry, account closure) varies by source: verify.
- Snowflake trial length forces a tight window: plan exports early.
- dbt SQL portability between Snowflake and DuckDB may need small compromises.
