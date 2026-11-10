"""Object stores for immutable raw data: local folder (tests, dev) and S3 (Lambda)."""

import hashlib
import json
from pathlib import Path


def canonical_bytes(rows):
    """Stable serialisation so identical content always hashes identically."""
    return json.dumps(rows, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256_hex(data):
    return hashlib.sha256(data).hexdigest()


class LocalStore:
    def __init__(self, root):
        self.root = Path(root)

    def exists(self, key):
        return (self.root / key).exists()

    def put(self, key, data):
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key):
        return (self.root / key).read_bytes()

    def list_keys(self, prefix):
        return sorted(
            p.relative_to(self.root).as_posix()
            for p in self.root.rglob("*")
            if p.is_file() and p.relative_to(self.root).as_posix().startswith(prefix)
        )


class S3Store:
    def __init__(self, bucket, client):
        self.bucket = bucket
        self.client = client

    def exists(self, key):
        from botocore.exceptions import ClientError

        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except ClientError as error:
            if error.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
                return False
            raise
        return True

    def put(self, key, data):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data)

    def get(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def list_keys(self, prefix):
        keys = []
        for page in self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        ):
            keys += [item["Key"] for item in page.get("Contents", [])]
        return sorted(keys)
