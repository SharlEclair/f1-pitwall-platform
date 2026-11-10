"""Export the clean-lap dataset for modelling from the Snowflake marts to a local Parquet file.

Usage (SNOWFLAKE_* variables set locally): python -m ml.export data/ml/laps_clean.parquet

Races only (not sprints), dry compounds, no rain, laps flagged `is_clean_lap` by dbt. `race_laps`
is the highest lap number seen in that race, used as the race length.
"""

import sys
from pathlib import Path

import polars as pl

from snowload.load import connect

QUERY = """
select
    l.session_key, l.circuit_short_name, l.driver_number, l.lap_number, l.stint_number,
    l.compound, l.tyre_age, l.lap_duration, l.track_temperature, l.air_temperature,
    r.race_laps
from MARTS.FCT_LAPS as l
inner join (
    select session_key, max(lap_number) as race_laps from MARTS.FCT_LAPS group by session_key
) as r on l.session_key = r.session_key
where l.is_clean_lap
  and l.session_name = 'Race'
  and l.compound in ('SOFT', 'MEDIUM', 'HARD')
  and coalesce(l.rainfall, 0) = 0
order by l.session_key, l.driver_number, l.lap_number
"""

COLUMNS = ["session_key", "circuit_short_name", "driver_number", "lap_number", "stint_number",
           "compound", "tyre_age", "lap_duration", "track_temperature", "air_temperature",
           "race_laps"]


def export(path):
    with connect() as conn:
        rows = conn.cursor().execute(QUERY).fetchall()
    frame = pl.DataFrame(rows, schema=COLUMNS, orient="row", infer_schema_length=None)
    frame = frame.with_columns(
        pl.col("session_key", "driver_number", "lap_number", "stint_number", "tyre_age",
               "race_laps").cast(pl.Int64),
        pl.col("lap_duration", "track_temperature", "air_temperature").cast(pl.Float64),
    )
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(path)
    return frame


if __name__ == "__main__":
    frame = export(sys.argv[1])
    print(f"{frame.height} laps, {frame['session_key'].n_unique()} races -> {sys.argv[1]}")
