"""Operator-facing science CLI demos have no external model dependency."""
from __future__ import annotations

import json

import pytest

from hex_cortex.core.cortex_verified_science_circuit_cli import main


@pytest.mark.parametrize("domain", ["mathematics", "physics", "chemistry"])
def test_three_public_demonstrations(
    domain: str, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--domain", domain, "--example", "--approve-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "verified_science_circuit"
    assert report["domain"] == domain
    assert report["verified_cell_count"] == 1
    assert report["spine_integrity_ok"] is True
    assert report["model_called"] is False


def test_dry_run_without_computation(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--domain", "chemistry", "--example", "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "configuration_only"
    assert report["calculation_performed"] is False


def test_explicit_approval_required(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["--domain", "mathematics", "--example"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["spine_event_count"] == 0
