import json

import hex_cortex.memory.cortex_searxng as searxng
from hex_cortex.memory.cortex_research_web_cli import main


def _capture(capsys) -> dict:
    return json.loads(capsys.readouterr().out)


def test_describe_is_cold(capsys) -> None:
    assert main(["describe"]) == 0
    payload = _capture(capsys)
    assert payload["unit_name"] == "web.search"
    assert payload["requires_citations"] is True


def test_search_blocked_without_operator_approval(capsys) -> None:
    assert main(["search", "kernel"]) == 2
    payload = _capture(capsys)
    assert payload["status"] == "blocked"
    assert payload["network_call_performed"] is False
    assert "operator-approved" in payload["summary"]


def test_search_blocks_remote_endpoint(capsys) -> None:
    code = main(
        ["search", "kernel", "--operator-approved", "--endpoint", "http://evil.example:8888/search"]
    )
    assert code == 2
    payload = _capture(capsys)
    assert payload["status"] == "blocked"
    assert payload["network_call_performed"] is False


def test_search_live_returns_citations(capsys, monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps(
                {"results": [{"title": "Hit", "url": "https://hit.example"}]}
            ).encode("utf-8")

    monkeypatch.setattr(searxng, "urlopen", lambda request, timeout: FakeResponse())

    assert main(["search", "kernel", "--operator-approved"]) == 0
    payload = _capture(capsys)
    assert payload["status"] == "ok"
    assert payload["network_call_performed"] is True
    assert payload["citations"] == [{"title": "Hit", "url": "https://hit.example"}]
    assert payload["raw_page_persisted"] is False
