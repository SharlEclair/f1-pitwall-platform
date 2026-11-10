"""Derive a track status (GREEN, VSC, SC, RED) for each lap from race_control messages.

OpenF1 puts Safety Car and Virtual Safety Car in one `SafetyCar` category; only the message text
tells them apart. Message `lap_number` is the leader's lap, so lapped cars would be misjudged;
windows are therefore built from message timestamps and matched to each lap's time interval.

Window rules:
  VSC: `VIRTUAL SAFETY CAR DEPLOYED` until `VIRTUAL SAFETY CAR ENDING`.
  SC:  `SAFETY CAR DEPLOYED` until `SAFETY CAR IN THIS LAP`.
  RED: a RED flag until the next `SESSION STARTED`; a RED flag also closes any open SC/VSC.
An unclosed window runs to the end of the session. When overlapping, RED > SC > VSC.
`SAFETY CAR IN THIS LAP` is announced at the start of the last SC lap, and the first lap after a
restart is also slow, so SC and RED windows end one typical lap (`grace`) after their closing
message. VSC windows end at their message.
"""

from datetime import datetime, timedelta
from statistics import median

PRIORITY = {"RED": 3, "SC": 2, "VSC": 1}


def _time(value):
    return datetime.fromisoformat(value)


def status_windows(race_control, grace=timedelta(0)):
    """Return [(label, start, end)] with end None for a window still open at the end."""
    events = sorted((r for r in race_control if r.get("date")), key=lambda r: r["date"])
    open_at = {"SC": None, "VSC": None, "RED": None}
    windows = []

    def close(label, at):
        if open_at[label] is not None:
            windows.append((label, open_at[label], at))
            open_at[label] = None

    for row in events:
        at, message = _time(row["date"]), (row.get("message") or "").upper()
        if row.get("flag") == "RED":
            close("SC", at)
            close("VSC", at)
            open_at["RED"] = open_at["RED"] or at
        elif row.get("category") == "SessionStatus" and "SESSION STARTED" in message:
            close("RED", at + grace)
        elif row.get("category") != "SafetyCar":
            continue
        elif "VIRTUAL SAFETY CAR DEPLOYED" in message:
            open_at["VSC"] = open_at["VSC"] or at
        elif "VIRTUAL SAFETY CAR ENDING" in message:
            close("VSC", at)
        elif "SAFETY CAR DEPLOYED" in message:
            open_at["SC"] = open_at["SC"] or at
        elif "SAFETY CAR IN THIS LAP" in message:
            close("SC", at + grace)
    windows += [(label, start, None) for label, start in open_at.items() if start is not None]
    return windows


def lap_statuses(race_control, laps):
    """Map (driver_number, lap_number) to a label for laps that overlap a window.

    A lap spans date_start to date_start + lap_duration; a lap with no duration spans up to the
    driver's next lap start, or is a single instant if there is none.
    """
    durations = [r["lap_duration"] for r in laps if r.get("lap_duration")]
    grace = timedelta(seconds=median(durations)) if durations else timedelta(0)
    windows = status_windows(race_control, grace)
    if not windows:
        return {}
    starts = {(r["driver_number"], r["lap_number"]): r.get("date_start") for r in laps}
    status = {}
    for row in laps:
        key = (row["driver_number"], row["lap_number"])
        if not row.get("date_start"):
            continue
        begin = _time(row["date_start"])
        if row.get("lap_duration") is not None:
            end = begin + timedelta(seconds=row["lap_duration"])
        elif starts.get((key[0], key[1] + 1)):
            end = _time(starts[(key[0], key[1] + 1)])
        else:
            end = begin
        for label, start, stop in windows:
            if start <= end and (stop is None or stop >= begin) and (
                PRIORITY[label] > PRIORITY.get(status.get(key), 0)
            ):
                status[key] = label
    return status
