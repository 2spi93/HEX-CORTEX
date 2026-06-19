from __future__ import annotations

import json
from collections.abc import Callable
from urllib.error import URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

AuthResolver = Callable[[str], str | None]


def build_cortex_searxng_searcher(
    *,
    endpoint: str,
    timeout_seconds: float = 8.0,
    auth_ref: str | None = None,
    auth_resolver: AuthResolver | None = None,
):
    _validate_endpoint(endpoint)
    if timeout_seconds <= 0 or timeout_seconds > 30:
        raise ValueError("timeout_seconds must be in (0, 30]")

    def search(query: str) -> dict[str, object]:
        if not isinstance(query, str) or not query.strip():
            return {
                "status": "blocked",
                "summary": "empty query",
                "citations": [],
                "results": [],
            }
        headers = {
            "Accept": "application/json",
            "User-Agent": "HEX-CORTEX/1.0",
        }
        if auth_ref is not None:
            if auth_resolver is None:
                return _blocked("search auth resolver missing")
            token = auth_resolver(auth_ref)
            if not token:
                return _blocked("search auth value missing")
            headers["Authorization"] = f"Bearer {token}"
        params = urlencode(
            {
                "q": query.strip(),
                "format": "json",
                "language": "all",
                "safesearch": "1",
            }
        )
        request = Request(
            f"{endpoint.rstrip('/')}/search?{params}",
            headers=headers,
            method="GET",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw = response.read().decode("utf-8")
        except URLError as exc:
            return _blocked(f"search request failed: {exc.reason}")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return _blocked("search response is not valid json")
        if not isinstance(payload, dict):
            return _blocked("search response must be an object")
        results = _normalize_results(payload.get("results"))
        return {
            "status": "ok" if results else "blocked",
            "summary": (
                f"{len(results)} cited search results"
                if results
                else "no cited search results"
            ),
            "query": query.strip(),
            "results": results,
            "citations": [
                {
                    "url": row["url"],
                    "title": row["title"],
                    "source": "searxng",
                }
                for row in results
            ],
            "network_call_performed": True,
            "external_effect_performed": False,
            "auth_ref": auth_ref,
            "auth_value_persisted": False,
        }

    return search


def _normalize_results(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    rows = []
    seen = set()
    for item in value:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not isinstance(url, str) or not url.startswith(("http://", "https://")):
            continue
        if not isinstance(title, str) or not title.strip() or url in seen:
            continue
        seen.add(url)
        content = item.get("content")
        score = item.get("score")
        engines = item.get("engines")
        rows.append(
            {
                "url": url,
                "title": title.strip(),
                "snippet": content if isinstance(content, str) else "",
                "score": float(score) if isinstance(score, int | float) else None,
                "engines": (
                    sorted(str(engine) for engine in engines)
                    if isinstance(engines, list)
                    else []
                ),
            }
        )
        if len(rows) >= 20:
            break
    return rows


def _validate_endpoint(endpoint: str) -> None:
    parsed = urlparse(endpoint)
    if parsed.username or parsed.password:
        raise ValueError("search endpoint must not contain credentials")
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("search endpoint must use http or https")
    if not parsed.hostname:
        raise ValueError("search endpoint must include a hostname")
    local_hosts = {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme == "http" and parsed.hostname not in local_hosts:
        raise ValueError("remote search endpoints must use https")


def _blocked(summary: str) -> dict[str, object]:
    return {
        "status": "blocked",
        "summary": summary,
        "results": [],
        "citations": [],
        "network_call_performed": False,
        "external_effect_performed": False,
    }
