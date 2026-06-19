import tomllib
from pathlib import Path


def test_wave3_commands_are_packaged() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = payload["project"]["scripts"]

    assert scripts["hexcortex-runtime"] == (
        "hex_cortex.memory.cortex_runtime_cli:main"
    )
    assert scripts["hexcortex-http"] == (
        "hex_cortex.memory.cortex_http_readonly:serve_cortex_http"
    )
