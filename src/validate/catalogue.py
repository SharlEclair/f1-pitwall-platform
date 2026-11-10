"""Render docs/DQ-CATALOGUE.md from the rule registry and a measured validation run.

Usage: python -m validate.catalogue <out.md> <run_summary.json> <sessions_listing.json> [...]
(one summary and listing per season; the counts are summed across seasons)
Every count comes from the run summary; only the review notes are hand-written (no numbers).
"""

import json
import sys

from validate.rules import RULES

ENTITY_ROWS = {"lap": ("laps", "laps"), "stint": ("stints", "stints"), "pit": ("pit", "pit stops"),
               "driver": ("drivers", "driver rows"), "position": ("position", "position rows"),
               "interval": ("intervals", "interval rows")}

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
    "DQ-POS-004": "Calibrated on 2024: a first version flagged any duplicate at once; "
                  "two updates for one overtake land seconds apart, so a short duplicate is "
                  "normal. Only a duplicate lasting over 10 s is flagged.",
    "DQ-INT-003": "Not rounding: the differences are mostly tens of seconds and sit in two races "
                  "(Baku, Singapore). Flagged and kept; gap-based analysis must treat flagged "
                  "rows as unknown.",
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
        f"Generated from a measured run over {summary['sessions']} sessions ({summary['year']}) "
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


def combine(summaries):
    """Sum per-season run summaries into one."""
    rows = {}
    for summary in summaries:
        for endpoint, r in summary["rows"].items():
            total = rows.setdefault(endpoint, {"raw": 0, "silver": 0, "quarantined": 0})
            for field, value in r.items():
                total[field] += value
    rule_counts, by_session = {}, {}
    for summary in summaries:
        for code, n in summary["rule_counts"].items():
            rule_counts[code] = rule_counts.get(code, 0) + n
        by_session.update(summary["rule_counts_by_session"])
    years = sorted(s["year"] for s in summaries)
    return {
        "year": str(years[0]) if len(years) == 1 else f"{years[0]} to {years[-1]}",
        "sessions": sum(s["sessions"] for s in summaries),
        "elapsed_seconds": round(sum(s["elapsed_seconds"] for s in summaries), 1),
        "balanced": all(s["balanced"] for s in summaries),
        "rows": rows,
        "rule_counts": dict(sorted(rule_counts.items())),
        "rule_counts_by_session": by_session,
    }


def main(out_path, *paths):
    pairs = list(zip(paths[0::2], paths[1::2], strict=True))
    summary = combine([json.load(open(summary_path)) for summary_path, _ in pairs])
    names = {}
    for _, sessions_path in pairs:
        for s in json.load(open(sessions_path)):
            year = s["date_start"][:4]
            names[s["session_key"]] = (
                f"{s['circuit_short_name']} {year} ({s['session_name']})")
    open(out_path, "w", encoding="utf-8").write(render(summary, names))


if __name__ == "__main__":
    main(*sys.argv[1:])
