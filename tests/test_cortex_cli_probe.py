import json

from hex_cortex.memory.cortex_cli import main


def test_cli_probe_is_filesystem_only(capsys, tmp_path) -> None:
    code = main(["probe", "--project-root", str(tmp_path)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["probe_type"] == "cortex_runtime_probe"
    assert payload["filesystem_only"] is True
    assert payload["network_probe_performed"] is False
    assert payload["process_probe_performed"] is False


def test_cli_surface_auto_uses_probe_facts(capsys, tmp_path) -> None:
    code = main(
        [
            "surface-auto",
            "server",
            "--project-root",
            str(tmp_path),
            "--overrides-json",
            json.dumps({"cli_entrypoint_available": True}),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["contract_ready"] is True
    assert payload["usable_ready"] is True
    assert payload["native_ready"] is False
    assert payload["runtime_probe"]["network_probe_performed"] is False
