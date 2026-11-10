"""Validate every ingested session of a season: raw JSON in, silver and quarantine Parquet out.

Outputs are derived and deterministic, so re-running overwrites them with identical content.
"""

import io
import json
import time
from collections import Counter

from validate.checks import ENDPOINTS, validate_session


def _parquet(frame):
    buffer = io.BytesIO()
    frame.write_parquet(buffer)
    return buffer.getvalue()


def validate_season(raw_store, out_store, year):
    started = time.monotonic()
    prefix = f"raw/season={year}/"
    manifests = [k for k in raw_store.list_keys(prefix) if k.endswith("/_complete.json")]
    summary = {
        "year": year,
        "sessions": 0,
        "rule_counts": Counter(),
        "rows": {e: {"raw": 0, "silver": 0, "quarantined": 0} for e in ENDPOINTS},
        "unbalanced_sessions": [],
        "rule_counts_by_session": {},
    }
    for manifest_key in manifests:
        session_key = int(manifest_key.split("session_key=")[1].split("/")[0])
        objects = json.loads(raw_store.get(manifest_key))["objects"]
        raw = {e: json.loads(raw_store.get(o["key"])) for e, o in objects.items()}
        source_keys = {e: o["key"] for e, o in objects.items()}
        result = validate_session(session_key, raw, source_keys)

        out = f"{{kind}}/season={year}/session_key={session_key}"
        for endpoint, frame in result.silver.items():
            out_store.put(f"{out.format(kind='silver')}/{endpoint}.parquet", _parquet(frame))
        out_store.put(f"{out.format(kind='quarantine')}/quarantine.parquet",
                      _parquet(result.quarantine))

        summary["sessions"] += 1
        summary["rule_counts"].update(result.rule_counts)
        summary["rule_counts_by_session"][session_key] = result.rule_counts
        for endpoint, counts in result.reconciliation.items():
            for field, value in counts.items():
                summary["rows"][endpoint][field] += value
        if not result.balanced:
            summary["unbalanced_sessions"].append(session_key)

    summary["rule_counts"] = dict(sorted(summary["rule_counts"].items()))
    summary["balanced"] = not summary["unbalanced_sessions"]
    summary["elapsed_seconds"] = round(time.monotonic() - started, 1)
    return summary
