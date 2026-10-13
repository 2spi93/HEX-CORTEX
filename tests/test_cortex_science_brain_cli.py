"""End-to-end operator CLI permissions, CPU-only adapter and redacted answer."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_science_brain_cli as cli


def test_dry_run_writes_nothing_and_calls_no_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = [
        "--project-root", str(tmp_path), "--domain", "chemistry",
        "--example", "--model", "test",
    ]
    assert cli.main([*args, "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "configuration_only"
    assert result["num_gpu"] == 0
    assert result["model_calls_performed"] == 0


def test_without_approvals_no_model_called(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli.main([
        "--project-root", str(tmp_path), "--domain", "mathematics",
        "--example", "--model", "test",
    ]) == 2
    assert json.loads(capsys.readouterr().out)["model_calls"] == 0


@pytest.mark.parametrize("domain", ["mathematics", "physics", "chemistry"])
def test_cli_uses_cpu_and_existing_cells_with_stub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str], domain: str,
) -> None:
    call_args: list[dict[str, object]] = []

    class FakeBrain:
        def __init__(self, **kwargs: object) -> None:
            call_args.append(kwargs)

        def __call__(self, _model: str, _task: object) -> str:
            return "verified-response"

    monkeypatch.setattr(cli, "LocalOllamaBrain", FakeBrain)
    assert cli.main([
        "--project-root", str(tmp_path), "--domain", domain,
        "--example", "--model", "local-test",
        "--approve-science", "--approve-model",
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert result["scientific_domain"] == domain
    assert result["answer"] is None
    assert result["answer_sha256"]
    assert result["model_calls"] == 1
    assert call_args[0]["num_gpu"] == 0
    assert result["files_saved"] is False
