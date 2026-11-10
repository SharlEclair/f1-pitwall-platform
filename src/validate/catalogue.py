"""Render docs/DQ-CATALOGUE.md from the rule registry and a measured validation run.

Usage: python -m validate.catalogue <run_summary.json> <sessions_listing.json> <out.md>
Every count comes from the run summary; only the review notes are hand-written (no numbers).
"""

import json
import sys

from validate.rules import RULES

ENTITY_ROWS = {"lap": ("laps", "laps"), "stint": ("stints", "stints"), "pit": ("pit", "pit stops"),
               "driver": ("drivers", "driver rows")}

REVIEW_NOTES = {
    "DQ-LAP-002": "Not an expected exception; reviewed individually, it is on the same lap as the "
                  "DQ-LAP-004 flags in that race (the lap after a red-flag restart).",
    "DQ-LAP-003": "Expected nulls: lap 1, red-flag laps and retirement laps. Kept visible, not "
                  "rejected.",
    "DQ-LAP-004": "Remaining flags are mostly one pattern: the lap after a red-flag restart, which "
                  "no race-control message explains. Left flagged on purpose (no rule tuned to one "
                  "race). Track status uses message timestamps, with one typical lap added after "
                  "SC and restart messages.",
    "DQ-LAP-005": "Concentrated in a single race with a near-constant gap, which points to a "
                  "systematic timing artifact rather than random bad rows. Severity is "
                  "reject; revisit if the ML target loses too many laps.",
    "DQ-STINT-001": "Zero-length stints created by tyre changes under a red flag.",
    "DQ-STINT-002": "Final stint ends one lap away from the driver's last recorded lap, in both "
                    "directions.",
    "DQ-PIT-001": "Red-flag waits plus a few isolated long stops. Excluded from pit-loss "
                  "estimates.",
    "DQ-PIT-002": "Stationary time is published only for the last races of 2024 (ADR 0004).",
    "DQ-SESS-002": "Sprints with no pit stops; plausible rather than a data gap.",
}


def _where(code, summary, names):
    by_session = summary["rule_counts_by_session"]
    pairs = sorted(((v[code], k) for k, v in by_session.items() if code in v), reverse=True)
    return ", ".join(f"{names.get(int(k), k)} {n}" for n, k in pairs[:3]) or "-"


def render(summary, names):
    rows = summary["rows"]
    total_rows = sum(r["raw"] for r in rows.values())
    lines = [
        "# Data-quality catalogue",
        "",
        f"Generated from a measured run over {summary['sessions']} sessions of {summary['year']} "
        f"(validation took {summary['elapsed_seconds']} s locally). Re-generate with "
        "`python -m validate.catalogue`.",
        "",
        "## Reconciliation (raw = silver + quarantine)",
        "",
        "| Endpoint | Raw rows | Silver | Quarantined |",
        "|---|---|---|---|",
    ]
    for endpoint, r in rows.items():
        lines.append(f"| {endpoint} | {r['raw']} | {r['silver']} | {r['quarantined']} |")
    lines += [
        "", f"All sessions balanced: {summary['balanced']}.", "", "## Rules", "",
        "| Code | Severity | Catches | Rows fired | Out of | Largest sessions | Review note |",
        "|---|---|---|---|---|---|---|",
    ]
    for rule in RULES:
        fired = summary["rule_counts"].get(rule.code, 0)
        if rule.code == "DQ-FRESH-001":
            fired = "n/a"
        if rule.entity in ENTITY_ROWS:
            endpoint, label = ENTITY_ROWS[rule.entity]
            denominator = f"{rows[endpoint]['raw']} {label}"
        elif rule.entity == "session":
            denominator = f"{summary['sessions']} sessions"
        else:
            denominator = f"{total_rows} rows"
        lines.append(
            f"| {rule.code} | {rule.severity} | {rule.description} | {fired} | {denominator} | "
            f"{_where(rule.code, summary, names)} | {REVIEW_NOTES.get(rule.code, '')} |"
        )
    lines += ["", "DQ-FRESH-001 is evaluated by the scheduled validator against the sessions "
              "listing, not per session, so it has no row count here.", ""]
    return "\n".join(lines)


def main(summary_path, sessions_path, out_path):
    summary = json.load(open(summary_path))
    names = {s["session_key"]: f"{s['circuit_short_name']} ({s['session_name']})"
             for s in json.load(open(sessions_path))}
    open(out_path, "w", encoding="utf-8").write(render(summary, names))


if __name__ == "__main__":
    main(*sys.argv[1:4])
