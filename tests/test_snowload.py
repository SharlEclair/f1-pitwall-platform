import polars as pl

from snowload.load import (
    copy_statement,
    create_table_statements,
    local_counts,
    put_statement,
    stage_files,
)


def test_laps_ddl_uses_validator_schema_and_snowflake_types():
    statements = dict(create_table_statements())
    laps = statements["LAPS"]
    assert "SESSION_KEY NUMBER(38,0)" in laps
    assert "LAP_DURATION FLOAT" in laps
    assert "DATE_START TIMESTAMP_TZ" in laps
    assert "IS_PIT_OUT_LAP BOOLEAN" in laps
    assert "TRACK_STATUS VARCHAR" in laps
    assert "DQ_FLAGS ARRAY" in laps


def test_every_silver_endpoint_and_quarantine_has_a_table():
    names = {name for name, _ in create_table_statements()}
    assert names == {
        "LAPS", "STINTS", "PIT", "DRIVERS", "RACE_CONTROL", "WEATHER", "POSITION", "INTERVALS",
        "QUARANTINE",
    }


def test_copy_matches_columns_by_name_and_only_forces_on_full_refresh():
    normal = copy_statement("LAPS", "silver", "laps", force=False)
    forced = copy_statement("LAPS", "silver", "laps", force=True)
    assert "MATCH_BY_COLUMN_NAME = CASE_INSENSITIVE" in normal
    assert "FORCE" not in normal and "FORCE = TRUE" in forced
    assert "PATTERN = '.*silver/.*/laps\\.parquet'" in normal


def test_put_never_overwrites_unless_asked_and_keeps_parquet_uncompressed(tmp_path):
    file = tmp_path / "laps.parquet"
    file.touch()
    keep = put_statement(file, "silver/season=2024/session_key=1", overwrite=False)
    replace = put_statement(file, "silver/season=2024/session_key=1", overwrite=True)
    assert "AUTO_COMPRESS = FALSE" in keep and "OVERWRITE = FALSE" in keep
    assert "OVERWRITE = TRUE" in replace
    assert "@RAW.PIPELINE_STAGE/silver/season=2024/session_key=1/" in keep


def test_stage_files_maps_local_layout_to_stage_folders(tmp_path):
    silver, quarantine = tmp_path / "silver", tmp_path / "quarantine"
    for root, name in ((silver, "laps.parquet"), (quarantine, "quarantine.parquet")):
        folder = root / "season=2024" / "session_key=7"
        folder.mkdir(parents=True)
        (folder / name).touch()
    destinations = {dest for _, dest in stage_files(silver, quarantine)}
    assert destinations == {
        "silver/season=2024/session_key=7",
        "quarantine/season=2024/session_key=7",
    }


def test_local_counts_sums_rows_across_session_files(tmp_path):
    for key in (1, 2):
        folder = tmp_path / f"season=2024/session_key={key}"
        folder.mkdir(parents=True)
        pl.DataFrame({"a": [1, 2, 3]}).write_parquet(folder / "laps.parquet")
    assert local_counts(tmp_path, "laps.parquet") == 6
