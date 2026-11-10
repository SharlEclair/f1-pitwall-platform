"""Load validated Parquet into Snowflake through an internal stage, and reconcile row counts.

Why an internal stage: the S3 storage integration cannot assume its AWS role (ADR 0011).

Usage (from the repo root, SNOWFLAKE_* environment variables set locally; first copy the
validator output from S3, e.g. `aws s3 sync s3://<bucket>/silver data/silver`):
  python -m snowload.load setup
  python -m snowload.load load <silver_dir> <quarantine_dir> [--full-refresh]
  python -m snowload.load reconcile <silver_dir> <quarantine_dir>

Table definitions come from the validator's schemas, so they cannot drift. A normal run stages
only files not already staged (PUT OVERWRITE = FALSE) and COPY INTO skips files already loaded, so
a repeat run loads nothing. A changed file of the same name is NOT replaced: after re-validating
with changed rules use --full-refresh, and use `reconcile` to detect a stale load.
"""

import os
import sys
from pathlib import Path

import polars as pl

from validate.checks import QUARANTINE_SCHEMA, SILVER_SCHEMA

SCHEMA = "RAW"
STAGE = "PIPELINE_STAGE"


def snowflake_type(dtype):
    if dtype == pl.Int64:
        return "NUMBER(38,0)"
    if dtype == pl.Float64:
        return "FLOAT"
    if dtype == pl.Boolean:
        return "BOOLEAN"
    if dtype == pl.Utf8:
        return "VARCHAR"
    if isinstance(dtype, pl.Datetime):
        return "TIMESTAMP_TZ"
    if isinstance(dtype, pl.List):
        return "ARRAY"
    raise ValueError(f"No Snowflake type for {dtype}")


def create_table_statements():
    """Yield (TABLE_NAME, CREATE TABLE statement) for each silver endpoint and quarantine."""
    layouts = {name.upper(): {**cols, "dq_flags": pl.List(pl.Utf8)}
               for name, cols in SILVER_SCHEMA.items()}
    layouts["QUARANTINE"] = QUARANTINE_SCHEMA
    for table, columns in layouts.items():
        body = ", ".join(f"{col.upper()} {snowflake_type(dtype)}" for col, dtype in columns.items())
        yield table, f"CREATE TABLE IF NOT EXISTS {SCHEMA}.{table} ({body})"


def copy_statement(table, folder, file_stem, force):
    return (
        f"COPY INTO {SCHEMA}.{table} FROM @{SCHEMA}.{STAGE} "
        f"PATTERN = '.*{folder}/.*/{file_stem}\\.parquet' "
        f"MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE" + (" FORCE = TRUE" if force else "")
    )


def put_statement(path, stage_dir, overwrite):
    return (
        f"PUT 'file://{Path(path).resolve().as_posix()}' @{SCHEMA}.{STAGE}/{stage_dir}/ "
        f"AUTO_COMPRESS = FALSE OVERWRITE = {'TRUE' if overwrite else 'FALSE'}"
    )


def stage_files(silver_dir, quarantine_dir):
    """Yield (local path, stage folder) per Parquet file, keeping the season/session layout."""
    for kind, root in (("silver", silver_dir), ("quarantine", quarantine_dir)):
        root = Path(root)
        for path in sorted(root.rglob("*.parquet")):
            yield path, f"{kind}/{path.parent.relative_to(root).as_posix()}"


def local_counts(directory, file_name):
    return sum(pl.read_parquet(p).height for p in Path(directory).rglob(file_name))


def connect():
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization

    with open(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"], "rb") as handle:
        key = serialization.load_pem_private_key(handle.read(), password=None)
    der = key.private_bytes(
        serialization.Encoding.DER,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return snowflake.connector.connect(
        account=os.environ["SNOWFLAKE_ACCOUNT"],
        user=os.environ["SNOWFLAKE_USER"],
        private_key=der,
        role=os.environ.get("SNOWFLAKE_ROLE", "F1_ENGINEER"),
        warehouse=os.environ.get("SNOWFLAKE_WAREHOUSE", "F1_WH"),
        database=os.environ.get("SNOWFLAKE_DATABASE", "F1_PITWALL"),
        server_session_keep_alive=False,
        session_parameters={"TIMEZONE": "UTC"},
    )


def setup(cursor):
    cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}")
    cursor.execute(
        f"CREATE FILE FORMAT IF NOT EXISTS {SCHEMA}.PARQUET_FF "
        "TYPE = PARQUET USE_LOGICAL_TYPE = TRUE"
    )
    cursor.execute(
        f"CREATE STAGE IF NOT EXISTS {SCHEMA}.{STAGE} FILE_FORMAT = {SCHEMA}.PARQUET_FF"
    )
    for _, statement in create_table_statements():
        cursor.execute(statement)


def upload(cursor, silver_dir, quarantine_dir, overwrite):
    counts = {"uploaded": 0, "skipped": 0}
    for path, stage_dir in stage_files(silver_dir, quarantine_dir):
        status = cursor.execute(put_statement(path, stage_dir, overwrite)).fetchall()[0][6]
        counts["uploaded" if status == "UPLOADED" else "skipped"] += 1
    return counts


def load(cursor, silver_dir, quarantine_dir, full_refresh):
    report = {"upload": upload(cursor, silver_dir, quarantine_dir, overwrite=full_refresh)}
    targets = [(name.upper(), "silver", name) for name in SILVER_SCHEMA]
    targets.append(("QUARANTINE", "quarantine", "quarantine"))
    for table, folder, stem in targets:
        if full_refresh:
            cursor.execute(f"TRUNCATE TABLE {SCHEMA}.{table}")
        rows = cursor.execute(copy_statement(table, folder, stem, full_refresh)).fetchall()
        loaded = [r for r in rows if len(r) > 3 and r[1] == "LOADED"]
        report[table] = {"files_loaded": len(loaded), "rows_loaded": sum(r[3] for r in loaded)}
    return report


def table_counts(cursor):
    return {
        table: cursor.execute(f"SELECT COUNT(*) FROM {SCHEMA}.{table}").fetchone()[0]
        for table, _ in create_table_statements()
    }


def main(argv):
    command = argv[0] if argv else ""
    if command == "reconcile":
        silver_dir, quarantine_dir = argv[1], argv[2]
        expected = {
            name.upper(): local_counts(silver_dir, f"{name}.parquet") for name in SILVER_SCHEMA
        }
        expected["QUARANTINE"] = local_counts(quarantine_dir, "quarantine.parquet")
        with connect() as conn:
            actual = table_counts(conn.cursor())
        for table, count in expected.items():
            status = "OK" if actual[table] == count else "MISMATCH"
            print(f"{table:13} parquet={count:>6} snowflake={actual[table]:>6} {status}")
        return 0 if all(actual[t] == c for t, c in expected.items()) else 1
    with connect() as conn:
        cursor = conn.cursor()
        if command == "setup":
            setup(cursor)
            print("setup done")
        elif command == "load":
            report = load(cursor, argv[1], argv[2], "--full-refresh" in argv)
            print(f"staged: {report.pop('upload')}")
            for table, result in report.items():
                print(f"{table:13} files_loaded={result['files_loaded']} "
                      f"rows={result['rows_loaded']}")
        else:
            print(__doc__)
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
