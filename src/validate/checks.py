"""Validate one session's raw endpoints into silver tables plus a quarantine table.

Reject rows go to quarantine (with rule code and reason), flag rows stay in silver with their
codes in `dq_flags`, warn rows are only counted. Nothing is dropped silently: for every endpoint
raw rows == silver rows + quarantined rows (see `Result.reconciliation`).
"""

import json
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta

import polars as pl

from validate.rules import EXPECTED_FIELDS, KNOWN_COMPOUNDS, REGISTRY
from validate.track_status import lap_statuses

ENDPOINTS = ("laps", "stints", "pit", "drivers", "race_control", "weather")
LONG_LAP_RATIO = 1.3
SECTOR_TOLERANCE = 0.05
LONG_PIT_SECONDS = 60.0

SILVER_SCHEMA = {
    "laps": {
        "session_key": pl.Int64, "driver_number": pl.Int64, "lap_number": pl.Int64,
        "date_start": pl.Datetime("us", "UTC"), "duration_sector_1": pl.Float64,
        "duration_sector_2": pl.Float64, "duration_sector_3": pl.Float64,
        "lap_duration": pl.Float64, "is_pit_out_lap": pl.Boolean, "is_in_lap": pl.Boolean,
        "track_status": pl.Utf8, "i1_speed": pl.Int64, "i2_speed": pl.Int64, "st_speed": pl.Int64,
    },
    "stints": {
        "session_key": pl.Int64, "driver_number": pl.Int64, "stint_number": pl.Int64,
        "lap_start": pl.Int64, "lap_end": pl.Int64, "compound": pl.Utf8,
        "tyre_age_at_start": pl.Int64,
    },
    "pit": {
        "session_key": pl.Int64, "driver_number": pl.Int64, "lap_number": pl.Int64,
        "date": pl.Datetime("us", "UTC"), "lane_duration": pl.Float64,
        "pit_duration": pl.Float64, "stop_duration": pl.Float64,
    },
    "drivers": {
        "session_key": pl.Int64, "driver_number": pl.Int64, "name_acronym": pl.Utf8,
        "full_name": pl.Utf8, "team_name": pl.Utf8, "team_colour": pl.Utf8,
        "country_code": pl.Utf8,
    },
    "race_control": {
        "session_key": pl.Int64, "date": pl.Datetime("us", "UTC"), "driver_number": pl.Int64,
        "lap_number": pl.Int64, "category": pl.Utf8, "flag": pl.Utf8, "scope": pl.Utf8,
        "message": pl.Utf8,
    },
    "weather": {
        "session_key": pl.Int64, "date": pl.Datetime("us", "UTC"),
        "air_temperature": pl.Float64, "track_temperature": pl.Float64, "humidity": pl.Float64,
        "pressure": pl.Float64, "rainfall": pl.Float64, "wind_speed": pl.Float64,
        "wind_direction": pl.Int64,
    },
}
QUARANTINE_SCHEMA = {
    "session_key": pl.Int64, "endpoint": pl.Utf8, "row_index": pl.Int64, "source_key": pl.Utf8,
    "rule_code": pl.Utf8, "severity": pl.Utf8, "reason": pl.Utf8, "row_json": pl.Utf8,
}


@dataclass
class Result:
    silver: dict
    quarantine: pl.DataFrame
    rule_counts: dict
    reconciliation: dict

    @property
    def balanced(self):
        return all(r["raw"] == r["silver"] + r["quarantined"] for r in self.reconciliation.values())


def _parse_time(value):
    return datetime.fromisoformat(value) if value else None


def validate_session(session_key, raw, source_keys=None):
    source_keys = source_keys or {}
    issues = defaultdict(list)  # (endpoint, row_index) -> [(code, reason)]
    fired = defaultdict(set)  # code -> {(endpoint, row_index)}

    def add(endpoint, index, code, reason):
        issues[(endpoint, index)].append((code, reason))
        fired[code].add((endpoint, index))

    data = {name: raw.get(name) or [] for name in ENDPOINTS}

    for name in ENDPOINTS:
        if not data[name]:
            add(name, -1, "DQ-SESS-002", f"{name} returned no rows")
        for index, row in enumerate(data[name]):
            missing = EXPECTED_FIELDS[name] - row.keys()
            extra = row.keys() - EXPECTED_FIELDS[name]
            if missing:
                add(name, index, "DQ-API-001", f"missing fields: {sorted(missing)}")
            if extra:
                add(name, index, "DQ-API-002", f"unexpected fields: {sorted(extra)}")

    schema_rejected = set(fired.get("DQ-API-001", ()))

    def usable(name):
        return [(i, r) for i, r in enumerate(data[name]) if (name, i) not in schema_rejected]

    status = lap_statuses(data["race_control"], [r for _, r in usable("laps")])
    _check_laps(usable("laps"), status, usable("pit"), add)
    _check_stints(usable("stints"), usable("laps"), add)
    for index, row in usable("pit"):
        if (row.get("pit_duration") or 0) > LONG_PIT_SECONDS:
            add("pit", index, "DQ-PIT-001", f"pit_duration {row['pit_duration']} s")
        if row.get("stop_duration") is None:
            add("pit", index, "DQ-PIT-002", "stop_duration is null")
    teams = defaultdict(set)
    for _, row in usable("drivers"):
        teams[row.get("driver_number")].add(row.get("team_name"))
    for index, row in usable("drivers"):
        if len(teams[row.get("driver_number")]) > 1:
            add("drivers", index, "DQ-SESS-001", f"driver {row['driver_number']} has 2+ teams")

    return _assemble(session_key, data, issues, fired, source_keys, status)


def _check_laps(laps, status, pits, add):
    rows = [r for _, r in laps]
    last_lap = {}
    for row in rows:
        driver = row["driver_number"]
        last_lap[driver] = max(last_lap.get(driver, 0), row["lap_number"])
    seen = Counter((r["driver_number"], r["lap_number"]) for r in rows)
    in_laps = {(r["driver_number"], r["lap_number"]) for _, r in pits}
    durations = [r["lap_duration"] for r in rows if r["lap_duration"] and not r["is_pit_out_lap"]]
    median = statistics.median(durations) if durations else None

    for index, row in laps:
        key = (row["driver_number"], row["lap_number"])
        track = status.get(key, "GREEN")
        if seen[key] > 1:
            add("laps", index, "DQ-LAP-001", f"duplicate lap {key}")
        duration = row["lap_duration"]
        if duration is None:
            explained = (
                row["lap_number"] == 1 or track == "RED" or row["lap_number"] == last_lap[key[0]]
            )
            code = "DQ-LAP-003" if explained else "DQ-LAP-002"
            add("laps", index, code, f"null lap_duration on lap {row['lap_number']} ({track})")
            continue
        sectors = [row[f"duration_sector_{n}"] for n in (1, 2, 3)]
        if None not in sectors and abs(sum(sectors) - duration) > SECTOR_TOLERANCE:
            gap = round(sum(sectors) - duration, 3)
            add("laps", index, "DQ-LAP-005", f"sector sum differs from lap time by {gap} s")
        if (median and duration > LONG_LAP_RATIO * median and track == "GREEN"
                and not row["is_pit_out_lap"] and key not in in_laps):
            add("laps", index, "DQ-LAP-004", f"{duration} s vs session median {median:.1f} s")


def _check_stints(stints, laps, add):
    last_lap = {}
    for _, row in laps:
        driver = row["driver_number"]
        last_lap[driver] = max(last_lap.get(driver, 0), row["lap_number"])
    by_driver = defaultdict(list)
    for index, row in stints:
        compound = row["compound"]
        if compound not in KNOWN_COMPOUNDS:
            add("stints", index, "DQ-STINT-003", f"compound {compound!r} not recognised")
        elif compound == "UNKNOWN":
            add("stints", index, "DQ-STINT-004", "compound UNKNOWN")
        if row["lap_start"] is None or row["lap_end"] is None or row["lap_end"] < row["lap_start"]:
            add("stints", index, "DQ-STINT-001",
                f"stint {row['stint_number']} laps {row['lap_start']}-{row['lap_end']}")
        else:
            by_driver[row["driver_number"]].append((index, row))
    for driver, items in by_driver.items():
        items.sort(key=lambda item: item[1]["stint_number"])
        for (_, previous), (index, current) in zip(items, items[1:], strict=False):
            if current["lap_start"] != previous["lap_end"] + 1:
                add("stints", index, "DQ-STINT-001",
                    f"stint {current['stint_number']} starts lap {current['lap_start']} "
                    f"after previous ended lap {previous['lap_end']}")
        index, final = items[-1]
        if driver in last_lap and final["lap_end"] != last_lap[driver]:
            add("stints", index, "DQ-STINT-002",
                f"last stint ends lap {final['lap_end']}, last lap is {last_lap[driver]}")


def _assemble(session_key, data, issues, fired, source_keys, status):
    rejected = {
        key for key, found in issues.items()
        if key[1] >= 0 and any(REGISTRY[c].severity == "reject" for c, _ in found)
    }
    quarantine = []
    for (endpoint, index), found in sorted(issues.items()):
        if (endpoint, index) not in rejected:
            continue
        for code, reason in found:
            if REGISTRY[code].severity == "reject":
                quarantine.append({
                    "session_key": session_key, "endpoint": endpoint, "row_index": index,
                    "source_key": source_keys.get(endpoint),
                    "rule_code": code, "severity": "reject", "reason": reason,
                    "row_json": json.dumps(data[endpoint][index], sort_keys=True),
                })

    in_laps = {(r.get("driver_number"), r.get("lap_number")) for r in data["pit"]}
    silver, reconciliation = {}, {}
    for endpoint in ENDPOINTS:
        schema = SILVER_SCHEMA[endpoint]
        out = []
        for index, row in enumerate(data[endpoint]):
            if (endpoint, index) in rejected:
                continue
            flags = sorted(
                c for c, _ in issues.get((endpoint, index), []) if REGISTRY[c].severity == "flag"
            )
            record = {name: row.get(name) for name in schema}
            for name in ("date_start", "date"):
                if name in record:
                    record[name] = _parse_time(record[name])
            if endpoint == "laps":
                record["is_in_lap"] = (row["driver_number"], row["lap_number"]) in in_laps
                record["track_status"] = status.get(
                    (row["driver_number"], row["lap_number"]), "GREEN"
                )
            out.append({**record, "dq_flags": flags})
        full_schema = {**schema, "dq_flags": pl.List(pl.Utf8)}
        silver[endpoint] = pl.DataFrame(out, schema=full_schema, strict=False)
        reconciliation[endpoint] = {
            "raw": len(data[endpoint]),
            "silver": len(out),
            "quarantined": sum(1 for key in rejected if key[0] == endpoint),
        }
    return Result(
        silver=silver,
        quarantine=pl.DataFrame(quarantine, schema=QUARANTINE_SCHEMA),
        rule_counts={code: len(rows) for code, rows in sorted(fired.items())},
        reconciliation=reconciliation,
    )


def freshness_warnings(sessions, ingested_keys, now, hours=48):
    """DQ-FRESH-001: finished race/sprint sessions not ingested within `hours` of ending."""
    late = timedelta(hours=hours)
    return [
        s["session_key"] for s in sessions
        if s["session_name"] in ("Race", "Sprint") and not s.get("is_cancelled")
        and now - datetime.fromisoformat(s["date_end"]) > late
        and s["session_key"] not in ingested_keys
    ]
