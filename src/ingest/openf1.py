"""Throttled, retrying client for the OpenF1 historical API (no authentication).

Stdlib only so the Lambda zip needs no extra dependencies.
"""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://api.openf1.org/v1/"
USER_AGENT = "f1-pitwall-platform"


class OpenF1Error(RuntimeError):
    pass


class OpenF1Client:
    def __init__(
        self,
        min_interval=1.0,
        max_retries=5,
        timeout=60,
        opener=urllib.request.urlopen,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self.min_interval = min_interval
        self.max_retries = max_retries
        self.timeout = timeout
        self._opener = opener
        self._sleep = sleep
        self._clock = clock
        self._last_request = None

    def _throttle(self):
        if self._last_request is not None:
            wait = self._last_request + self.min_interval - self._clock()
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._clock()

    def get(self, endpoint, **params):
        """Return the list of rows for an endpoint; an empty result (HTTP 404) is []."""
        url = f"{BASE_URL}{endpoint}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        for attempt in range(self.max_retries + 1):
            self._throttle()
            try:
                with self._opener(request, timeout=self.timeout) as response:
                    payload = json.load(response)
            except urllib.error.HTTPError as error:
                if error.code == 404:
                    return []
                if error.code != 429 and not 500 <= error.code < 600:
                    raise OpenF1Error(f"HTTP {error.code} for {url}") from error
                delay = self._retry_delay(error, attempt)
            except (urllib.error.URLError, TimeoutError):
                delay = 2.0 * 2**attempt
            else:
                if not isinstance(payload, list):
                    raise OpenF1Error(f"Expected a JSON list from {url}, got {type(payload)}")
                return payload
            if attempt < self.max_retries:
                self._sleep(delay)
        raise OpenF1Error(f"Gave up after {self.max_retries + 1} attempts: {url}")

    @staticmethod
    def _retry_delay(error, attempt):
        retry_after = error.headers.get("Retry-After") if error.headers else None
        try:
            return float(retry_after)
        except (TypeError, ValueError):
            return 2.0 * 2**attempt
