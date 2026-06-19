from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urlparse

SearchHandler = Callable[[str], dict[str, object]]
CrawlHandler = Callable[[str], dict[str, object]]


def run_cortex_research_flow(
    query: str,
    *,
    searcher: SearchHandler,
    crawler: CrawlHandler | None = None,
    result_limit: int = 8,
    crawl_limit: int = 4,
) -> dict[str, object]:
    if not query.strip():
        return _blocked("empty_query")
    if result_limit < 1 or result_limit > 20:
        raise ValueError("result_limit must be in [1, 20]")
    if crawl_limit < 0 or crawl_limit > result_limit:
        raise ValueError("crawl_limit must be in [0, result_limit]")
    search_payload = searcher(query.strip())
    if search_payload.get("status") != "ok":
        return _blocked("search_stage_blocked")
    candidates = _select_sources(search_payload.get("results"), limit=result_limit)
    if not candidates:
        return _blocked("missing_citations")
    crawled = []
    if crawler is not None:
        for row in candidates[:crawl_limit]:
            payload = crawler(str(row["url"]))
            crawled.append(_crawl_receipt(row, payload))
    return {
        "status": "ok",
        "query": query.strip(),
        "result_count": len(candidates),
        "crawl_count": len(crawled),
        "results": candidates,
        "crawled": crawled,
        "citations": [
            {
                "url": row["url"],
                "title": row["title"],
                "source": row["source"],
            }
            for row in candidates
        ],
        "raw_page_persisted": False,
        "network_call_performed": True,
        "external_effect_performed": False,
        "next_action": "synthesize_cited_answer",
    }


def _select_sources(value: object, *, limit: int) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    rows = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        title = item.get("title")
        if not isinstance(url, str) or not isinstance(title, str):
            continue
        host = urlparse(url).hostname or "unknown"
        score = item.get("score")
        rows.append(
            {
                "url": url,
                "title": title,
                "snippet": item.get("snippet", ""),
                "score": float(score) if isinstance(score, int | float) else 0.0,
                "host": host,
                "source": "searxng",
                "original_rank": index,
            }
        )
    rows.sort(key=lambda row: (-float(row["score"]), int(row["original_rank"])))
    selected = []
    host_counts: dict[str, int] = {}
    for row in rows:
        host = str(row["host"])
        if host_counts.get(host, 0) >= 2:
            continue
        selected.append(row)
        host_counts[host] = host_counts.get(host, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def _crawl_receipt(
    source: dict[str, object],
    payload: dict[str, object],
) -> dict[str, object]:
    markdown = payload.get("markdown")
    return {
        "url": source["url"],
        "title": source["title"],
        "status": payload.get("status", "blocked"),
        "content_length": len(markdown) if isinstance(markdown, str) else 0,
        "content_hash": payload.get("content_hash"),
        "raw_content_persisted": False,
    }


def _blocked(blocker: str) -> dict[str, object]:
    return {
        "status": "blocked",
        "blockers": [blocker],
        "results": [],
        "crawled": [],
        "citations": [],
        "network_call_performed": False,
        "external_effect_performed": False,
        "next_action": "repair_research_flow",
    }
