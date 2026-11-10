import io
import json
import urllib.error

import pytest

from ingest.openf1 import OpenF1Client, OpenF1Error


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def http_error(code, body=b"{}", headers=None):
    return urllib.error.HTTPError("u", code, "x", headers or {}, io.BytesIO(body))


def make_client(script, sleeps, clock_values=None):
    calls = []
    script = list(script)

    def opener(request, timeout):
        calls.append(request.full_url)
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return FakeResponse(json.dumps(item).encode())

    now = [0.0]

    def sleep(seconds):
        sleeps.append(seconds)
        now[0] += seconds

    client = OpenF1Client(min_interval=1.0, opener=opener, sleep=sleep, clock=lambda: now[0])
    return client, calls


def test_returns_rows_and_builds_url():
    client, calls = make_client([[{"a": 1}]], [])
    assert client.get("laps", session_key=9590) == [{"a": 1}]
    assert calls == ["https://api.openf1.org/v1/laps?session_key=9590"]


def test_throttles_consecutive_requests():
    sleeps = []
    client, _ = make_client([[], []], sleeps)
    client.get("laps", session_key=1)
    client.get("laps", session_key=2)
    assert sleeps == [1.0]


def test_retries_on_429_using_retry_after():
    sleeps = []
    script = [http_error(429, headers={"Retry-After": "7"}), [{"ok": 1}]]
    client, calls = make_client(script, sleeps)
    assert client.get("pit", session_key=1) == [{"ok": 1}]
    assert 7.0 in sleeps
    assert len(calls) == 2


def test_no_results_404_is_empty_list():
    body = b'{"detail":"No results found."}'
    client, _ = make_client([http_error(404, body)], [])
    assert client.get("laps", session_key=1) == []


def test_other_client_error_raises_without_retry():
    client, calls = make_client([http_error(400)], [])
    with pytest.raises(OpenF1Error):
        client.get("laps", session_key=1)
    assert len(calls) == 1


def test_gives_up_after_max_retries():
    client, calls = make_client([http_error(503)] * 6, [])
    with pytest.raises(OpenF1Error):
        client.get("laps", session_key=1)
    assert len(calls) == 6


def test_non_list_payload_is_rejected():
    client, _ = make_client([{"unexpected": "shape"}], [])
    with pytest.raises(OpenF1Error):
        client.get("laps", session_key=1)
