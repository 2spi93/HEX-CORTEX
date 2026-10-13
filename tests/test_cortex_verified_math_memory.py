"""Math fact provenance -> Replay -> Memory -> retrieval -> Brain, no network."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_verified_math_memory_cli as cli
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.cortex_verified_math_memory import (
    append_verified_math_fact,
    verify_math_fact_task,
)
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _valid_spine() -> CanonicalSpine:
    spine = CanonicalSpine()
    receipt = append_verified_math_fact(
        spine, task_id="math001", expression="127*413", approved=True
    )
    assert receipt["model_called"] is False
    assert verify_math_fact_task(spine, "math001")
    return spine


def test_math_proof_to_actual_replay_and_retrieval() -> None:
    spine = _valid_spine()
    learning = VerifiedLearningLoop(spine=spine)
    result = learning.run(
        task_id="math001",
        query=RetrievalQuery(query="127*413"),
        approve_promotion=True,
    )
    assert result.promotion is not None and result.promotion.status.value == "promoted"
    assert result.replay.status.value == "consolidated"
    assert "52451" in result.context.context_text
    assert len(result.context.results) == 1


def test_math_fact_can_reach_real_harness_as_untrusted_verified_data(
    tmp_path: Path,
) -> None:
    spine = _valid_spine()
    learning = VerifiedLearningLoop(spine=spine)
    learning.run(
        task_id="math001", query=RetrievalQuery(query="127*413"),
        approve_promotion=True,
    )
    harness = LocalHarness(
        session=Session("math-memory", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
        spine=spine,
    )
    instructions: list[str] = []

    def brain(_model: str, task: Task) -> str:
        instructions.append(task.instruction)
        return "52451"

    outcome = run_memory_augmented_task(
        harness=harness, learning=learning,
        task=Task("new_question", "math", "What is 127*413?"),
        models=["test"], brain=brain,
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="127*413"),
    )
    assert outcome["status"] == "complete"
    assert outcome["memory_context"]["retrieved_count"] == 1
    assert "52451" in instructions[0]
    assert harness.verify_replay()


def test_wrong_math_fact_in_valid_hash_chain_is_not_accepted_as_truth(
    tmp_path: Path,
) -> None:
    valid = _valid_spine()
    payload = valid.events[0].payload
    payload["numerator"] = 1
    payload["observations"] = ["Verified exact arithmetic: 127*413 = 1"]
    forged = CanonicalSpine()
    forged.append(
        event_type="math.exact_verified", task_id="math001",
        source="ExactMathCell", payload=payload, confidence=1.0,
    )
    forged.append(
        event_type="clock.completed", task_id="math001",
        source="VerifiedMathMemory", payload={"completed": True}, confidence=1.0,
    )
    assert forged.verify_integrity().ok
    assert not verify_math_fact_task(forged, "math001")
    # A hash chain plus Replay alone is not a scientific evidence checker.
    learning = VerifiedLearningLoop(spine=forged)
    promoted = learning.run(
        task_id="math001", query=RetrievalQuery(query="127*413"),
        approve_promotion=True,
    )
    assert promoted.promotion is not None
    assert promoted.promotion.status.value == "rejected"
    assert promoted.promotion.details["reason"] == "math_fact_source_not_verified"
    assert promoted.promotion.index_entry is None
    assert not learning.index.entries
    calls: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append(True)
        return "1"

    harness = LocalHarness(
        session=Session("math-forgery", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
        spine=forged,
    )
    with pytest.raises(ValueError, match="verified_math_fact_validation_failed"):
        run_memory_augmented_task(
            harness=harness, learning=learning,
            task=Task("new_question", "math", "127*413"),
            models=["test"], brain=brain,
            approve_model=True, approve_memory_use=True,
        )
    assert calls == []


def test_math_fact_requires_approval_and_unique_task() -> None:
    spine = CanonicalSpine()
    with pytest.raises(PermissionError):
        append_verified_math_fact(spine, task_id="math001", expression="17*23")
    assert not spine.events
    append_verified_math_fact(spine, task_id="math001", expression="17*23", approved=True)
    with pytest.raises(ValueError, match="already_exists"):
        append_verified_math_fact(spine, task_id="math001", expression="17*23", approved=True)


@pytest.mark.parametrize("expression", ["1/0", "oops", "1.5", "10**99999"])
def test_invalid_fact_does_not_write_to_spine(expression: str) -> None:
    spine = CanonicalSpine()
    with pytest.raises(ValueError, match="expression_rejected"):
        append_verified_math_fact(
            spine, task_id="math001", expression=expression, approved=True
        )
    assert spine.events == []


def test_persistence_checkpoint_restore_and_scientific_reverification(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path),
        "--task-id", "math001", "--expression", "127*413",
        "--approve-record", "--approve-promote", "--approve-persist",
        "--spine-output", "math-spine.jsonl",
        "--checkpoint-output", "math-checkpoint.jsonl",
    ]
    assert cli.main(args) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["promotion_status"] == "promoted"
    assert report["retrieval_count"] == 1
    assert report["saved"] is True
    spine = CanonicalSpineJsonlStore(tmp_path / "math-spine.jsonl").load()
    assert verify_math_fact_task(spine, "math001")
    loaded = VerifiedLearningLoop.restore_checkpoint(
        project_root=tmp_path,
        relative_path=Path("math-checkpoint.jsonl"),
        spine=spine,
    )
    assert len(loaded.index.entries) == 1


def test_cli_dry_run_and_refuse_unsafe_persistence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    args = [
        "--project-root", str(tmp_path),
        "--task-id", "math001", "--expression", "127*413",
    ]
    assert cli.main([*args, "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert not report["will_write_files"]
    with pytest.raises(SystemExit):
        cli.main([*args, "--approve-record", "--spine-output", "events.jsonl"])
    assert not (tmp_path / "events.jsonl").exists()
