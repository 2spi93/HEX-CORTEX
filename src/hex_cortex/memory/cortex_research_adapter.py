from __future__ import annotations

from collections.abc import Callable

from hex_cortex.memory.cortex_gateway import CortexAdapter
from hex_cortex.memory.cortex_searxng import build_searxng_searcher
from hex_cortex.memory.cortex_web import build_cortex_web_search

SearchHandler = Callable[[str], dict[str, object]]


def build_cortex_research_adapter(
    *,
    searcher: SearchHandler,
) -> CortexAdapter:
    if not callable(searcher):
        raise ValueError("searcher must be callable")
    guarded_search = build_cortex_web_search(searcher)

    def handler(request: dict[str, object]) -> dict[str, object]:
        query = request.get("query")
        if not isinstance(query, str):
            return {
                "status": "blocked",
                "summary": "missing query",
                "citations": [],
                "network_call_performed": False,
                "external_effect_performed": False,
            }
        payload = guarded_search(query)
        return {
            **payload,
            "network_call_performed": payload.get("network_call_performed", True),
            "external_effect_performed": False,
        }

    return CortexAdapter(
        name="research.web",
        lane="tool",
        handler=handler,
        description="Read-only web research adapter with mandatory citations.",
        network_capable=True,
        auto_safe_capable=True,
    )


def build_live_cortex_research_adapter(
    *,
    endpoint: str = "http://127.0.0.1:8888/search",
    max_items: int = 8,
    timeout_seconds: float = 10.0,
) -> CortexAdapter:
    return build_cortex_research_adapter(
        searcher=build_searxng_searcher(
            endpoint=endpoint,
            max_items=max_items,
            timeout_seconds=timeout_seconds,
        )
    )
