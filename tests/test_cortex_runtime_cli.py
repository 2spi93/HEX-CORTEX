import json

from hex_cortex.memory.cortex_runtime_cli import main


def test_runtime_cli_lists_windows_and_optional_linux(capsys) -> None:
    code = main(
        [
            "targets",
            "--linux-endpoint",
            "https://llama.example.test",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert [row["target_id"] for row in payload["targets"]] == [
        "linux-llama-server",
        "windows-ollama",
    ]


def test_runtime_cli_selects_from_health_records(monkeypatch, capsys) -> None:
    def fake_probe(registry, timeout_seconds):
        return {
            "target_count": 1,
            "healthy_count": 1,
            "target_records": [
                {
                    "target_id": "windows-ollama",
                    "kind": "ollama",
                    "platform": "windows",
                    "healthy": True,
                    "priority": 90,
                    "latency_ms": 20.0,
                    "models": ["qwen3:8b"],
                    "loaded_model_count": 1,
                }
            ],
        }

    monkeypatch.setattr(
        "hex_cortex.memory.cortex_runtime_cli.probe_cortex_runtime_targets",
        fake_probe,
    )

    code = main(
        [
            "select",
            "--platform",
            "windows",
            "--model",
            "qwen3:8b",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["selected_target"]["target_id"] == "windows-ollama"
    assert payload["health_summary"]["healthy_count"] == 1


def test_runtime_cli_wiring_auto_uses_static_probe(capsys, tmp_path) -> None:
    code = main(
        [
            "wiring-auto",
            "--project-root",
            str(tmp_path),
            "--overrides-json",
            json.dumps({"mcp_server_available": True}),
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True
    assert payload["runtime_probe"]["network_probe_performed"] is False
