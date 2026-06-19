import json
from pathlib import Path

from hex_cortex.memory.cortex_world_training_cli import _parse_float_csv
from hex_cortex.memory.cortex_world_training_cli import build_parser
from hex_cortex.memory.cortex_world_training_cli import main


def test_parser_supports_capture() -> None:
    args = build_parser().parse_args(
        [
            "capture",
            "current.png",
            "next.png",
            "--comfy-root",
            "ComfyUI",
            "--action",
            "0,0,0,0",
            "--dataset-jsonl",
            "transitions.jsonl",
        ]
    )

    assert args.command == "capture"
    assert args.split == "auto"
    assert args.device == "cpu"


def test_parser_supports_train_and_promote() -> None:
    train = build_parser().parse_args(
        [
            "train",
            "manifest.json",
            "plan.json",
            "--comfy-root",
            "ComfyUI",
            "--output-dir",
            "candidate",
            "--operator-approved",
        ]
    )
    promote = build_parser().parse_args(
        [
            "promote",
            "candidate.json",
            "--registry-dir",
            "registry",
            "--operator-approved",
        ]
    )

    assert train.command == "train"
    assert train.operator_approved is True
    assert promote.command == "promote"
    assert promote.operator_approved is True


def test_float_csv_parser(capsys) -> None:
    assert _parse_float_csv("0,-0.5,1", "action") == [0.0, -0.5, 1.0]
    assert _parse_float_csv("bad", "action") is None
    payload = json.loads(capsys.readouterr().out)
    assert payload["blockers"] == ["action_invalid_csv"]


def test_audit_cli_on_repository(capsys) -> None:
    root = Path(__file__).resolve().parents[1]

    code = main(["audit", "--project-root", str(root)])
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload["architecture_ready"] is True
    assert payload["engineering_complete"] is True
