"""Lambda entry point. Event (all optional): {"years": [2024], "refresh": false}.

An empty event (the weekly schedule) ingests the current year. A manual backfill passes years.
Completed sessions are skipped, so a run that times out can simply be started again.
"""

import json
import os
from datetime import UTC, datetime

import boto3

from ingest.openf1 import OpenF1Client
from ingest.pipeline import run_season
from ingest.store import S3Store


def lambda_handler(event, context):
    now = datetime.now(UTC)
    years = event.get("years") or [now.year]
    refresh = bool(event.get("refresh"))
    store = S3Store(os.environ["RAW_BUCKET"], boto3.client("s3"))
    client = OpenF1Client()

    summaries = []
    for year in years:
        summary = run_season(client, store, int(year), now, refresh)
        print(json.dumps(summary, sort_keys=True))
        summaries.append(summary)
    return {"summaries": summaries}
