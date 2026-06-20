import json

from hex_cortex.memory.cortex_research_runtime_cli import build_parser
from hex_cortex.memory.cortex_research_runtime_cli import main


def test_research_cli_parses_live_audit() -> None:
    args = build_parser().parse_args(
        [
            "audit",
            "HEX CORTEX",
            "--network",
            "--pretty",
        ]
    )

    assert args.command == "audit"
    assert args.network is True
    assert args.endpoint == "http://127.0.0.1:8888/search"


def test_research_cli_requires_explicit_network_authorization(capsys) -> None:
    code = main(["search", "HEX CORTEX", "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "planned"
    assert payload["network_call_performed"] is False
    assert payload["blockers"] == ["network_execution_not_authorized"]


def test_research_cli_rejects_nonlocal_endpoint(capsys) -> None:
    code = main(
        [
            "audit",
            "HEX CORTEX",
            "--endpoint",
            "http://example.com:8888/search",
            "--network",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert payload["network_call_performed"] is False
    assert "localhost-only" in payload["blockers"][0]
