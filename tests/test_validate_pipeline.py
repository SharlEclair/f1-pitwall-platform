import io
import json

import polars as pl
from conftest import baseline_session, expand_case

from ingest.pipeline import store_rows
from ingest.store import LocalStore, canonical_bytes
from validate.pipeline import validate_season


def put_session(store, session_key, raw):
    prefix = f"raw/season=2024/session_key={session_key}"
    objects = {}
    for endpoint, rows in raw.items():
        key, _ = store_rows(store, prefix, endpoint, rows)
        objects[endpoint] = {"key": key, "rows": len(rows)}
    store.put(f"{prefix}/_complete.json", canonical_bytes({"objects": objects}))


def test_validate_season_writes_parquet_and_reconciles(tmp_path):
    raw_store, out_store = LocalStore(tmp_path / "raw"), LocalStore(tmp_path / "out")
    put_session(raw_store, 1, baseline_session())
    put_session(raw_store, 2, expand_case({"stints": [{"compound": "MEDIUMM"}]}))

    summary = validate_season(raw_store, out_store, 2024)

    assert summary["sessions"] == 2
    assert summary["balanced"]
    assert summary["rule_counts"]["DQ-STINT-003"] == 1
    assert summary["rows"]["stints"] == {"raw": 4, "silver": 3, "quarantined": 1}
    quarantine = pl.read_parquet(io.BytesIO(out_store.get(
        "quarantine/season=2024/session_key=2/quarantine.parquet")))
    assert quarantine["rule_code"].to_list() == ["DQ-STINT-003"]
    assert json.loads(quarantine["row_json"][0])["compound"] == "MEDIUMM"
    assert quarantine["source_key"][0].startswith("raw/season=2024/session_key=2/endpoint=stints/")


def test_rerun_is_deterministic(tmp_path):
    raw_store, out_store = LocalStore(tmp_path / "raw"), LocalStore(tmp_path / "out")
    put_session(raw_store, 1, baseline_session())
    validate_season(raw_store, out_store, 2024)
    first = {k: out_store.get(k) for k in out_store.list_keys("")}
    validate_season(raw_store, out_store, 2024)
    assert {k: out_store.get(k) for k in out_store.list_keys("")} == first
