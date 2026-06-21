import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_competence_rule_candidate import build_competence_rule_candidate


def _cluster(**over: object) -> dict[str, object]:
    base = {
        "residual_signature": "sig123",
        "failure_class": "arithmetic_set_reasoning",
        "domain": "arithmetic_reasoning",
        "occurrence_count": 5,
        "distinct_context_count": 3,
        "distinct_model_count": 2,
        "verified_correction_count": 5,
        "causal_intervention_count": 2,
        "dominant_corrective_intervention": "generate_and_execute_python_then_cross_check",
        "skill_consolidation_ready": True,
    }
    base.update(over)
    return base


def test_ready_cluster_yields_proposed_candidate() -> None:
    receipt = build_competence_rule_candidate(_cluster())
    assert receipt["status"] == "candidate_proposed"
    assert receipt["prescribed_intervention"] == "generate_and_execute_python_then_cross_check"
    assert receipt["trigger"]["domain"] == "arithmetic_reasoning"
    assert receipt["requires_operator_approval"] is True
    assert receipt["installed"] is False
    assert receipt["next_action"] == "operator_review_competence_rule"


def test_not_ready_cluster_is_insufficient_evidence() -> None:
    receipt = build_competence_rule_candidate(_cluster(skill_consolidation_ready=False))
    assert receipt["status"] == "insufficient_evidence"
    assert receipt["prescribed_intervention"] is None
    assert "cluster_not_consolidation_ready" in receipt["blockers"]
    assert receipt["installed"] is False


def test_missing_intervention_blocks_proposal() -> None:
    receipt = build_competence_rule_candidate(_cluster(dominant_corrective_intervention=None))
    assert receipt["status"] == "insufficient_evidence"
    assert "no_dominant_corrective_intervention" in receipt["blockers"]


def test_candidate_receipt_written_without_raw_reasoning(tmp_path: Path) -> None:
    receipt_path = tmp_path / "candidates.jsonl"
    build_competence_rule_candidate(_cluster(), receipt_path=receipt_path)
    row = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert row["record_type"] == "cortex_competence_rule_candidate_v1"
    assert row["raw_reasoning_persisted"] is False
    assert row["autonomy_ladder_step"] == 5
    assert len(row["candidate_hash"]) == 64


def test_missing_required_field_rejected() -> None:
    bad = _cluster()
    del bad["failure_class"]
    with pytest.raises(ValueError):
        build_competence_rule_candidate(bad)
