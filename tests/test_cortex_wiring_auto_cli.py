import json

from hex_cortex.memory.cortex_cli import main


def test_wiring_auto_uses_runtime_probe_facts(capsys, tmp_path) -> None:
    memory_root = tmp_path / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    for filename in (
        "cortex_cli.py",
        "cortex_stdio.py",
        "cortex_rpc.py",
        "cortex_rpc_tools.py",
        "cortex_runtime_model_orchestration.py",
        "cortex_research_social_credentials.py",
        "cortex_server_federation_audit.py",
    ):
        (memory_root / filename).touch()

    code = main(["wiring-auto", "--project-root", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True
    assert payload["runtime_facts"]["mcp_server_available"] is True
    assert payload["runtime_facts"]["runtime_orchestration_available"] is True
    assert "native_mcp_server_not_available" not in payload["runtime_blockers"]
