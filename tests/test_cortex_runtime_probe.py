from pathlib import Path

import pytest

from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime


def test_runtime_probe_detects_static_components(tmp_path) -> None:
    memory_root = tmp_path / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    for filename in (
        "cortex_cli.py",
        "cortex_stdio.py",
        "cortex_rpc.py",
        "cortex_rpc_tools.py",
        "cortex_ollama_link.py",
        "cortex_openai_local.py",
        "cortex_project_adapter.py",
        "cortex_hardware_adapter.py",
        "cortex_service_adapter.py",
        "cortex_research_adapter.py",
    ):
        (memory_root / filename).write_text("", encoding="utf-8")
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text("", encoding="utf-8")
    (tmp_path / ".mcp.json").write_text("{}", encoding="utf-8")

    payload = probe_cortex_runtime(tmp_path)
    facts = payload["runtime_facts"]

    assert facts["cli_entrypoint_available"] is True
    assert facts["mcp_server_available"] is True
    assert facts["claude_project_configured"] is True
    assert facts["codex_project_configured"] is True
    assert facts["ollama_adapter_available"] is True
    assert facts["llama_cpp_adapter_available"] is True
    assert facts["local_model_runtime_available"] is False
    assert facts["project_adapter_available"] is False
    assert payload["network_probe_performed"] is False
    assert payload["process_probe_performed"] is False


def test_runtime_probe_accepts_explicit_boolean_overrides(tmp_path) -> None:
    payload = probe_cortex_runtime(
        tmp_path,
        overrides={
            "local_model_runtime_available": True,
            "ollama_endpoint_configured": True,
        },
    )

    assert payload["runtime_facts"]["local_model_runtime_available"] is True
    assert payload["runtime_facts"]["ollama_endpoint_configured"] is True


def test_runtime_probe_rejects_non_boolean_override(tmp_path) -> None:
    with pytest.raises(ValueError, match="boolean"):
        probe_cortex_runtime(
            tmp_path,
            overrides={"bad": "yes"},  # type: ignore[dict-item]
        )


def test_runtime_probe_resolves_project_root(tmp_path) -> None:
    payload = probe_cortex_runtime(Path(tmp_path) / ".")

    assert payload["project_root"] == str(tmp_path.resolve())
