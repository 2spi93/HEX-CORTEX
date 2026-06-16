import tomllib
from pathlib import Path


def test_hexctl_console_entrypoint_is_declared() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert payload["project"]["scripts"]["hexctl"] == "hex_cortex.memory.profile_control_cli:main"
