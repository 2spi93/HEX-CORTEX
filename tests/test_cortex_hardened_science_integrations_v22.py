"""Fail-closed source math proofs and opt-in strict model response grading."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_science_brain_cli as cli
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.cortex_verified_math_memory import append_verified_math_fact
from hex_cortex.memory.memory_promotion import MemoryPromoter
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.spine.canonical_spine import CanonicalSpine


def test_forced_forged_manifest_never_reaches_brain(tmp_path: Path) -> None:
    genuine = CanonicalSpine()
    append_verified_math_fact(
        genuine, task_id="math-fact", expression="127*413", approved=True
    )
    payload = dict(genuine.events_for_task("math-fact")[0].payload)
    payload["numerator"] = 1
    payload["observations"] = ["Verified exact arithmetic: 127*413 = 1"]
    forged = CanonicalSpine()
    forged.append(
        event_type="math.exact_verified", task_id="math-fact",
        source="ExactMathCell", payload=payload, confidence=1.0,
    )
    forged.append(
        event_type="clock.completed", task_id="math-fact",
        source="VerifiedMathMemory", payload={"completed": True}, confidence=1.0,
    )
    assert forged.verify_integrity().ok
    replay = ReplayEngine(spine=forged).replay_task("math-fact")
    assert replay.memory is not None
    loop = VerifiedLearningLoop(spine=forged)
    loop._records["math-fact"] = {
        "task_id": "math-fact",
        "source_event_ids": list(replay.source_event_ids),
        "promotion_hash": MemoryPromoter(
            index=loop.index, spine=forged
        ).compute_promotion_hash(replay.memory),
    }
    calls: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        calls.append(True)
        return "1"

    harness = LocalHarness(
        session=Session("forced-manifest", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1), spine=forged,
    )
    with pytest.raises(ValueError, match="verified_math_fact_validation_failed"):
        run_memory_augmented_task(
            harness=harness, learning=loop,
            task=Task("fresh-question", "math", "What is 127*413?"),
            models=["mock"], brain=brain,
            approve_model=True, approve_memory_use=True,
        )
    assert calls == []
    assert harness._model_calls == 0


def test_cli_strict_science_answer_is_graded(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls: list[str] = []

    class StubBrain:
        def __init__(self, **kwargs: object) -> None:
            assert kwargs["num_gpu"] == 0

        def __call__(self, _model: str, task: Task) -> str:
            calls.append(task.instruction)
            return "6 N"

    monkeypatch.setattr(cli, "LocalOllamaBrain", StubBrain)
    rc = cli.main([
        "--project-root", str(tmp_path),
        "--domain", "physics", "--example", "--model", "local-test",
        "--approve-science", "--approve-model", "--strict-answer",
    ])
    assert rc == 0
    result = json.loads(capsys.readouterr().out)
    assert result["status"] == "complete"
    assert result["answer_verification"]["status"] == "matched"
    assert result["model_answer_independently_verified"] is True
    assert result["answer"] is None
    assert "SI-unit" in calls[0]
