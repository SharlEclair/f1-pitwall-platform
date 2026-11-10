"""Export the dbt marts from Snowflake to Parquet so the work survives the Snowflake trial.

Usage (SNOWFLAKE_* variables set locally): python -m snowload.export_marts

Writes every mart to data/export/marts/ (git-ignored backup, includes row-level lap data) and only
the small aggregated marts to dashboard/data/ (committed; used by the Streamlit app). Row-level
lap data is not committed because OpenF1's reuse terms have not been verified.
"""

from pathlib import Path

import polars as pl

from snowload.load import connect

BACKUP_DIR = Path("data/export/marts")
APP_DIR = Path("dashboard/data")
ALL_MARTS = ["FCT_LAPS", "FCT_STINTS", "FCT_PIT_STOPS", "MART_TYRE_DEGRADATION", "MART_PIT_LOSS",
             "MART_DQ_HEALTH"]
APP_MARTS = ["MART_TYRE_DEGRADATION", "MART_PIT_LOSS", "MART_DQ_HEALTH"]


def to_frame(cursor, table):
    cursor.execute(f"SELECT * FROM MARTS.{table}")
    names = [c[0].lower() for c in cursor.description]
    frame = pl.DataFrame(cursor.fetchall(), schema=names, orient="row", infer_schema_length=None)
    decimals = [c for c, t in frame.schema.items() if isinstance(t, pl.Decimal)]
    return frame.with_columns([pl.col(c).cast(pl.Float64) for c in decimals])


def main():
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    APP_DIR.mkdir(parents=True, exist_ok=True)
    with connect() as conn:
        cursor = conn.cursor()
        for table in ALL_MARTS:
            frame = to_frame(cursor, table)
            name = f"{table.lower()}.parquet"
            frame.write_parquet(BACKUP_DIR / name)
            if table in APP_MARTS:
                frame.write_parquet(APP_DIR / name)
            print(f"{table}: {frame.height} rows, {frame.width} columns")


if __name__ == "__main__":
    main()
