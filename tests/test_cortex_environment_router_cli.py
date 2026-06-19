import json
from pathlib import Path

from hex_cortex.memory.cortex_environment_router_cli import _read_json_object
from hex_cortex.memory.cortex_environment_router_cli import _write_json
from hex_cortex.memory.cortex_environment_router_cli import build_parser


def test_route_parser_supports_canonical_output_file() -> None:
    args = build_parser().parse_args(
        [
            "route",
            "active.json",
            "current.png",
            "goal.png",
            "actions.json",
            "--environment-root",
            "workspace",
            "--domain",
            "screen_lab_v1",
            "--output",
            "route-latest.json",
        ]
    )

    assert args.command == "route"
    assert args.output == "route-latest.json"


def test_read_json_object_accepts_windows_powershell_utf16(tmp_path: Path) -> None:
    path = tmp_path / "route.json"
    path.write_text(json.dumps({"status": "advisory_ready"}), encoding="utf-16")

    payload = _read_json_object(path, "route")

    assert payload == {"status": "advisory_ready"}


def test_write_json_uses_utf8_without_bom(tmp_path: Path) -> None:
    path = tmp_path / "nested" / "route.json"

    _write_json(path, {"status": "advisory_ready"})

    raw = path.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8")) == {"status": "advisory_ready"}
