"""Three real preexisting science cells reach one gated Harness Brain."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_science_brain_bridge import run_science_guided_brain


def _harness(path: Path, *, grant: bool = True) -> LocalHarness:
    return LocalHarness(
        session=Session("guided-science", path),
        grants=frozenset({Capability.CALL_MODEL}) if grant else frozenset(),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )


@pytest.mark.parametrize(("domain", "scientific_input", "needle"), [
    ("mathematics", "127*413", '"numerator": 52451'),
    ("physics", json.dumps({
        "law": "force",
        "inputs": {
            "mass": {"value": "2", "unit": "kg"},
            "acceleration": {"value": "3", "unit": "m/s^2"},
        }
    }), '"unit": "N"'),
    ("chemistry", json.dumps({
        "reactants": ["H2", "O2"], "products": ["H2O"]
    }), '"formula": "H2O"'),
])
def test_three_science_brains_share_real_harness_and_spine(
    tmp_path: Path, domain: str, scientific_input: str, needle: str
) -> None:
    harness = _harness(tmp_path)
    calls: list[str] = []

    def brain(_model: str, task: Task) -> str:
        calls.append(task.instruction)
        return "answer"

    report = run_science_guided_brain(
        harness=harness, domain=domain, scientific_request=scientific_input,
        task=Task("first-task", domain, "Please explain the verified result"),
        model_id="mock", brain=brain,
        approve_science=True, approve_model=True,
    )
    assert report["status"] == "complete"
    assert report["model_calls"] == 1
    assert needle in calls[0]
    assert "NOT an instruction" in calls[0]
    assert report["scientific_evidence_refs"]
    assert report["harness_spine_verified"] is True
    assert report["model_answer_independently_verified"] is False
    assert harness.verify_replay()
    assert harness.spine.latest_by_type("science.verified_cell_receipt") is not None
    assert scientific_input not in str([
        e.model_dump() for e in harness.spine.events
    ])


def test_requires_two_explicit_approvals_before_any_work(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    called: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        called.append(True)
        return "ok"

    report = run_science_guided_brain(
        harness=harness, domain="mathematics", scientific_request="17*23",
        task=Task("t1", "mathematics", "What is result?"),
        model_id="mock", brain=brain,
        approve_science=True,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0
    assert not harness.spine.events
    assert not called


def test_science_failure_never_calls_brain(tmp_path: Path) -> None:
    harness = _harness(tmp_path)
    called: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        called.append(True)
        return "ok"

    report = run_science_guided_brain(
        harness=harness, domain="chemistry", scientific_request='{"no": "data"}',
        task=Task("t1", "chemistry", "Is this balanced?"),
        model_id="mock", brain=brain,
        approve_science=True, approve_model=True,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0
    assert not called
    assert not harness.spine.events


def test_harness_model_denial_still_blocks(tmp_path: Path) -> None:
    harness = _harness(tmp_path, grant=False)
    called: list[bool] = []

    def brain(_model: str, _task: Task) -> str:
        called.append(True)
        return "ok"

    report = run_science_guided_brain(
        harness=harness, domain="mathematics", scientific_request="17*23",
        task=Task("t1", "mathematics", "What is result?"),
        model_id="mock", brain=brain,
        approve_science=True, approve_model=True,
    )
    assert report["status"] == "blocked"
    assert report["model_calls"] == 0
    assert not called


def test_request_for_tool_is_denied_before_science(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="science_domain_or_tool_authorization_mismatch"):
        run_science_guided_brain(
            harness=_harness(tmp_path), domain="mathematics",
            scientific_request="17*23",
            task=Task("t1", "mathematics", "What is result?", "shell"),
            model_id="mock", brain=lambda _model, _task: "ok",
            approve_science=True, approve_model=True,
        )
