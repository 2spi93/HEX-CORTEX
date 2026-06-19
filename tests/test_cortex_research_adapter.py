from hex_cortex.memory.cortex_research_adapter import build_cortex_research_adapter


def test_research_adapter_accepts_cited_result() -> None:
    adapter = build_cortex_research_adapter(
        searcher=lambda query: {
            "status": "ok",
            "summary": "verified",
            "citations": [{"url": "https://example.test/source"}],
        }
    )

    payload = adapter.handler({"query": "current facts"})

    assert payload["status"] == "ok"
    assert payload["summary"] == "verified"
    assert len(payload["citations"]) == 1
    assert payload["network_call_performed"] is True
    assert payload["external_effect_performed"] is False


def test_research_adapter_blocks_uncited_result() -> None:
    adapter = build_cortex_research_adapter(
        searcher=lambda query: {
            "status": "ok",
            "summary": "uncited",
            "citations": [],
        }
    )

    payload = adapter.handler({"query": "current facts"})

    assert payload["status"] == "blocked"
    assert payload["summary"] == "missing citations"
    assert payload["citations"] == []


def test_research_adapter_blocks_missing_query() -> None:
    adapter = build_cortex_research_adapter(
        searcher=lambda query: {
            "status": "ok",
            "summary": "unused",
            "citations": [{"url": "https://example.test/source"}],
        }
    )

    payload = adapter.handler({})

    assert payload["status"] == "blocked"
    assert payload["network_call_performed"] is False
