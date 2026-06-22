import tomllib
from pathlib import Path


def test_cognitive_loop_cli_is_packaged() -> None:
    payload = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    assert payload["project"]["scripts"]["hexcortex-loop"] == (
        "hex_cortex.memory.cortex_cognitive_loop_cli:main"
    )
