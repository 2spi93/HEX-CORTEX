"""End-to-end deterministic grading after real three-domain Harness execution."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_science_brain_bridge import run_science_guided_brain


@pytest.mark.parametrize(("domain", "request_text", "answer", "format_marker"), [
    ("mathematics", "127*413", "52451", "rational"),
    ("physics", json.dumps({
        "law": "force", "inputs": {
            "mass": {"value": "2", "unit": "kg"},
            "acceleration": {"value": "3", "unit": "m/s^2"},
        }
    }), "6 N", "SI-unit"),
    ("chemistry", json.dumps({
        "reactants": ["H2", "O2"], "products": ["H2O"]
    }), '{"reactants":[2,1],"products":[2]}', "JSON integer"),
])
def test_strict_science_model_output_grades_true(
    tmp_path: Path, domain: str, request_text: str,
    answer: str, format_marker: str,
) -> None:
    harness = LocalHarness(
        session=Session("science-grade", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )
    prompts: list[str] = []

    def brain(_model: str, task: Task) -> str:
        prompts.append(task.instruction)
        return answer

    result = run_science_guided_brain(
        harness=harness,
        task=Task("science-2026", domain, "Give the scientifically bounded result"),
        scientific_request=request_text,
        domain=domain,
        model_id="stub",
        brain=brain,
        approve_science=True,
        approve_model=True,
        strict_answer=True,
    )
    assert result["status"] == "complete"
    assert result["answer_verification"]["status"] == "matched"
    assert result["model_answer_independently_verified"] is True
    assert format_marker in prompts[0]
    assert harness.verify_replay()
    assert result["real_world_science_certified"] is False


def test_freeform_correct_explanation_is_not_falsely_certified(
    tmp_path: Path,
) -> None:
    harness = LocalHarness(
        session=Session("science-prose", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
    )
    result = run_science_guided_brain(
        harness=harness,
        task=Task("science-prose", "mathematics", "Explain 17*23"),
        scientific_request="17*23", domain="mathematics",
        model_id="mock", brain=lambda _model, _task: "The result is 391.",
        approve_science=True, approve_model=True,
    )
    assert result["status"] == "complete"
    assert result["model_answer_independently_verified"] is False
    assert result["answer_verification"]["status"] == "invalid_answer_format"


def test_exact_but_wrong_answer_is_not_certified(tmp_path: Path) -> None:
    harness = LocalHarness(
        session=Session("science-wrong", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
    )
    result = run_science_guided_brain(
        harness=harness, task=Task("science-wrong", "physics", "Give exact force"),
        scientific_request=json.dumps({
            "law": "force", "inputs": {
                "mass": {"value": "2", "unit": "kg"},
                "acceleration": {"value": "3", "unit": "m/s^2"},
            },
        }),
        domain="physics", model_id="mock",
        brain=lambda _model, _task: "6 J",
        approve_science=True, approve_model=True, strict_answer=True,
    )
    assert result["status"] == "complete"
    assert result["model_answer_independently_verified"] is False
    assert result["answer_verification"]["status"] == "incorrect"
