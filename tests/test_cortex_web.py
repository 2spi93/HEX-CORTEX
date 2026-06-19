from hex_cortex.memory.cortex_web import build_cortex_web_search
from hex_cortex.memory.cortex_web import describe_cortex_web


def test_describe_cortex_web() -> None:
    payload = describe_cortex_web()

    assert payload["adapter_type"] == "cortex_web"
    assert payload["unit_name"] == "web.search"
    assert payload["known_unit"] is True
    assert payload["readonly"] is True
    assert payload["requires_citations"] is True
    assert payload["raw_page_persistence_allowed"] is False


def test_web_search_blocks_missing_query() -> None:
    runner = build_cortex_web_search(lambda query: {"status": "ok"})

    result = runner("")

    assert result == {"status": "blocked", "summary": "missing query", "citations": []}


def test_web_search_requires_citations() -> None:
    runner = build_cortex_web_search(lambda query: {"status": "ok", "summary": "found"})

    result = runner("Adinkra codes")

    assert result == {"status": "blocked", "summary": "missing citations", "citations": []}


def test_web_search_accepts_cited_result() -> None:
    runner = build_cortex_web_search(
        lambda query: {
            "status": "ok",
            "summary": "Adinkra topology is linked to doubly even codes.",
            "citations": ["source:arxiv"],
        }
    )

    result = runner("Adinkra codes")

    assert result["status"] == "ok"
    assert result["citations"] == ["source:arxiv"]
    assert result["raw_page_persisted"] is False
