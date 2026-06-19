import json

import pytest

import hex_cortex.memory.cortex_searxng as module
from hex_cortex.memory.cortex_searxng import build_cortex_searxng_searcher


class Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_searxng_searcher_returns_citations(monkeypatch) -> None:
    observed = {}

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        return Response(
            {
                "results": [
                    {
                        "url": "https://docs.example.test/a",
                        "title": "A",
                        "content": "snippet",
                        "score": 2.5,
                        "engines": ["bing", "duckduckgo"],
                    }
                ]
            }
        )

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    search = build_cortex_searxng_searcher(
        endpoint="http://127.0.0.1:8088",
    )

    payload = search("world model")

    assert payload["status"] == "ok"
    assert payload["citations"][0]["url"] == "https://docs.example.test/a"
    assert "format=json" in observed["url"]
    assert observed["timeout"] == 8.0


def test_searxng_rejects_remote_plain_http() -> None:
    with pytest.raises(ValueError, match="https"):
        build_cortex_searxng_searcher(endpoint="http://search.example.test")


def test_searxng_uses_auth_reference_without_persisting_value(monkeypatch) -> None:
    def fake_urlopen(request, timeout):
        assert request.headers["Authorization"] == "Bearer token-value"
        return Response({"results": []})

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    search = build_cortex_searxng_searcher(
        endpoint="https://search.example.test",
        auth_ref="keyring://hex-cortex/search/main",
        auth_resolver=lambda ref: "token-value",
    )

    payload = search("query")

    assert "token-value" not in str(payload)
    assert payload["auth_value_persisted"] is False
