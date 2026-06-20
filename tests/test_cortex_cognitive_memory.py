import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_cognitive_memory import append_causal_intervention
from hex_cortex.memory.cortex_cognitive_memory import append_competency_baseline
from hex_cortex.memory.cortex_cognitive_memory import append_skill_graph_node
from hex_cortex.memory.cortex_cognitive_memory import project_adapter_registry
from hex_cortex.memory.cortex_cognitive_memory import project_skill_graph
from hex_cortex.memory.cortex_cognitive_memory import register_adapter_candidate
from hex_cortex.memory.cortex_cognitive_memory import transition_adapter_status


def test_competency_baseline_hashes_model_and_suite_refs(tmp_path: Path) -> None:
    ledger = tmp_path / "baselines.jsonl"
    payload = append_competency_baseline(
        ledger,
        model_id="private-model-id",
        suite_ref="private-suite-reference",
        metrics={"architecture": 1.0, "coding": 0.8},
        critical_competencies=["architecture"],
    )

    text = ledger.read_text(encoding="utf-8")
    assert payload["record_type"] == "competency_baseline_v1"
    assert payload["critical_competencies"] == ["architecture"]
    assert "private-model-id" not in text
    assert "private-suite-reference" not in text
    assert payload["raw_model_identifier_persisted"] is False


def test_causal_intervention_records_verified_improvement_without_raw_refs(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "interventions.jsonl"
    payload = append_causal_intervention(
        ledger,
        residual_signature="a" * 64,
        intervention_id="enable-deterministic-verifier",
        control_ref="raw-control-ref",
        treatment_ref="raw-treatment-ref",
        verifier_ref="raw-verifier-ref",
        outcome_delta=0.25,
        verified=True,
    )

    text = ledger.read_text(encoding="utf-8")
    assert payload["causal_improvement_observed"] is True
    assert "raw-control-ref" not in text
    assert "raw-treatment-ref" not in text
    assert "raw-verifier-ref" not in text


def test_skill_graph_requires_existing_dependencies(tmp_path: Path) -> None:
    ledger = tmp_path / "skills.jsonl"
    append_skill_graph_node(
        ledger,
        skill_id="base-skill",
        domain="hex-cortex",
        source_residual_signature="b" * 64,
        dependencies=[],
        verification_ref="verification-base",
        status="active",
    )
    child = append_skill_graph_node(
        ledger,
        skill_id="child-skill",
        domain="hex-cortex",
        source_residual_signature="c" * 64,
        dependencies=["base-skill"],
        verification_ref="verification-child",
    )

    graph = project_skill_graph(ledger)
    assert child["dependencies"] == ["base-skill"]
    assert graph["graph_valid"] is True
    assert graph["node_count"] == 2
    assert graph["active_skills"] == ["base-skill"]

    with pytest.raises(ValueError, match="skill dependency missing"):
        append_skill_graph_node(
            ledger,
            skill_id="invalid-skill",
            domain="hex-cortex",
            source_residual_signature="d" * 64,
            dependencies=["unknown-skill"],
            verification_ref="verification-invalid",
        )


def test_skill_graph_projection_detects_cycles(tmp_path: Path) -> None:
    ledger = tmp_path / "skills.jsonl"
    rows = [
        {
            "record_type": "cognitive_skill_graph_node_v1",
            "skill_id": "skill-a",
            "dependencies": ["skill-b"],
            "status": "candidate",
        },
        {
            "record_type": "cognitive_skill_graph_node_v1",
            "skill_id": "skill-b",
            "dependencies": ["skill-a"],
            "status": "candidate",
        },
    ]
    ledger.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )

    graph = project_skill_graph(ledger)
    assert graph["graph_valid"] is False
    assert graph["cycles"]


def test_adapter_registry_requires_evaluated_operator_approved_lifecycle(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "adapters.jsonl"
    registered = register_adapter_candidate(
        ledger,
        adapter_id="adapter-debug-v1",
        base_model_id="private-base-model",
        skill_id="debug-skill",
        plan_hash="e" * 64,
        checkpoint_hash="f" * 64,
        reversible=True,
    )
    assert registered["status"] == "candidate"
    assert registered["base_model_immutable"] is True
    assert "private-base-model" not in ledger.read_text(encoding="utf-8")

    with pytest.raises(ValueError, match="adapter status transition invalid"):
        transition_adapter_status(
            ledger,
            adapter_id="adapter-debug-v1",
            new_status="promoted",
            evaluation_hash="1" * 64,
            operator_approved=True,
        )

    evaluated = transition_adapter_status(
        ledger,
        adapter_id="adapter-debug-v1",
        new_status="evaluated",
        evaluation_hash="2" * 64,
        operator_approved=False,
    )
    assert evaluated["status"] == "evaluated"

    with pytest.raises(ValueError, match="operator approval required"):
        transition_adapter_status(
            ledger,
            adapter_id="adapter-debug-v1",
            new_status="promoted",
            evaluation_hash="3" * 64,
            operator_approved=False,
        )

    promoted = transition_adapter_status(
        ledger,
        adapter_id="adapter-debug-v1",
        new_status="promoted",
        evaluation_hash="3" * 64,
        operator_approved=True,
    )
    assert promoted["status"] == "promoted"

    revoked = transition_adapter_status(
        ledger,
        adapter_id="adapter-debug-v1",
        new_status="revoked",
        evaluation_hash="4" * 64,
        operator_approved=True,
    )
    assert revoked["status"] == "revoked"

    registry = project_adapter_registry(ledger)
    assert registry["base_model_immutable"] is True
    assert registry["revoked_adapter_ids"] == ["adapter-debug-v1"]
    assert registry["promoted_adapter_ids"] == []
