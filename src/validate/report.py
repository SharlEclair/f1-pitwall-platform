"""Plain-text run summary for the SNS email."""


def format_summary(summary, stale_sessions=()):
    rows = summary["rows"]
    quarantined = sum(r["quarantined"] for r in rows.values())
    status = "OK" if summary["balanced"] and not stale_sessions else "ATTENTION"
    subject = (f"F1 Pitwall validation {summary['year']}: {status} - {summary['sessions']} "
               f"sessions, {quarantined} rows quarantined")
    lines = [
        f"Sessions validated: {summary['sessions']}",
        f"Row counts reconcile (raw = silver + quarantine): {summary['balanced']}",
        f"Rows quarantined: {quarantined}",
        f"Finished sessions not ingested in time (DQ-FRESH-001): {len(stale_sessions)}",
        f"Elapsed: {summary['elapsed_seconds']} s",
        "",
        "Rows fired per rule:",
    ]
    lines += [f"  {code}: {count}" for code, count in summary["rule_counts"].items()] or ["  none"]
    if summary["unbalanced_sessions"]:
        lines += ["", f"Unbalanced sessions: {summary['unbalanced_sessions']}"]
    if stale_sessions:
        lines += ["", f"Stale session keys: {list(stale_sessions)}"]
    return subject, "\n".join(lines)
