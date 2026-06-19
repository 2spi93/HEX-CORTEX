from __future__ import annotations

from collections.abc import Callable

Searcher = Callable[[str], dict[str, object]]


def describe_cortex_web() -> dict[str, object]:
    return {
        "adapter_type": "cortex_web",
        "unit_name": "web.search",
        "known_unit": True,
        "readonly": True,
        "requires_citations": True,
        "requires_source_quality": True,
        "requires_recency_for_time_sensitive_claims": True,
        "raw_page_persistence_allowed": False,
        "next_action": "register_web_search_unit",
    }


def build_cortex_web_search(searcher: Searcher) -> Searcher:
    def run(query: str) -> dict[str, object]:
        if not isinstance(query, str) or not query.strip():
            return {"status": "blocked", "summary": "missing query", "citations": []}
        payload = searcher(query)
        citations = payload.get("citations")
        if not isinstance(citations, list) or not citations:
            return {
                "status": "blocked",
                "summary": "missing citations",
                "citations": [],
            }
        return {
            "status": payload.get("status") if isinstance(payload.get("status"), str) else "ok",
            "summary": payload.get("summary") if isinstance(payload.get("summary"), str) else "web result received",
            "citations": citations,
            "raw_page_persisted": False,
        }

    return run
