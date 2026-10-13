"""CPU-only CLI tests with injected fake Brain, zero network requests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_memory_augmented_cli as cli
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _spine(tmp_path: Path) -> CanonicalSpine:
    spine = CanonicalSpine()
    spine.append(
        event_type="task.received", task_id="source", source="test",
        payload={"goal": "Fibonacci recurrence verified data"}, confidence=0.95,
    )
    spine.append(
        event_type="clock.completed", task_id="source", source="test",
        payload={"completed": True}, confidence=0.95,
    )
    CanonicalSpineJsonlStore(tmp_path / "spine.jsonl").save(spine)
    return spine


def _options(tmp_path: Path) -> list[str]:
    return [
        "--project-root", str(tmp_path), "--spine-file", "spine.jsonl",
        "--task-id", "unseen", "--instruction", "Fibonacci recurrence",
        "--model", "test-model",
    ]


def test_dry_run_reads_no_files(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main([*_options(tmp_path), "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["will_call_model"] is False
    assert report["will_read_spine"] is False
    assert report["num_gpu"] == 0


def test_unapproved_does_not_call_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _spine(tmp_path)
    calls: list[str] = []

    class StubBrain:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __call__(self, _model: str, _task: object) -> str:
            calls.append("called")
            return "answer"

    monkeypatch.setattr(cli, "LocalOllamaBrain", StubBrain)
    assert cli.main(_options(tmp_path)) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert calls == []


def test_operator_approved_memory_reaches_local_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    spine = _spine(tmp_path)
    loop = VerifiedLearningLoop(spine=spine)
    approved = loop.run(
        task_id="source", query=RetrievalQuery(query="Fibonacci"),
        approve_promotion=True,
    )
    assert approved.promotion and approved.promotion.status.value == "promoted"
    loop.save_checkpoint(
        project_root=tmp_path, relative_path=Path("checkpoint.jsonl"), approved=True
    )
    calls: list[str] = []
    seen_options: list[dict[str, object]] = []

    class StubBrain:
        def __init__(self, **options: object) -> None:
            seen_options.append(options)

        def __call__(self, _model: str, task: object) -> str:
            calls.append(task.instruction)
            return "42"

    monkeypatch.setattr(cli, "LocalOllamaBrain", StubBrain)
    assert cli.main([
        *_options(tmp_path), "--checkpoint", "checkpoint.jsonl",
        "--approve-model", "--approve-memory-use",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["answer"] is None
    assert report["memory_context"]["retrieved_count"] == 1
    assert report["cpu_only"] is True
    assert report["files_saved"] is False
    assert seen_options[0]["num_gpu"] == 0
    assert "UNTRUSTED retrieved memory data" in calls[0]


def test_plain_approved_still_works_with_no_checkpoint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _spine(tmp_path)
    seen: list[str] = []

    class StubBrain:
        def __init__(self, **_kwargs: object) -> None:
            pass

        def __call__(self, _model: str, task: object) -> str:
            seen.append(task.instruction)
            return "answer"

    monkeypatch.setattr(cli, "LocalOllamaBrain", StubBrain)
    assert cli.main([*_options(tmp_path), "--approve-model"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "complete"
    assert report["memory_context"]["retrieved_count"] == 0
    assert seen == ["Fibonacci recurrence"]


def test_memory_use_needs_checkpoint_and_explicit_model_approval(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit):
        cli.main([*_options(tmp_path), "--approve-memory-use"])
    with pytest.raises(SystemExit):
        cli.main([*_options(tmp_path), "--approve-model", "--approve-memory-use"])
