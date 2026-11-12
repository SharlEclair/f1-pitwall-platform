"""Create the dbt seed and the small DuckDB fixture from the validator's local output.

Reads (after `aws s3 sync`): data/silver, data/quarantine, data/raw sessions listing.
Writes: dbt/seeds/sessions.csv (every ingested season's race and sprint sessions) and
        dbt/fixtures/raw/<table>.parquet (three races, for CI on DuckDB).
Only facts and counts are copied; no secrets are involved.

The `position` and `intervals` fixture tables are SYNTHETIC: they are derived from the committed
fixture laps (order and gaps at each lap crossing), not copied from OpenF1, so they add no new
row-level OpenF1 data to the repository (see ADR 0015 and ADR 0018).
"""

import csv
import glob
import json
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from validate.checks import SILVER_SCHEMA  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SESSIONS = (9488, 9590, 9523)  # Melbourne (VSC), Monza (clean), Monaco (red flag)
ENDPOINTS = ("laps", "stints", "pit", "drivers", "race_control", "weather")


def sessions_seed():
    sessions = []
    for season_dir in sorted(ROOT.glob("data/raw/season=*")):
        # the pointer names the latest stored listing for the season
        pointer = json.loads((season_dir / "_sessions_latest.json").read_text())
        sessions += json.loads((ROOT / "data" / pointer["key"]).read_text())
    rows = [
        s for s in sessions if s["session_name"] in ("Race", "Sprint") and not s["is_cancelled"]
    ]
    out = ROOT / "dbt/seeds/sessions.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["session_key", "meeting_key", "session_name", "circuit_short_name", "country_name",
              "location", "race_date", "year"]
    with out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for s in sorted(rows, key=lambda s: s["date_start"]):
            writer.writerow({**{k: s[k] for k in fields if k != "race_date"},
                             "race_date": s["date_start"][:10]})
    print(f"{out.name}: {len(rows)} sessions")


def synthetic_position_and_intervals(laps):
    """Order and gaps at each lap crossing, from lap start times (one fixture race at a time)."""
    from datetime import timedelta

    positions, intervals = [], []
    for session_key, race in laps.group_by("session_key", maintain_order=True):
        rows = race.filter(pl.col("date_start").is_not_null()).sort("driver_number", "lap_number")
        start = {(r["driver_number"], r["lap_number"]): r["date_start"]
                 for r in rows.iter_rows(named=True)}
        last = {}
        for (driver, lap) in start:
            last[driver] = max(last.get(driver, 0), lap)
        previous = {}
        for lap in range(1, max(last.values())):
            crossing = {d: start[(d, lap + 1)] for d in last if (d, lap + 1) in start}
            order = sorted(crossing, key=lambda d: (crossing[d], d))
            for place, driver in enumerate(order, start=1):
                at = crossing[driver] + timedelta(milliseconds=500)
                if previous.get(driver) != place:
                    positions.append((session_key[0], driver, at, place))
                    previous[driver] = place
                if place == 1:
                    gaps = (None, None)
                else:
                    ahead, leader = crossing[order[place - 2]], crossing[order[0]]
                    gaps = (round((crossing[driver] - ahead).total_seconds(), 3),
                            round((crossing[driver] - leader).total_seconds(), 3))
                intervals.append((session_key[0], driver, at, gaps[0], gaps[1], None))
    pos = pl.DataFrame(positions, schema=["session_key", "driver_number", "date", "race_position"],
                       orient="row")
    itv = pl.DataFrame(intervals, schema=["session_key", "driver_number", "date", "interval_s",
                                          "gap_to_leader_s", "laps_down"], orient="row")
    out = {}
    for name, frame in (("position", pos), ("intervals", itv)):
        frame = frame.with_columns(pl.col("date").cast(SILVER_SCHEMA[name]["date"]))
        frame = frame.select([pl.col(c).cast(t) for c, t in SILVER_SCHEMA[name].items()])
        out[name] = frame.with_columns(pl.lit([]).cast(pl.List(pl.Utf8)).alias("dq_flags"))
    return out


def fixture():
    target = ROOT / "dbt/fixtures/raw"
    target.mkdir(parents=True, exist_ok=True)
    for name, base in [(e, "silver") for e in ENDPOINTS] + [("quarantine", "quarantine")]:
        file_name = "quarantine.parquet" if name == "quarantine" else f"{name}.parquet"
        frames = []
        for key in FIXTURE_SESSIONS:
            pattern = f"data/{base}/season=2024/session_key={key}/{file_name}"
            frames += [pl.read_parquet(p) for p in glob.glob(str(ROOT / pattern))]
        frame = pl.concat(frames)
        frame.write_parquet(target / f"{name}.parquet")
        print(f"fixture {name}: {frame.height} rows")
        if name == "laps":
            for synthetic_name, synthetic in synthetic_position_and_intervals(frame).items():
                synthetic.write_parquet(target / f"{synthetic_name}.parquet")
                print(f"fixture {synthetic_name} (synthetic): {synthetic.height} rows")


if __name__ == "__main__":
    sessions_seed()
    fixture()
