from urllib.parse import parse_qs, urlparse

import pytest

from hex_cortex.memory.cortex_searxng import audit_searxng_runtime
from hex_cortex.memory.cortex_searxng import build_searxng_searcher
from hex_cortex.memory.cortex_searxng import normalize_searxng_results
from hex_cortex.memory.cortex_searxng import validate_searxng_endpoint


def test_validate_searxng_endpoint_is_localhost_only() -> None:
    assert (
        validate_searxng_endpoint("http://127.0.0.1:8888/search")
        == "http://127.0.0.1:8888/search"
    )

    with pytest.raises(ValueError, match="localhost-only"):
        validate_searxng_endpoint("http://example.com:8888/search")


def test_searcher_builds_json_search_and_citation_pack() -> None:
    calls = []

    def transport(url: str, timeout: float) -> dict[str, object]:
        calls.append((url, timeout))
        return {
            "results": [
                {
                    "title": "Official HEX-CORTEX reference",
                    "url": "https://example.org/reference",
                    "content": "A cited result.",
                    "engine": "duckduckgo",
                }
            ]
        }

    searcher = build_searxng_searcher(transport=transport, max_items=4)
    payload = searcher("HEX CORTEX citations")

    parsed = urlparse(calls[0][0])
    params = parse_qs(parsed.query)
    assert parsed.path == "/search"
    assert params["q"] == ["HEX CORTEX citations"]
    assert params["format"] == ["json"]
    assert payload["status"] == "ok"
    assert payload["citation_pack"]["pack_allowed"] is True
    assert payload["citations"][0]["url"] == "https://example.org/reference"
    assert payload["query_persisted"] is False
    assert payload["raw_response_persisted"] is False


def test_searcher_blocks_empty_or_uncited_results() -> None:
    searcher = build_searxng_searcher(transport=lambda url, timeout: {"results": []})

    assert searcher("")["blockers"] == ["query_missing"]
    payload = searcher("no result query")
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["no_usable_citations"]


def test_searcher_records_only_transport_error_type() -> None:
    def transport(url: str, timeout: float) -> dict[str, object]:
        raise TimeoutError("sensitive upstream details")

    payload = build_searxng_searcher(transport=transport)("query")

    assert payload["status"] == "blocked"
    assert payload["error_type"] == "TimeoutError"
    assert "sensitive upstream details" not in str(payload)
    assert payload["raw_response_persisted"] is False


def test_normalize_searxng_results_drops_invalid_rows() -> None:
    rows = normalize_searxng_results(
        {
            "results": [
                {"title": "Good", "url": "https://example.org", "content": "ok"},
                {"title": "Bad", "url": "javascript:alert(1)"},
                {"title": "", "url": "https://example.net"},
            ]
        }
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Good"


def test_live_runtime_audit_requires_network_and_valid_citation_urls() -> None:
    search_result = {
        "status": "ok",
        "network_call_performed": True,
        "search_receipt_hash": "abc",
        "citations": [
            {"title": "Source", "url": "https://example.org", "snippet": "cited"}
        ],
    }

    payload = audit_searxng_runtime(search_result)

    assert payload["status"] == "operational"
    assert payload["operational_ready"] is True
    assert payload["runtime_fact_override"] == {"web_search_adapter_configured": True}


def test_live_runtime_audit_fails_closed_without_citations() -> None:
    payload = audit_searxng_runtime(
        {
            "status": "blocked",
            "network_call_performed": True,
            "citations": [],
        }
    )

    assert payload["status"] == "blocked"
    assert payload["runtime_fact_override"] == {"web_search_adapter_configured": False}
    assert "live_citations_missing" in payload["blockers"]
