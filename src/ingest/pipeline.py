"""Raw ingest: fetch finished race/sprint sessions once and store them immutably.

Raw objects are keyed by content hash (ADR 0002), so an unchanged re-fetch is a no-op and a
corrected response becomes a new object. A per-session manifest (`_complete.json`) marks the
session as ingested so later runs skip it without calling the API (ADR 0003).
"""

from datetime import datetime

from ingest.store import canonical_bytes, sha256_hex

SESSION_ENDPOINTS = ("drivers", "laps", "stints", "pit", "weather", "race_control")
SESSION_NAMES = ("Race", "Sprint")


def store_rows(store, prefix, endpoint, rows):
    data = canonical_bytes(rows)
    key = f"{prefix}/endpoint={endpoint}/{sha256_hex(data)}.json"
    if store.exists(key):
        return key, False
    store.put(key, data)
    return key, True


def ingest_session(client, store, session, now, refresh=False):
    prefix = f"raw/season={session['year']}/session_key={session['session_key']}"
    manifest_key = f"{prefix}/_complete.json"
    if not refresh and store.exists(manifest_key):
        return {"status": "skipped_complete", "new": 0, "unchanged": 0}

    fetches = [("meetings", {"meeting_key": session["meeting_key"]})]
    key = session["session_key"]
    fetches += [(endpoint, {"session_key": key}) for endpoint in SESSION_ENDPOINTS]
    objects, new, unchanged = {}, 0, 0
    for endpoint, params in fetches:
        rows = client.get(endpoint, **params)
        key, is_new = store_rows(store, prefix, endpoint, rows)
        objects[endpoint] = {"key": key, "rows": len(rows)}
        new, unchanged = new + is_new, unchanged + (not is_new)

    manifest = {"fetched_at": now.isoformat(), "objects": objects}
    store.put(manifest_key, canonical_bytes(manifest))
    return {"status": "ingested", "new": new, "unchanged": unchanged}


def run_season(client, store, year, now, refresh=False):
    sessions = client.get("sessions", year=year)
    listing_key, listing_is_new = store_rows(store, f"raw/season={year}", "sessions", sessions)
    store.put(f"raw/season={year}/_sessions_latest.json", canonical_bytes({"key": listing_key}))
    wanted = [
        s for s in sessions if s["session_name"] in SESSION_NAMES and not s.get("is_cancelled")
    ]
    finished = [s for s in wanted if datetime.fromisoformat(s["date_end"]) < now]

    summary = {
        "year": year,
        "eligible": len(finished),
        "skipped_not_finished": len(wanted) - len(finished),
        "ingested": 0,
        "skipped_complete": 0,
        "new_objects": int(listing_is_new),
        "unchanged_objects": int(not listing_is_new),
    }
    for session in finished:
        result = ingest_session(client, store, session, now, refresh)
        if result["status"] == "ingested":
            summary["ingested"] += 1
        else:
            summary["skipped_complete"] += 1
        summary["new_objects"] += result["new"]
        summary["unchanged_objects"] += result["unchanged"]

    if not finished:
        summary["message"] = f"nothing to ingest for {year}: no finished race or sprint sessions"
    elif summary["new_objects"] == 0:
        summary["message"] = f"nothing new for {year}"
    else:
        summary["message"] = f"ingested {summary['ingested']} sessions for {year}"
    return summary
