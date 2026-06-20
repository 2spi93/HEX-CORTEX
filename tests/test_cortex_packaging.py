import json
import tomllib
from pathlib import Path


def test_python_scripts_expose_cortex_cli_and_operational_stdio() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = payload["project"]["scripts"]

    assert scripts["hexcortex"] == "hex_cortex.memory.cortex_cli:main"
    assert scripts["hexcortex-mcp"] == (
        "hex_cortex.memory.cortex_operational_stdio:serve_cortex_operational_stdio"
    )
    assert scripts["hexcortex-audit"] == (
        "hex_cortex.memory.cortex_operational_audit_cli:main"
    )
    assert scripts["hexcortex-genome"] == (
        "hex_cortex.memory.cortex_cognitive_genome_cli:main"
    )
    assert scripts["hexcortex-memory"] == (
        "hex_cortex.memory.cortex_cognitive_memory_cli:main"
    )


def test_claude_project_config_starts_operational_readonly_stdio_server() -> None:
    payload = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    server = payload["mcpServers"]["hex-cortex"]

    assert server["command"] == "python"
    assert server["args"] == [
        "-m",
        "hex_cortex.memory.cortex_operational_stdio",
    ]
    assert server["env"]["PYTHONPATH"] == "${CLAUDE_PROJECT_DIR:-.}/src"
    assert not any("TOKEN" in value for value in server["env"].values())


def test_codex_project_config_starts_same_operational_stdio_server() -> None:
    payload = tomllib.loads(
        Path(".codex/config.toml").read_text(encoding="utf-8")
    )
    server = payload["mcp_servers"]["hex-cortex"]

    assert server["command"] == "python"
    assert server["args"] == [
        "-m",
        "hex_cortex.memory.cortex_operational_stdio",
    ]
    assert server["cwd"] == "."
    assert server["env"] == {"PYTHONPATH": "./src"}
