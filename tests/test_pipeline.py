import json
from datetime import UTC, datetime

from ingest.pipeline import run_season
from ingest.store import LocalStore

NOW = datetime(2026, 11, 10, tzinfo=UTC)


def session(key, name="Race", end="2024-09-01T15:00:00+00:00", cancelled=False):
    return {
        "session_key": key,
        "meeting_key": key + 1000,
        "session_name": name,
        "year": 2024,
        "date_end": end,
        "is_cancelled": cancelled,
    }


class FakeClient:
    def __init__(self, sessions, rows=None):
        self.sessions = sessions
        self.rows = rows or {}
        self.calls = []

    def get(self, endpoint, **params):
        self.calls.append((endpoint, params))
        if endpoint == "sessions":
            return self.sessions
        key = params.get("session_key", params.get("meeting_key"))
        return self.rows.get((endpoint, key), [{"endpoint": endpoint, "key": key}])


def raw_files(tmp_path):
    return sorted(p for p in tmp_path.rglob("*") if p.is_file())


def test_second_run_writes_nothing_and_makes_no_session_calls(tmp_path):
    client = FakeClient([session(1), session(2, "Sprint")])
    store = LocalStore(tmp_path)
    first = run_season(client, store, 2024, NOW)
    files_after_first = raw_files(tmp_path)
    calls_after_first = len(client.calls)

    second = run_season(client, store, 2024, NOW)

    assert first["ingested"] == 2 and first["new_objects"] > 0
    assert second["ingested"] == 0 and second["skipped_complete"] == 2
    assert second["new_objects"] == 0
    assert raw_files(tmp_path) == files_after_first
    assert len(client.calls) == calls_after_first + 1  # only the sessions listing is refetched


def test_skips_future_cancelled_and_non_race_sessions(tmp_path):
    client = FakeClient(
        [
            session(1),
            session(2, end="2026-12-06T15:00:00+00:00"),
            session(3, cancelled=True),
            session(4, "Qualifying"),
        ]
    )
    summary = run_season(client, LocalStore(tmp_path), 2024, NOW)
    assert summary["eligible"] == 1
    assert summary["skipped_not_finished"] == 1
    assert not any("session_key=2" in str(p) for p in raw_files(tmp_path))


def test_off_season_run_does_nothing_and_says_so(tmp_path):
    client = FakeClient([session(2, end="2026-12-06T15:00:00+00:00")])
    summary = run_season(client, LocalStore(tmp_path), 2024, NOW)
    assert summary["eligible"] == 0
    assert "nothing to ingest" in summary["message"]


def test_corrected_data_becomes_a_new_object_and_old_one_is_kept(tmp_path):
    store = LocalStore(tmp_path)
    original = FakeClient([session(1)], {("laps", 1): [{"lap": 1, "d": 90.1}]})
    run_season(original, store, 2024, NOW)
    corrected = FakeClient([session(1)], {("laps", 1): [{"lap": 1, "d": 90.2}]})
    summary = run_season(corrected, store, 2024, NOW, refresh=True)

    lap_files = [p for p in raw_files(tmp_path) if "endpoint=laps" in str(p)]
    assert summary["new_objects"] == 1
    assert len(lap_files) == 2


def test_latest_sessions_pointer_names_the_stored_listing(tmp_path):
    run_season(FakeClient([session(1)]), LocalStore(tmp_path), 2024, NOW)
    pointer = json.loads((tmp_path / "raw/season=2024/_sessions_latest.json").read_text())
    assert (tmp_path / pointer["key"]).exists()
    assert "endpoint=sessions" in pointer["key"]


def test_object_key_is_content_hash_and_manifest_lists_endpoints(tmp_path):
    run_season(FakeClient([session(1)]), LocalStore(tmp_path), 2024, NOW)
    manifest_path = tmp_path / "raw/season=2024/session_key=1/_complete.json"
    manifest = json.loads(manifest_path.read_text())
    assert set(manifest["objects"]) == {
        "meetings", "drivers", "laps", "stints", "pit", "weather", "race_control"
    }
    key = manifest["objects"]["laps"]["key"]
    assert (tmp_path / key).exists()
    assert key.startswith("raw/season=2024/session_key=1/endpoint=laps/")
    assert key.endswith(".json")
