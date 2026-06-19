from hex_cortex.memory.cortex_research_flow import run_cortex_research_flow


def test_research_flow_diversifies_sources_and_crawls() -> None:
    searcher = lambda query: {
        "status": "ok",
        "results": [
            {"url": "https://a.test/1", "title": "A1", "score": 10},
            {"url": "https://a.test/2", "title": "A2", "score": 9},
            {"url": "https://a.test/3", "title": "A3", "score": 8},
            {"url": "https://b.test/1", "title": "B1", "score": 7},
        ],
    }
    crawler = lambda url: {
        "status": "ok",
        "markdown": "content",
        "content_hash": f"hash:{url}",
    }

    payload = run_cortex_research_flow(
        "query",
        searcher=searcher,
        crawler=crawler,
        result_limit=4,
        crawl_limit=2,
    )

    assert payload["status"] == "ok"
    assert payload["result_count"] == 3
    assert payload["crawl_count"] == 2
    assert {row["host"] for row in payload["results"]} == {"a.test", "b.test"}
    assert all(row["raw_content_persisted"] is False for row in payload["crawled"])
    assert len(payload["citations"]) == 3


def test_research_flow_blocks_without_citations() -> None:
    payload = run_cortex_research_flow(
        "query",
        searcher=lambda query: {"status": "ok", "results": []},
    )

    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["missing_citations"]


def test_research_flow_validates_limits() -> None:
    searcher = lambda query: {"status": "ok", "results": []}

    try:
        run_cortex_research_flow("query", searcher=searcher, result_limit=0)
    except ValueError as exc:
        assert "result_limit" in str(exc)
    else:
        raise AssertionError("expected result_limit validation")
