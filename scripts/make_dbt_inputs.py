"""Create the dbt seed and the small DuckDB fixture from the validator's local output.

Reads (after `aws s3 sync`): data/silver, data/quarantine, data/raw sessions listing.
Writes: dbt/seeds/sessions.csv (all 2024 race and sprint sessions) and
        dbt/fixtures/raw/<table>.parquet (three races, for CI on DuckDB).
Only facts and counts are copied; no secrets are involved.
"""

import csv
import glob
import json
from pathlib import Path

import polars as pl

ROOT = Path(__file__).resolve().parent.parent
FIXTURE_SESSIONS = (9488, 9590, 9523)  # Melbourne (VSC), Monza (clean), Monaco (red flag)
ENDPOINTS = ("laps", "stints", "pit", "drivers", "race_control", "weather")


def sessions_seed():
    listing = sorted(ROOT.glob("data/raw/season=2024/endpoint=sessions/*.json"))
    sessions = json.loads(listing[0].read_text())
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


if __name__ == "__main__":
    sessions_seed()
    fixture()
