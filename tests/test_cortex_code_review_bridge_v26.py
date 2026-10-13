"""One restricted code file enters actual Harness and structured-plan parser."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_code_review_bridge_v26 import review_local_code
from hex_cortex.memory.cortex_code_review_cli_v26 import main
from hex_cortex.memory.cortex_local_harness_v2 import Task


def _file(tmp_path: Path) -> Path:
    p = tmp_path / "example.py"
    p.write_text("import math\ndef area(x):\n    return x*x\n", encoding="utf-8")
    return p


def _reply(name: str = "example.py") -> str:
    return json.dumps({
        "summary": "Evaluate whether function inputs should be validated",
        "focus_areas": ["testing"],
        "candidate_files": [name],
        "proposed_changes": [{
            "area": "testing", "file": name,
            "objective": "Cover edge cases",
            "change": "Add zero and negative input tests",
            "confidence": .9,
        }],
        "tests": ["python -m pytest -q"],
        "risks": ["No mutation approved"],
        "unknowns": ["Desired units unknown"],
    })


def test_ast_only_read_only_result(tmp_path: Path) -> None:
    path = _file(tmp_path)
    report = review_local_code(
        project_root=tmp_path, file_path=path,
        model_id="none", approve_read=True,
    )
    assert report["status"] == "static_inspection"
    assert report["features"]["functions"] == 1
    assert report["source_sent_to_model"] is False
    assert report["files_written"] is False


def test_structured_plan_requires_real_harness_and_grounded_files(tmp_path: Path) -> None:
    path = _file(tmp_path)
    calls: list[str] = []

    def brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return _reply("another_file.py")

    report = review_local_code(
        project_root=tmp_path, file_path=path,
        model_id="test", brain=brain,
        approve_read=True, approve_model=True,
    )
    assert report["status"] == "reviewed"
    assert report["model_calls"] == 1
    assert report["plan_status"] == "valid"
    assert report["invalid_paths"] == ["another_file.py"]
    assert report["plan"]["candidate_files"] == []
    assert report["plan"]["proposed_changes"][0]["file"] is None
    assert report["harness_replay_verified"] is True
    assert report["files_written"] is False
    assert report["patch_applied"] is False
    assert "return x*x" not in calls[0]


def test_code_source_explicitly_shared_ephemerally_only(tmp_path: Path) -> None:
    path = _file(tmp_path)
    prompts: list[str] = []

    def brain(_model: str, task: Task) -> str:
        prompts.append(task.instruction)
        return _reply()

    report = review_local_code(
        project_root=tmp_path, file_path=path,
        model_id="test", brain=brain, approve_read=True,
        approve_model=True, approve_share_source=True,
    )
    assert report["source_sent_to_model"] is True
    assert "return x*x" in prompts[0]
    assert report["status"] == "reviewed"
    assert report["patch_applied"] is False


def test_potential_embedded_secret_blocks_model_sharing(tmp_path: Path) -> None:
    path = tmp_path / "code.py"
    path.write_text("API_KEY = '12345678901234567890'\n", encoding="utf-8")
    calls: list[str] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append("called")
        return _reply()

    with pytest.raises(ValueError, match="potential_secret_in_source"):
        review_local_code(
            project_root=tmp_path, file_path=path,
            model_id="test", brain=brain,
            approve_read=True, approve_model=True,
            approve_share_source=True,
        )
    assert calls == []


def test_no_file_read_without_approval(tmp_path: Path) -> None:
    report = review_local_code(
        project_root=tmp_path, file_path=_file(tmp_path),
        model_id="test", approve_read=False,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0


def test_cli_dry_run_never_loads_code_or_model(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["--file", "nonexistent.py", "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "configuration_only"
    assert report["files_read"] is False


def test_cli_local_cpu_model_adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from hex_cortex.memory import cortex_code_review_cli_v26 as cli
    path = _file(tmp_path)
    configurations: list[dict] = []

    class FakeBrain:
        def __init__(self, **kwargs: object) -> None:
            configurations.append(kwargs)

        def __call__(self, _model: str, _task: Task) -> str:
            return _reply()

    monkeypatch.setattr(cli, "LocalOllamaBrain", FakeBrain)
    assert cli.main([
        "--project-root", str(tmp_path), "--file", str(path),
        "--model", "test", "--approve-read", "--approve-model",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "reviewed"
    assert report["source_sent_to_model"] is False
    assert configurations[0]["num_gpu"] == 0
    assert configurations[0]["max_predict_tokens"] == 1536
    assert configurations[0]["response_format"]["type"] == "object"
    assert "summary" in configurations[0]["response_format"]["required"]



def test_invalid_coder_reply_is_rejected_with_redacted_parse_reason(
    tmp_path: Path,
) -> None:
    path = _file(tmp_path)

    def brain(_model: str, _task: Task) -> str:
        return "Thoughts about architecture, not JSON."

    result = review_local_code(
        project_root=tmp_path, file_path=path,
        model_id="test", brain=brain,
        approve_read=True, approve_model=True,
    )
    assert result["status"] == "blocked"
    assert result["plan_status"] == "invalid"
    assert result["plan_error_type"] == "structured_code_plan_validation_failed"
    assert len(result["plan_error_hash"]) == 64
    assert result["plan"] is None
    assert result["model_calls"] == 1
    assert "Thoughts about architecture" not in str(result)
