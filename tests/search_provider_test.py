from __future__ import annotations

import sys
from pathlib import Path as _BootstrapPath
sys.path.insert(0, str(_BootstrapPath(__file__).resolve().parents[1]))

from spriditis.search.searxng import SearXNGProvider


class Response:
    status_code = 200
    headers = {"Content-Type": "application/json"}
    def json(self):
        return {
            "results": [
                {
                    "url": "https://market.example/chair",
                    "title": "Ergonomic chair",
                    "content": "Lumbar support and mesh back",
                    "engines": ["duckduckgo", "brave"],
                    "score": 2.5,
                }
            ]
        }


class Session:
    def __init__(self):
        self.headers = {}
        self.calls = []
    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return Response()


session = Session()
provider = SearXNGProvider("https://search.example/", session=session)
hits = provider.search("chair", language="en", limit=5, safesearch=1)
assert len(hits) == 1
assert hits[0].url == "https://market.example/chair"
assert hits[0].engine == "duckduckgo,brave"
url, kwargs = session.calls[0]
assert url == "https://search.example/search"
assert kwargs["params"]["format"] == "json"
assert kwargs["params"]["q"] == "chair"
print("SEARCH PROVIDER TEST OK")
