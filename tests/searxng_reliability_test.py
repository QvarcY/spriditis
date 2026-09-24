from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.search.base import SearchProviderError
from spriditis.search.searxng import SearXNGProvider


class Response:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload
        self.headers = headers or {"Content-Type": "application/json"}

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


class Session:
    def __init__(self, responses):
        self.headers = {}
        self.responses = list(responses)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        return self.responses.pop(0)


def payload(url="https://market.example/item"):
    return {"results": [{"url": url, "title": "Market item", "content": "chair"}]}


sleeps = []
session = Session([
    Response(503, headers={"Retry-After": "0"}),
    Response(200, payload()),
])
provider = SearXNGProvider(
    "https://search.example",
    session=session,
    max_retries=2,
    retry_base_seconds=0,
    sleep_func=sleeps.append,
)
hits = provider.search("chair", language="en", limit=5, safesearch=1)
assert len(hits) == 1
assert session.calls == 2

# 403 is configuration/non-retryable and must fail immediately.
session = Session([Response(403)])
provider = SearXNGProvider("https://search.example", session=session, max_retries=3, sleep_func=lambda _: None)
try:
    provider.search("chair", language="en", limit=5, safesearch=1)
    raise AssertionError("403 should fail")
except SearchProviderError as exc:
    assert exc.kind == "json_output_forbidden"
    assert exc.retryable is False
    assert exc.attempts == 1
    assert session.calls == 1

# Duplicate URLs from one provider response collapse before the crawler sees them.
session = Session([Response(200, {"results": [
    {"url": "https://market.example/item", "title": "A"},
    {"url": "https://market.example/item", "title": "A duplicate"},
    {"url": "mailto:test@example.com", "title": "invalid"},
]})])
provider = SearXNGProvider("https://search.example", session=session)
hits = provider.search("chair", language="en", limit=5, safesearch=1)
assert len(hits) == 1
assert hits[0].url == "https://market.example/item"

print("SEARXNG RELIABILITY TEST OK")
