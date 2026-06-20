from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

Searcher = Callable[[str], dict[str, object]]

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_MAX_CITATIONS = 8


def build_cortex_searxng_searcher(
    *,
    endpoint: str = "http://127.0.0.1:8888/search",
    timeout_seconds: float = 8.0,
    max_results: int = _MAX_CITATIONS,
) -> Searcher:
    """Build a localhost-only SearXNG searcher with mandatory citations.

    The returned callable conforms to the ``Searcher`` contract consumed by
    ``build_cortex_web_search`` / ``build_cortex_research_adapter``: it returns
    ``{"status", "summary", "citations"}`` and only keeps title+url pairs, never
    raw page bodies (``raw_page_persistence_allowed`` is False upstream).
    """
    _assert_local_endpoint(endpoint)
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("timeout_seconds must be in (0, 30]")
    if max_results <= 0 or max_results > 50:
        raise ValueError("max_results must be in (0, 50]")

    def search(query: str) -> dict[str, object]:
        if not isinstance(query, str) or not query.strip():
            return {"status": "blocked", "summary": "missing query", "citations": []}
        url = f"{endpoint}?{urlencode({'q': query.strip(), 'format': 'json'})}"
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - localhost only.
                raw = response.read().decode("utf-8")
        except URLError as exc:
            return {
                "status": "blocked",
                "summary": f"local search request failed: {exc.reason}",
                "citations": [],
            }
        return _extract(raw, max_results=max_results)

    return search


def _assert_local_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.scheme != "http":
        raise ValueError("endpoint must use http")
    if parsed.hostname not in _LOCAL_HOSTS:
        raise ValueError("endpoint must be localhost")
    if parsed.port is None:
        raise ValueError("endpoint must include an explicit port")


def _extract(raw: str, *, max_results: int) -> dict[str, object]:
    try:
        payload: dict[str, Any] = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "blocked", "summary": "invalid json response", "citations": []}
    results = payload.get("results")
    if not isinstance(results, list):
        return {"status": "blocked", "summary": "missing results", "citations": []}
    citations = _build_citations(results, max_results=max_results)
    if not citations:
        return {"status": "blocked", "summary": "missing citations", "citations": []}
    return {
        "status": "ok",
        "summary": f"{len(citations)} cited result(s) returned",
        "citations": citations,
        "raw_page_persisted": False,
    }


def _build_citations(
    results: list[Any],
    *,
    max_results: int,
) -> list[dict[str, str]]:
    citations: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        title = item.get("title")
        citations.append(
            {
                "title": title.strip() if isinstance(title, str) and title.strip() else url,
                "url": url,
            }
        )
        if len(citations) >= max_results:
            break
    return citations
