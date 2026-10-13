"""Coding V28: schema valid is not substantive review, AST informs model."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_code_review_bridge_v26 import review_local_code
from hex_cortex.memory.cortex_code_structural_context_v28 import (
    assess_review_substance, describe_python_structure,
)
from hex_cortex.memory.cortex_local_harness_v2 import Task


def test_static_context_has_named_functions_but_no_source_statements() -> None:
    report = describe_python_structure(
        "import os\ndef movement(x):\n    if x > 0:\n"
        "        return abs(x)\n    return 0\n"
    )
    assert report["functions"][0]["name"] == "movement"
    assert report["functions"][0]["branches"] == 1
    assert report["functions"][0]["calls"] == ["abs"]
    assert report["source_semantics_verified"] is False
    assert "return abs(x)" not in str(report)


def test_exact_model_echo_is_not_accepted_as_substantive_review(tmp_path: Path) -> None:
    selected = tmp_path / "module.py"
    selected.write_text("def movement(x):\n    return x\n", encoding="utf-8")
    template = {
        "summary": "Review based only on available structural evidence",
        "focus_areas": ["testing"],
        "candidate_files": ["module.py"],
        "proposed_changes": [],
        "tests": ["python -m pytest -q"],
        "risks": ["Source logic was not read"],
        "unknowns": ["Implementation details not available"],
    }
    prompts: list[str] = []

    def brain(_model: str, task: Task) -> str:
        prompts.append(task.instruction)
        return json.dumps(template)

    result = review_local_code(
        project_root=tmp_path, file_path=selected,
        model_id="test", brain=brain,
        approve_model=True, approve_read=True,
    )
    assert result["plan_status"] == "valid"
    assert result["status"] == "blocked"
    assert result["review_quality"]["status"] == "prompt_template_echo"
    assert result["review_quality"]["actionable"] is False
    assert result["harness_replay_verified"]
    assert result["structural_context_provided"] is True
    assert result["structural_context"]["functions"][0]["name"] == "movement"
    assert "movement" in prompts[0]
    assert "return x" not in prompts[0]
    assert result["model_calls"] == 1
    assert result["files_written"] is False


def test_specific_structural_suggestion_remains_unverified_without_source(
    tmp_path: Path,
) -> None:
    path = tmp_path / "source.py"
    path.write_text("def tick(x):\n    return x + 1\n", encoding="utf-8")
    plan = {
        "summary": "The function tick has a branch-free static shape.",
        "focus_areas": ["testing"],
        "candidate_files": ["source.py"],
        "proposed_changes": [{
            "area": "testing", "file": "source.py",
            "objective": "Test tick behavior",
            "change": "Add inputs and boundary tests for tick",
            "confidence": 0.5,
        }],
        "tests": ["python -m pytest -q"], "risks": [],
        "unknowns": ["Body not disclosed"],
    }
    def brain(_model: str, _task: Task) -> str:
        return json.dumps(plan)

    report = review_local_code(
        project_root=tmp_path, file_path=path, model_id="test",
        brain=brain, approve_read=True, approve_model=True,
    )
    assert report["status"] == "reviewed"
    assert report["review_quality"]["status"] == "structural_suggestions_only"
    assert report["review_quality"]["actionable"] is False
    assert report["source_sent_to_model"] is False


def test_substance_gate_flags_no_changes_and_does_not_certify_real_code() -> None:
    assert assess_review_substance({
        "summary": "No details", "proposed_changes": [],
    }, source_disclosed=True)["status"] == "no_specific_change_proposed"
    assert assess_review_substance({
        "summary": "Change potential", "proposed_changes": [{"file": "a.py"}],
    }, source_disclosed=True)["status"] == "source_informed_proposal_unverified"


@pytest.mark.parametrize("text", ["def broken(", " " * 129000])
def test_static_context_refuses_invalid_or_oversized_code(text: str) -> None:
    with pytest.raises((ValueError, SyntaxError)):
        describe_python_structure(text)
