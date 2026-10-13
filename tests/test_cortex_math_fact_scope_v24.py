"""V24 negative transfer guard: old correct answers cannot answer new arithmetic."""
from __future__ import annotations

from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_math_fact_scope_v24 import math_fact_applicability
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.cortex_verified_math_memory import append_verified_math_fact
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine


def _context(tmp_path: Path) -> tuple[VerifiedLearningLoop, LocalHarness]:
    spine = CanonicalSpine()
    append_verified_math_fact(
        spine, task_id="training", expression="127*413", approved=True
    )
    loop = VerifiedLearningLoop(spine=spine)
    r = loop.run(
        task_id="training", query=RetrievalQuery(query="127*413"),
        approve_promotion=True,
    )
    assert r.promotion is not None and r.promotion.status.value == "promoted"
    h = LocalHarness(
        session=Session("scope-test", tmp_path), spine=spine,
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )
    return loop, h


def test_prior_scalar_different_task_is_ineligible(tmp_path: Path) -> None:
    loop, harness = _context(tmp_path)
    scope = math_fact_applicability(
        loop.spine, source_task_id="training", target_expression="127*419"
    )
    assert scope["eligible"] is False
    assert scope["reason"] == "different_arithmetic_expression"
    inputs: list[str] = []

    def brain(_model: str, task: Task) -> str:
        inputs.append(task.instruction)
        return "53213"

    result = run_memory_augmented_task(
        harness=harness, learning=loop, 
        task=Task("evaluation", "math", "Compute 127*419"),
        models=["test"], brain=brain,
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="127*413"),
        target_math_expression="127*419",
    )
    assert result["status"] == "complete"
    assert result["memory_context"]["enabled"] is True
    assert result["memory_context"]["retrieved_count"] == 0
    assert result["memory_context"]["math_fact_scope"] == "identical_expression_only"
    assert inputs == ["Compute 127*419"]
    assert harness.verify_replay()


def test_missing_explicit_expression_blocks_old_scalar_injection(
    tmp_path: Path,
) -> None:
    loop, harness = _context(tmp_path)
    seen: list[str] = []

    def brain(_model: str, task: Task) -> str:
        seen.append(task.instruction)
        return "53213"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("evaluation", "math", "What is 127*419?"),
        models=["test"], brain=brain,
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="127*413"),
    )
    assert result["status"] == "complete"
    assert result["memory_context"]["retrieved_count"] == 0
    assert result["memory_context"]["target_math_expression_explicit"] is False
    assert "52451" not in seen[0]


def test_exact_expression_with_different_spacing_is_eligible(
    tmp_path: Path,
) -> None:
    loop, harness = _context(tmp_path)
    scope = math_fact_applicability(
        loop.spine, source_task_id="training", target_expression="( 127 * 413 )"
    )
    assert scope["eligible"] is True
    seen: list[str] = []

    def brain(_model: str, task: Task) -> str:
        seen.append(task.instruction)
        return "52451"

    result = run_memory_augmented_task(
        harness=harness, learning=loop,
        task=Task("evaluation", "math", "Compute 127 * 413"),
        models=["test"], brain=brain,
        approve_model=True, approve_memory_use=True,
        query=RetrievalQuery(query="127*413"),
        target_math_expression="( 127 * 413 )",
    )
    assert result["status"] == "complete"
    assert result["memory_context"]["retrieved_count"] == 1
    assert "52451" in seen[0]
    assert "UNTRUSTED" in seen[0]


@pytest.mark.parametrize("target", [
    None, "", "127*419", "127 * 413 + 0",
    "127*413 or 1", "__import__('os')", "127*413 # injection",
])
def test_math_scope_fails_closed_on_non_matching_or_unparseable_target(
    tmp_path: Path, target: str | None,
) -> None:
    loop, _ = _context(tmp_path)
    outcome = math_fact_applicability(
        loop.spine, source_task_id="training", target_expression=target
    )
    assert outcome["eligible"] is False
    assert outcome["reason"] in {
        "different_arithmetic_expression",
        "target_expression_unavailable",
        "target_expression_unverifiable",
    }


def test_forged_but_rehashed_proof_is_not_applicable(tmp_path: Path) -> None:
    original, _ = _context(tmp_path)
    p = dict(original.spine.events_for_task("training")[0].payload)
    p["numerator"] = 100
    altered = CanonicalSpine()
    altered.append(
        event_type="math.exact_verified", task_id="training",
        source="ExactMathCell", payload=p, confidence=1.0,
    )
    altered.append(
        event_type="clock.completed", task_id="training",
        source="VerifiedMathMemory", payload={"completed": True}, confidence=1.0,
    )
    assert altered.verify_integrity().ok
    with pytest.raises(ValueError, match="math_fact_applicability_provenance_invalid"):
        math_fact_applicability(
            altered, source_task_id="training", target_expression="127*413"
        )
