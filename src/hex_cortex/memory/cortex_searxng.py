from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener

from hex_cortex.memory.cortex_research_social_credentials import build_citation_pack

JsonTransport = Callable[[str, float], dict[str, object]]
_ALLOWED_HOSTS = {"127.0.0.1", "localhost", "::1"}


def build_searxng_searcher(
    *,
    endpoint: str = "http://127.0.0.1:8888/search",
    max_items: int = 8,
    timeout_seconds: float = 10.0,
    transport: JsonTransport | None = None,
) -> Callable[[str], dict[str, object]]:
    normalized_endpoint = validate_searxng_endpoint(endpoint)
    if not 1 <= max_items <= 20:
        raise ValueError("max_items must be in [1, 20]")
    if not 1.0 <= timeout_seconds <= 60.0:
        raise ValueError("timeout_seconds must be in [1, 60]")
    caller = transport or _http_get_json

    def search(query: str) -> dict[str, object]:
        if not isinstance(query, str) or not query.strip():
            return _blocked("query_missing", network_call_performed=False)
        query_value = query.strip()
        request_url = _build_search_url(normalized_endpoint, query_value)
        try:
            response = caller(request_url, timeout_seconds)
        except Exception as exc:  # noqa: BLE001 - only the exception type is retained.
            return {
                **_blocked("searxng_request_failed", network_call_performed=True),
                "error_type": type(exc).__name__,
                "endpoint": normalized_endpoint,
            }
        rows = normalize_searxng_results(response)
        citation_pack = build_citation_pack(query=query_value, rows=rows, max_items=max_items)
        citations = citation_pack["citations"]
        ready = citation_pack["pack_allowed"] is True and bool(citations)
        stable = {
            "endpoint": normalized_endpoint,
            "query_hash": hashlib.sha256(query_value.encode("utf-8")).hexdigest(),
            "citation_pack_hash": citation_pack["pack_hash"],
            "citation_count": len(citations),
            "ready": ready,
        }
        return {
            "status": "ok" if ready else "blocked",
            "summary": f"SearXNG returned {len(citations)} cited result(s)." if ready else "SearXNG returned no usable citations.",
            "citations": citations,
            "citation_pack": citation_pack,
            "endpoint": normalized_endpoint,
            "query_hash": stable["query_hash"],
            "query_persisted": False,
            "raw_response_persisted": False,
            "raw_page_content_persisted": False,
            "network_call_performed": True,
            "external_effect_performed": False,
            "search_receipt_hash": _stable_hash(stable),
            "blockers": [] if ready else ["no_usable_citations"],
            "next_action": "consume_citation_pack" if ready else "repair_searxng_sources",
        }

    return search


def audit_searxng_runtime(search_result: dict[str, object]) -> dict[str, object]:
    citations = search_result.get("citations")
    citation_rows = citations if isinstance(citations, list) else []
    valid_urls = [
        row.get("url")
        for row in citation_rows
        if isinstance(row, dict) and _is_http_url(row.get("url"))
    ]
    operational = (
        search_result.get("status") == "ok"
        and search_result.get("network_call_performed") is True
        and len(valid_urls) == len(citation_rows)
        and len(valid_urls) > 0
    )
    blockers: list[str] = []
    if search_result.get("network_call_performed") is not True:
        blockers.append("live_network_search_not_performed")
    if not citation_rows:
        blockers.append("live_citations_missing")
    elif len(valid_urls) != len(citation_rows):
        blockers.append("citation_url_invalid")
    if search_result.get("status") != "ok":
        blockers.append("searxng_search_not_ok")
    payload = {
        "audit_type": "searxng_live_citation_audit_v1",
        "status": "operational" if operational else "blocked",
        "operational_ready": operational,
        "citation_count": len(citation_rows),
        "valid_citation_url_count": len(valid_urls),
        "network_call_performed": search_result.get("network_call_performed") is True,
        "raw_response_persisted": False,
        "runtime_fact_override": {"web_search_adapter_configured": operational},
        "search_receipt_hash": search_result.get("search_receipt_hash"),
        "blockers": sorted(set(blockers)),
        "next_action": "apply_evidence_backed_runtime_override" if operational else "repair_live_research_runtime",
    }
    payload["audit_hash"] = _stable_hash(payload)
    return payload


def validate_searxng_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http":
        raise ValueError("SearXNG endpoint must use http")
    if parsed.hostname not in _ALLOWED_HOSTS:
        raise ValueError("SearXNG endpoint must be localhost-only")
    if parsed.port is None:
        raise ValueError("SearXNG endpoint must include an explicit port")
    if parsed.path.rstrip("/") != "/search":
        raise ValueError("SearXNG endpoint path must be /search")
    if parsed.query or parsed.fragment or parsed.username or parsed.password:
        raise ValueError("SearXNG endpoint must not contain credentials, query, or fragment")
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{parsed.port}/search"


def normalize_searxng_results(payload: dict[str, object]) -> list[dict[str, object]]:
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    rows: list[dict[str, object]] = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not _is_http_url(url) or not isinstance(title, str) or not title.strip():
            continue
        snippet_value = item.get("content")
        snippet = snippet_value if isinstance(snippet_value, str) else ""
        updated_at = item.get("publishedDate")
        if not isinstance(updated_at, str):
            updated_at = item.get("published_date") if isinstance(item.get("published_date"), str) else None
        rows.append(
            {
                "title": title.strip(),
                "url": str(url),
                "snippet": snippet.strip(),
                "updated_at": updated_at,
                "source_type": "unknown",
                "engine": item.get("engine") if isinstance(item.get("engine"), str) else None,
                "category": item.get("category") if isinstance(item.get("category"), str) else None,
            }
        )
    return rows


def _build_search_url(endpoint: str, query: str) -> str:
    params = urlencode(
        {
            "q": query,
            "format": "json",
            "language": "all",
            "safesearch": "1",
            "categories": "general",
        }
    )
    return f"{endpoint}?{params}"


def _http_get_json(url: str, timeout_seconds: float) -> dict[str, object]:
    request = Request(url, method="GET", headers={"Accept": "application/json"})
    opener = build_opener()
    with opener.open(request, timeout=timeout_seconds) as response:  # noqa: S310 - endpoint is localhost-only.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("SearXNG response must be a JSON object")
    return payload


def _is_http_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.hostname)


def _blocked(blocker: str, *, network_call_performed: bool) -> dict[str, object]:
    payload = {
        "status": "blocked",
        "summary": "SearXNG search blocked.",
        "citations": [],
        "query_persisted": False,
        "raw_response_persisted": False,
        "raw_page_content_persisted": False,
        "network_call_performed": network_call_performed,
        "external_effect_performed": False,
        "blockers": [blocker],
        "next_action": "repair_searxng_search",
    }
    payload["search_receipt_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
