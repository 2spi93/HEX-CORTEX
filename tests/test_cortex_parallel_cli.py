import json

from hex_cortex.memory.cortex_cli import main


def test_runtime_auto_cli_is_offline_by_default(capsys) -> None:
    code = main(["runtime-auto", "--system", "Windows"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["status"] == "planned"
    assert payload["selected_runtime_id"] == "windows.ollama"
    assert payload["network_call_performed"] is False


def test_research_plan_cli(capsys) -> None:
    code = main(["research-plan"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["search_stack"]["search_engine"] == "searxng"
    assert payload["credential_policy"]["read_only_first"] is True


def test_federation_audit_cli_ready(capsys) -> None:
    facts = json.dumps(
        {
            "internal_api_available": True,
            "https_reverse_proxy_available": True,
            "private_or_tunneled_transport_available": True,
            "server_worker_queue_available": True,
            "signed_task_envelopes_available": True,
            "remote_receipts_available": True,
            "hermes_autodiscovery_available": True,
            "gtixt_read_only_audit_available": True,
        }
    )
    code = main(["federation-audit", "--facts-json", facts])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["federation_allowed"] is True
    assert payload["hermes"]["memory_policy"] == "separate_no_merge"
