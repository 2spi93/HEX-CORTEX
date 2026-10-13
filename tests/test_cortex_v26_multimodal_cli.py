"""Operator dry run and denial for local vision and simulated voice."""
from __future__ import annotations

import json

import pytest

from hex_cortex.memory import (
    cortex_local_vision_cli_v26 as vision,
    cortex_voice_simulation_cli_v26 as voice,
)


def test_local_vision_dry_run_does_not_access_file(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert vision.main([
        "--image", "missing.png", "--dry-run"
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["encoder_called"] is False
    assert report["files_read"] is False
    assert report["network_allowed"] is False
    assert report["device"] == "cpu"


def test_vision_requires_explicit_approvals(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert vision.main(["--image", "missing.png"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["encoder_called"] is False


def test_voice_cli_operator_approvals_and_simulated_effect_only(
    capsys: pytest.CaptureFixture[str],
) -> None:
    args = ["--transcript", "simule le mouvement"]
    assert voice.main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["physical_action_executed"] is False
    assert voice.main(args) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "blocked"
    assert voice.main([
        *args, "--approve-transcript", "--approve-simulation"
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "simulation_only"
    assert result["virtual_object_state"]["x"] == 0.5
    assert result["physical_action_executed"] is False
