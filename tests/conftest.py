"""Shared helpers: a clean baseline session and golden-case expansion."""

import copy
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

GOLDEN_DIR = Path(__file__).parent / "golden"

BASE_ROWS = {
    "laps": {
        "meeting_key": 1, "session_key": 1, "driver_number": 1, "lap_number": 2,
        "date_start": "2024-01-01T10:00:00+00:00", "duration_sector_1": 30.0,
        "duration_sector_2": 30.0, "duration_sector_3": 30.0, "i1_speed": 300, "i2_speed": 300,
        "is_pit_out_lap": False, "lap_duration": 90.0, "segments_sector_1": [],
        "segments_sector_2": [], "segments_sector_3": [], "st_speed": 300,
    },
    "stints": {
        "meeting_key": 1, "session_key": 1, "stint_number": 1, "driver_number": 1,
        "lap_start": 1, "lap_end": 4, "compound": "MEDIUM", "tyre_age_at_start": 0,
    },
    "pit": {
        "date": "2024-01-01T10:03:00+00:00", "session_key": 1, "stop_duration": 2.3,
        "lap_number": 2, "lane_duration": 22.0, "meeting_key": 1, "driver_number": 1,
        "pit_duration": 22.0,
    },
    "drivers": {
        "meeting_key": 1, "session_key": 1, "driver_number": 1, "broadcast_name": "A ONE",
        "full_name": "A One", "name_acronym": "ONE", "team_name": "Team A",
        "team_colour": "FFFFFF", "first_name": "A", "last_name": "One", "headshot_url": None,
        "country_code": "AAA",
    },
    "race_control": {
        "meeting_key": 1, "session_key": 1, "date": "2024-01-01T10:00:00+00:00",
        "driver_number": None, "lap_number": 1, "category": "Flag", "flag": "GREEN",
        "scope": "Track", "sector": None, "qualifying_phase": None, "message": "GREEN LIGHT",
    },
    "weather": {
        "date": "2024-01-01T10:00:00+00:00", "session_key": 1, "rainfall": 0, "humidity": 40.0,
        "air_temperature": 25.0, "pressure": 1000.0, "wind_direction": 100,
        "meeting_key": 1, "track_temperature": 40.0, "wind_speed": 1.0,
    },
}


def lap_time(lap_number):
    """Start time of a lap when every lap takes 90 s from 10:00:00 UTC."""
    start = datetime(2024, 1, 1, 10, 0, 0, tzinfo=UTC) + timedelta(seconds=90 * (lap_number - 1))
    return start.isoformat()


def row(endpoint, **overrides):
    result = copy.deepcopy(BASE_ROWS[endpoint])
    result.update(overrides)
    if endpoint == "laps" and "date_start" not in overrides:
        result["date_start"] = lap_time(result["lap_number"])
    return result


def baseline_session():
    """A tiny clean session: no rule should fire on it."""
    laps = [row("laps", driver_number=d, lap_number=n) for d in (1, 2) for n in (1, 2, 3, 4)]
    return {
        "laps": laps,
        "stints": [
            row("stints", stint_number=1, lap_end=2),
            row("stints", stint_number=2, lap_start=3, lap_end=4, tyre_age_at_start=0),
            row("stints", driver_number=2),
        ],
        "pit": [row("pit")],
        "drivers": [
            row("drivers"),
            row("drivers", driver_number=2, team_name="Team B", name_acronym="TWO"),
        ],
        "race_control": [row("race_control")],
        "weather": [row("weather")],
    }


def expand_case(case):
    """Replace baseline endpoints with the case's rows (merged onto base rows).

    Per-row helpers: `_n` repeats a row with consecutive lap_numbers, `_drop` removes fields.
    """
    session = baseline_session()
    for endpoint, overrides in case.items():
        rows = []
        for spec in overrides:
            spec = dict(spec)
            count, drop = spec.pop("_n", 1), spec.pop("_drop", [])
            for offset in range(count):
                item = row(endpoint, **spec)
                if count > 1:
                    item["lap_number"] = spec["lap_number"] + offset
                    if endpoint == "laps" and "date_start" not in spec:
                        item["date_start"] = lap_time(item["lap_number"])
                for field in drop:
                    item.pop(field)
                rows.append(item)
        session[endpoint] = rows
    return session


def load_golden():
    return {p.stem: json.loads(p.read_text()) for p in sorted(GOLDEN_DIR.glob("DQ-*.json"))}
