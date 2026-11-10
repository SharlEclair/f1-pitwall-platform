"""Lambda entry point. Event (all optional): {"years": [2024], "refresh": false}.

An empty event (the weekly schedule) ingests the current year. A manual backfill passes years.
Completed sessions are skipped. The run stops starting new sessions when under 90 s remain, so a
backfill that needs more than one invocation is simply started again until nothing is left.
"""

import json
import os
from datetime import UTC, datetime

import boto3

from ingest.openf1 import OpenF1Client
from ingest.pipeline import run_season
from ingest.store import S3Store

STOP_BEFORE_TIMEOUT_MS = 90_000  # one session takes at most about 30 s; leave a safe margin


def lambda_handler(event, context):
    now = datetime.now(UTC)
    years = event.get("years") or [now.year]
    refresh = bool(event.get("refresh"))
    store = S3Store(os.environ["RAW_BUCKET"], boto3.client("s3"))
    client = OpenF1Client()

    def should_stop():
        return context.get_remaining_time_in_millis() < STOP_BEFORE_TIMEOUT_MS

    summaries = []
    for year in years:
        summary = run_season(client, store, int(year), now, refresh, should_stop)
        print(json.dumps(summary, sort_keys=True))
        summaries.append(summary)
    return {"summaries": summaries}
