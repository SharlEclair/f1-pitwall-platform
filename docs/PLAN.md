# F1 Pitwall Platform: PLAN (Phase A output)

Status: approved on 2026-11-10. Sample data used for findings was pulled from the live OpenF1 API on that date.

## Context
Portfolio data-engineering project (OpenF1 -> S3 -> validate/quarantine -> Snowflake -> dbt -> MLflow -> dashboard) closing gaps in AWS, Snowflake, MLOps and DQ-in-DE. Must be real, measured, defensible. Budget ~8-10 h/week, target public in 7 weeks.

## Decisions from interview
| Topic | Decision |
|---|---|
| Seasons | 2024 first (24 races, 0 cancelled), widen later |
| Sessions | Race; the 6 sprints if cheap |
| Undercut mart | Deferred stretch |
| Quarantine | S3 source of truth + mirrored Snowflake table |
| Dashboard | Power BI Desktop (.pbix + screenshots) + Streamlit live link on exported Parquet |
| Repo | Private until week 6, then public, MIT, `f1-pitwall-platform` |
| Tooling | venv + pip, ruff + pytest, no type checker, dbt Core, EventBridge + Lambda, `COPY INTO`, container image for validator, local MLflow |
| Deadline | 7 weeks from approval (6 core + 1 buffer) |
| ML | Clean lap = not lap 1, not pit in/out, green-flag only, not quarantined; fuel effect estimated from data, +0.04 s/lap as sensitivity check (revisit after more data) |

## Verified vs not verified
**Confirmed (official sources / direct calls):**
- OpenF1 historical data (2023+) is free with no authentication; real-time is paid (openf1.org/docs). It is an unofficial project; F1 marks belong to Formula One Licensing B.V.
- API live today: 24 races in 2024, 24 in 2025, 25 sessions listed for 2026 including future ones (last = 2026-12-06 Yas Marina), 6 sprints in 2024.
- Endpoints return the fields below. `car_data`/`location` exist and stay excluded.
- dbt on PyPI today: dbt-core 1.12.6, dbt-snowflake 1.12.5 (requires dbt-core >=1.10,<2.0), dbt-duckdb 1.11.1 (requires dbt-core >=1.8). Python 3.13.2 locally; all three support >=3.10. Pin exact versions in a lockfile after a compatibility install test (M0).
- Snowflake trial: 30 days or $400, whichever ends first (signup/FAQ pages, marketing-level source). Card needed to continue after.
- AWS Free plan: $100 on signup + up to $100 from activities (Lambda, Budgets etc.), account closes at plan end with a 90-day recovery window (AWS Billing docs, search summary).

**Could not confirm:**
- OpenF1 official rate limit and terms of use. The docs page states neither. Third-party sources say ~3 req/s, 30 req/min (one library uses 6/s, 60/min). Plan: throttle to <=1 req/s, back off on 429, cache. Check the GitHub repo licence and F1 data terms before publishing anything beyond tiny fixtures.
- AWS credit expiry (FAQ contradicts itself: 6 vs 12 months) and whether S3 earns credits. Read the account's Billing > Credits page after signup.
- Snowflake trial availability in ap-southeast-2 (AWS Sydney) and exact edition. Confirm in the signup form.
- Snowflake CONNECTOR/storage-integration specifics, Lambda container/ECR free storage: check during M1/M3 against docs.

## Real data findings (Monza 2024 race, key 9590; Monaco 2024 race, key 9523)
Sample kept outside the repo (scratchpad); only a tiny fixture will be committed.
- `laps` Monza: 1009 rows; 20 drivers; 19 finished 52-53 laps, one retired after 8. No duplicate (driver, lap). Lap 1 has a duration (89-93 s). Only 1 null `lap_duration` (retirement lap 8), not pit-out. `i1_speed` null 220/1009, `st_speed` null 133/1009, so speed trap fields are not reliable. Sector sums match `lap_duration` exactly (0 mismatches).
- Pit-out laps are 30 and are slow (median 105.6 s vs ~85 s median overall; max 120.2 s). In-laps are also slow (median ~90.2 s).
- **Red-flag race (Monaco):** 20 of 1237 laps null, all lap 1 (red flag on lap 1). Max lap times 162-178 s. Pit `pit_duration` is ~2390 s (waiting in the pit lane under red flag), so naive pit-loss would be wildly wrong.
- `stints` Monza: 50 rows, compounds HARD/MEDIUM/SOFT only. Stints are contiguous. One mismatch: driver 22's last stint ends lap 7 while laps run to 8 (the retirement lap). `tyre_age_at_start` is 0/1/2.
- `pit`: `pit_duration` equals `lane_duration` (pit-lane transit, ~24-39 s at Monza). **`stop_duration` is null in Monza (30/30) and Monaco (23/23) but is not null for the whole of 2024**: the full 2024 backfill shows it set on 151 of 865 pit stops, only in the last races (Austin, Mexico City, Interlagos, Las Vegas, Lusail race and sprint, Yas Marina). An earlier version of this note generalised wrongly from two races. Pit-loss analysis uses lane time for all races and treats stationary time as available only for those late-2024 races (ADR 0004).
- `race_control`: Monza has no SafetyCar rows; flags are BLUE/GREEN/CHEQUERED. Monaco has RED, YELLOW, DOUBLE YELLOW, CLEAR. Track-status must come from `race_control` (lap_number, flag/category), and some flag rows have `lap_number` but no driver.
- `weather`: ~133 rows (about 1/min), no nulls. `drivers`: 20 rows, one null `headshot_url`.
- **Future sessions appear** in `sessions` (2026), so ingest must skip sessions not yet complete and distinguish "not yet run" from "missing data" (freshness rule).
- Not yet sampled: corrected/late data.

## M1 sampling addendum (2026-11-10): Melbourne 2024 race (key 9488), Shanghai 2024 sprint (key 9672), Lusail 2024 race (key 9655, race_control only)
- Across the 24 2024 races, `race_control` has `SafetyCar` category rows in 12 of the 24 races and a RED flag in 3 (Suzuka, Monaco, Interlagos); counts from one API pass over all 2024 races.
- **Safety Car and VSC share one category.** Track status is only in the message text (`SAFETY CAR DEPLOYED`, `VIRTUAL SAFETY CAR DEPLOYED`, `... ENDING`, `SAFETY CAR IN THIS LAP`, `SAFETY CAR THROUGH THE PIT LANE`). Windows must be derived by pairing deploy and end messages by `lap_number`, and they can nest (Lusail lap 40 has both a VSC and an SC deploy). A parsing rule and golden tests are needed.
- Melbourne VSC effect: median non-pit-out lap time 104.3 s on lap 17 vs about 83 s on neighbouring laps (measured, one race).
- **Null `lap_duration` is mostly retirement or lap 1:** Melbourne has 4 nulls: driver 24 lap 1 (finished the race), and 3 on drivers' last recorded laps (1, 44, 63). So a null on a driver's final lap is expected and is flagged, not rejected (DQ-LAP-002 and DQ-LAP-003 updated).
- **Sprint:** same schema as races; `session_name` is "Sprint"; 379 laps, 21 stints, 1 pit stop, compounds MEDIUM/SOFT only; `stop_duration` null; no flags beyond green and chequered. Sprints are cheap to ingest with the race pipeline.
- Not covered by this addendum: precision of rules over all 24 races (M2).

## Rule registry (starter set, each tied to a real observation; severities provisional)
| Code | Entity | Rule | Severity | Evidence |
|---|---|---|---|---|
| DQ-LAP-001 | lap | duplicate (session, driver, lap) | reject | 0 in samples; keep as guard |
| DQ-LAP-002 | lap | null `lap_duration` that is not lap 1, not a red-flag lap, and not the driver's last recorded lap | reject | none seen in Monza, Monaco, Melbourne, Shanghai sprint; guard |
| DQ-LAP-003 | lap | null `lap_duration` on lap 1, on a red-flag lap, or on the driver's last recorded lap (retirement) | flag | Monaco 20 rows; Melbourne 4 (lap 1 once, 3 final laps); Monza 1 final lap |
| DQ-LAP-004 | lap | `lap_duration` outside session band (e.g. >1.3x session median) and not pit-out/in-lap/flag lap | flag | max 120 s in Monza are pit-out |
| DQ-LAP-005 | lap | sector sum differs from lap_duration by >0.05 s | reject | 0 mismatches; guard |
| DQ-STINT-001 | stint | lap_end < lap_start, gap or overlap between stints | reject | guard |
| DQ-STINT-002 | stint | last stint ends before driver's last lap | flag | driver 22 |
| DQ-STINT-003 | stint | compound outside known set | reject | guard |
| DQ-PIT-001 | pit | `pit_duration` > 60 s (red-flag wait) | flag | Monaco ~2390 s |
| DQ-PIT-002 | pit | `stop_duration` null | warn | Monza and Monaco samples; 714 of 865 stops in 2024 |
| DQ-SESS-001 | session | driver number maps to 2 teams | reject | guard |
| DQ-API-001 | response | schema drift: missing/unexpected fields | reject | ingest |
| DQ-FRESH-001 | session | completed session not ingested after N hours | warn | future sessions listed |
Every rule gets a good/bad golden fixture. Rule precision is measured on the 24 races and reviewed before freezing.

## Architecture changes vs the sketch (to be ADRs)
1. Raw S3 key: `raw/season=/session_key=/endpoint=/{content_sha256}.json` plus a small manifest, not an ingest timestamp in the path, so a re-run with unchanged content is a true no-op and a corrected response is a new immutable object.
2. Skip sessions whose `date_end` is in the future or older than the ingest cursor; off-season runs do nothing and report it.
3. Pit-loss mart uses lane duration; flags red-flag pit stops; excludes them from loss estimates. `stop_duration` is populated only from the 2024 US Grand Prix onwards (OpenF1 docs; 151 of 865 stops in 2024, see ADR 0004).
4. Track-status per lap derived from `race_control` flags, with the rule that lap_number-null rows are ignored and flagged.
5. Lambda #2 container image needs an ECR repo; SAM manages it, with a lifecycle policy; teardown script checks for leftovers.

## Milestones (dependency order; each item has a "done when")
**M0 Setup and compat (week 0-1).**
- Repo scaffold, `.venv`, ruff, pytest, `.env.example`, `.gitignore` check for `*.pem`/`.env`. Done when: `pytest` and `ruff` run green on a placeholder test.
- Install pinned dbt-core/dbt-snowflake/dbt-duckdb in the venv. Done when: `dbt --version` lists all three and `dbt debug` passes against DuckDB.
- Maintainer: AWS account, root MFA, admin IAM user (no root use), Budget alert ~US$5 email. Done when: `aws sts get-caller-identity` (no secrets printed).
**M1 Raw ingest (week 1).**
- Throttled OpenF1 client with 429 backoff and caching; sample a Safety Car race and a sprint and update rules. Done when: 24 races of 2024 land in S3 raw with manifests; second run reports 0 new objects (test proves it).
- SAM skeleton (ingest Lambda, S3 private + lifecycle, EventBridge weekly, manual backfill event). Done when: `sam validate` passes, `sam deploy` works, `sam delete` removes everything but non-empty bucket handled by documented script.
**M2 Validation and quarantine (week 2).**
- Rule registry + Polars validator + golden tests; silver Parquet and quarantine; SNS email summary. Done when: golden tests pass; a seeded bad file is caught with the right code; raw = silver + quarantine + explained exclusions for all 24 races; email received.
- Generate `docs/DQ-CATALOGUE.md` with measured counts per rule. Done when: counts come from a logged run.
**M3 Warehouse (week 3; start Snowflake trial only now).**
- Snowflake trial (maintainer), resource monitor + XS warehouse AUTO_SUSPEND 60 before any load, storage integration + stage + `COPY INTO`, quarantine table. Done when: reconciliation query shows silver rows == Snowflake rows, load history shows idempotent reload loads 0 files.
**M4 dbt (week 4).**
- Staging, intermediate (lap context, track status), marts `fct_laps`, `fct_stints`, `fct_pit_stops`, `mart_tyre_degradation`; tests on every layer; DuckDB fixture of 2-3 races committed. Done when: `dbt build` passes on Snowflake and on DuckDB; dialect differences documented.
**M5 ML and CI/CD (week 5).**
- Baselines B0, B1 and LightGBM, leave-one-race-out, MAE with bootstrap CI over races, MLflow local tracking, one-command results table. Done when: MLflow shows all runs with n races / n laps; result published even if the model loses.
- GitHub Actions: ruff, pytest, `sam validate`, `dbt build` on DuckDB; OIDC deploy role. Done when: green run with no stored AWS keys.
**M6 Serve and document (week 6).**
- Export marts to Parquet and screenshots before the trial ends (date confirmed in advance); Power BI .pbix; Streamlit on Parquet; README (questions first), architecture diagram, ADRs, measured cost table, Limitations. Teardown + redeploy rehearsed. Done when: fresh clone passes CI, no secrets in history, repo made public.
**M7 Buffer / stretch (week 7).** Buffer first. Stretch only if ahead: widen to 2023/2025, undercut mart with `position`, Databricks Free Edition.

## Risks
- Snowflake window: trial starts week 3, dashboard week 6. Mitigation: exports early, DuckDB CI, Streamlit on Parquet.
- AWS credit/plan expiry: everything reproducible from the repo; screenshots of cost.
- Rate limits unknown: conservative throttling and cache.
- Terms of use unknown: commit only tiny fixtures; keep full data out of the repo.
- `stop_duration` missing for most 2024 races (714 of 865 stops): pit loss uses lane time; stationary time only for late-2024 races; documented.
- Workload: if behind, cut Power BI polish and stretch, never DQ or honest evaluation.
- Over-flagging: wide DQ rules could remove too many laps from the ML target; report counts and sensitivity.

## Cost estimate (targets, not measured)
AWS: expected near US$0 within free-plan credits (Lambda, S3 small, SNS, ECR small). Snowflake: well under the $400 trial credits with XS warehouse and short runs. Real figures go in the README only after measurement.

## Out of scope
Kafka, Airflow, Kubernetes, Terraform, streaming/real-time, `car_data`/`location`, race-winner prediction, Snowpipe, Databricks (stretch only), team radio.

## Who does what
- Maintainer: AWS and Snowflake accounts, MFA, billing, credentials/keys, GitHub repo creation and OIDC trust confirmation, Power BI Desktop, making the repo public, approving anything that costs money.

## ADRs to write on approval
0002 raw key by content hash + idempotency; 0003 skip future sessions / freshness; 0004 pit-loss from lane_duration (stop_duration mostly null in 2024); 0005 DQ severities and flag-vs-reject; 0006 quarantine in S3 + Snowflake; 0007 versions pinned (dbt trio) and DuckDB portability policy; 0008 dashboard = Power BI + Streamlit, repo private then public MIT.

## Verification of this plan
Each milestone's "done when" is the test. 

