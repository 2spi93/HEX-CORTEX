import json

import pytest

import hex_cortex.memory.cortex_searxng as module
from hex_cortex.memory.cortex_searxng import build_cortex_searxng_searcher
from hex_cortex.memory.cortex_web import build_cortex_web_search


def test_searxng_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        build_cortex_searxng_searcher(endpoint="http://example.invalid:8888/search")


def test_searxng_rejects_missing_port() -> None:
    with pytest.raises(ValueError, match="port"):
        build_cortex_searxng_searcher(endpoint="http://localhost/search")


def test_searxng_rejects_bad_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_seconds"):
        build_cortex_searxng_searcher(timeout_seconds=0)


def test_extract_builds_citations_and_drops_bodies() -> None:
    raw = json.dumps(
        {
            "results": [
                {"title": "  Result A  ", "url": "https://a.example/x", "content": "body"},
                {"title": "", "url": "http://b.example/y"},
                {"title": "no url", "url": "ftp://nope"},
                "not-a-dict",
            ]
        }
    )

    result = module._extract(raw, max_results=8)

    assert result["status"] == "ok"
    assert result["raw_page_persisted"] is False
    assert result["citations"] == [
        {"title": "Result A", "url": "https://a.example/x"},
        {"title": "http://b.example/y", "url": "http://b.example/y"},
    ]


def test_extract_blocks_when_no_citations() -> None:
    raw = json.dumps({"results": []})

    result = module._extract(raw, max_results=8)

    assert result["status"] == "blocked"
    assert result["summary"] == "missing citations"
    assert result["citations"] == []


def test_extract_respects_max_results() -> None:
    raw = json.dumps(
        {"results": [{"title": f"t{i}", "url": f"https://e/{i}"} for i in range(10)]}
    )

    result = module._extract(raw, max_results=3)

    assert len(result["citations"]) == 3


def test_searcher_gets_localhost_json(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"results": [{"title": "Hit", "url": "https://hit.example"}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    searcher = build_cortex_searxng_searcher(timeout_seconds=3)

    result = searcher("local first intelligence kernel")

    assert result["status"] == "ok"
    assert result["citations"] == [{"title": "Hit", "url": "https://hit.example"}]
    assert len(calls) == 1
    request, timeout = calls[0]
    assert timeout == 3
    assert request.get_method() == "GET"
    assert request.full_url.startswith("http://127.0.0.1:8888/search?")
    assert "format=json" in request.full_url
    assert "q=local+first+intelligence+kernel" in request.full_url


def test_searcher_blocks_empty_query() -> None:
    searcher = build_cortex_searxng_searcher()

    assert searcher("   ") == {"status": "blocked", "summary": "missing query", "citations": []}


def test_pipeline_through_web_contract(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"results": [{"title": "Cited", "url": "https://cited.example"}]}
            ).encode("utf-8")

    monkeypatch.setattr(module, "urlopen", lambda request, timeout: FakeResponse())
    guarded = build_cortex_web_search(build_cortex_searxng_searcher())

    result = guarded("query")

    assert result["status"] == "ok"
    assert result["citations"] == [{"title": "Cited", "url": "https://cited.example"}]
    assert result["raw_page_persisted"] is False
