import tomllib
from pathlib import Path


def test_hex_operator_console_entrypoints_are_declared() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    scripts = payload["project"]["scripts"]

    assert scripts["hexctl"] == "hex_cortex.memory.profile_control_cli:main"
    assert scripts["hexnext"] == "hex_cortex.memory.profile_next_action_cli:main"
