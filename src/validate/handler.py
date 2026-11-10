"""Lambda entry point for validation. Event (all optional): {"years": [2024]}.

Reads raw objects, writes silver and quarantine Parquet to the same bucket, then emails a run
summary through SNS. Any failure is emailed too, then re-raised so the invocation shows as failed.
"""

import json
import os
from datetime import UTC, datetime

import boto3

from ingest.store import S3Store
from validate.checks import freshness_warnings
from validate.pipeline import validate_season
from validate.report import format_summary


def _stale(store, year, summary, now):
    pointer_key = f"raw/season={year}/_sessions_latest.json"
    if not store.exists(pointer_key):
        return []
    sessions = json.loads(store.get(json.loads(store.get(pointer_key))["key"]))
    ingested = {int(k) for k in summary["rule_counts_by_session"]}
    return freshness_warnings(sessions, ingested, now)


def lambda_handler(event, context):
    now = datetime.now(UTC)
    store = S3Store(os.environ["RAW_BUCKET"], boto3.client("s3"))
    topic = os.environ["SUMMARY_TOPIC_ARN"]
    sns = boto3.client("sns")
    try:
        results = []
        for year in event.get("years") or [now.year]:
            summary = validate_season(store, store, int(year))
            stale = _stale(store, int(year), summary, now)
            subject, body = format_summary(summary, stale)
            sns.publish(TopicArn=topic, Subject=subject[:100], Message=body)
            print(json.dumps({**summary, "stale_sessions": stale}, sort_keys=True))
            results.append({"year": year, "balanced": summary["balanced"], "stale": len(stale)})
        return {"results": results}
    except Exception as error:
        sns.publish(TopicArn=topic, Subject="F1 Pitwall validation FAILED",
                    Message=f"{type(error).__name__}: {error}")
        raise
