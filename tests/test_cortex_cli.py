import json

from hex_cortex.memory.cortex_cli import main


def test_cli_units_outputs_json(capsys) -> None:
    code = main(["units"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["command"] == "units"
    assert payload["unit_count"] > 20
    names = {row["name"] for row in payload["units"]}
    assert "exec.call" in names
    assert "wiring.audit" in names


def test_cli_wiring_reports_static_ready(capsys) -> None:
    code = main(["wiring"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True
    assert payload["operational_ready"] is False


def test_cli_read_plan_runs(capsys) -> None:
    code = main(["read-plan"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["bus_allowed"] is True
    assert payload["result_count"] == payload["step_count"]


def test_cli_surface_accepts_boolean_runtime_facts(capsys) -> None:
    facts = json.dumps(
        {
            "cli_entrypoint_available": True,
            "service_packaging_available": False,
        }
    )

    code = main(["surface", "server", "--facts-json", facts])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["contract_ready"] is True
    assert payload["usable_ready"] is True
    assert payload["native_ready"] is False


def test_cli_surface_rejects_invalid_facts(capsys) -> None:
    code = main(["surface", "server", "--facts-json", "not-json"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["facts_json_invalid"]


def test_cli_manifest_unknown_surface_blocks(capsys) -> None:
    code = main(["manifest", "unknown"])
    payload = json.loads(capsys.readouterr().out)

    assert code == 2
    assert payload["state"] == "blocked"
