"""Regress Qwen's REAL V28 report: three generic, ungrounded proposals."""
from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_code_evidence_gate_v29 import (
    check_code_review_evidence,
)
from hex_cortex.memory.cortex_code_review_bridge_v26 import review_local_code
from hex_cortex.memory.cortex_code_structural_context_v28 import (
    describe_python_structure,
)
from hex_cortex.memory.cortex_local_harness_v2 import Task


def _code() -> str:
    return (
        "from math import isfinite\n"
        "def _finite_vector(x):\n"
        "    if not isfinite(x):\n"
        "        raise ValueError('invalid')\n"
        "    return x\n"
        "def run_universal_world_advisory(x):\n"
        "    '''A guarded virtual world simulation advisory.'''\n"
        "    return _finite_vector(x)\n"
    )


def _v28_style_plan() -> dict:
    return {
        "candidate_files": ["world.py"],
        "focus_areas": ["consensus_quality", "repository_context", "testing"],
        "proposed_changes": [
            {
                "area": "consensus_quality",
                "file": None,
                "objective": "Ensure _finite_vector handles non-finite values.",
                "change": "Add non-finite check to _finite_vector.",
                "confidence": .8,
            },
            {
                "area": "repository_context",
                "file": None,
                "objective": "Document run_universal_world_advisory.",
                "change": "Add a docstring to run_universal_world_advisory.",
                "confidence": .7,
            },
            {
                "area": "testing",
                "file": None,
                "objective": "More unit tests",
                "change": "Add tests for _finite_vector.",
                "confidence": .9,
            },
        ],
        "summary": "Structural suggestions only.",
        "risks": [], "tests": [], "unknowns": [],
    }


def test_real_model_style_plan_exposes_unverified_and_duplicate_claims() -> None:
    structure = describe_python_structure(_code())
    proposal = check_code_review_evidence(
        _v28_style_plan(),
        selected_file="world.py", structure=structure,
        source_disclosed=False,
    )
    assert proposal["status"] == "insufficient_verified_review_evidence"
    assert proposal["proposal_count"] == 3
    assert proposal["grounded_proposal_count"] == 0
    assert proposal["human_review_candidate_count"] == 0
    assert proposal["has_actionable_evidence"] is False
    assert proposal["independently_verified_code_fix"] is False
    assert "no_proposed_change_references_both_allowed_file_and_known_function" in proposal["warnings"]
    assert "some_proposals_may_duplicate_existing_guards_or_docstrings" in proposal["warnings"]
    assert proposal["proposals"][0]["potentially_redundant_with_ast"] == [
        "_finite_vector:finite_guard_already_present_in_ast"
    ]
    assert proposal["proposals"][1]["potentially_redundant_with_ast"] == [
        "run_universal_world_advisory:docstring_already_present_in_ast"
    ]
    assert "test_coverage_not_verified_from_repository" in proposal["warnings"]


def test_grounded_change_with_source_still_is_not_verified_fix() -> None:
    structure = describe_python_structure(_code())
    suggestion = _v28_style_plan()
    suggestion["proposed_changes"] = [{
        "area": "testing", "file": "world.py",
        "objective": "Add boundary tests for run_universal_world_advisory",
        "change": "Test negative acceleration on run_universal_world_advisory",
        "confidence": .5,
    }]
    receipt = check_code_review_evidence(
        suggestion, selected_file="world.py",
        structure=structure, source_disclosed=True,
    )
    assert receipt["status"] == "source_proposal_needs_review"
    assert receipt["grounded_proposal_count"] == 1
    assert receipt["human_review_candidate_count"] == 1
    assert receipt["has_actionable_evidence"] is False
    assert receipt["proposals"][0]["behavior_proven"] is False


def test_bridge_runs_real_harness_and_flags_gaps_beside_valid_json(tmp_path: Path) -> None:
    path = tmp_path / "world.py"
    path.write_text(_code(), encoding="utf-8")

    def brain(_model: str, _task: Task) -> str:
        return json.dumps(_v28_style_plan())

    report = review_local_code(
        project_root=tmp_path, file_path=path, model_id="stub",
        brain=brain, approve_read=True, approve_model=True,
    )
    assert report["status"] == "reviewed"
    assert report["plan_status"] == "valid"
    assert report["plan_grounding_ratio"] == 1.0
    assert report["review_evidence"]["grounded_proposal_count"] == 0
    assert report["review_evidence"]["independently_verified_code_fix"] is False
    assert report["model_calls"] == 1
    assert report["harness_replay_verified"] is True
    assert report["files_written"] is False
