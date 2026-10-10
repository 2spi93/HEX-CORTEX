"""End-to-end model-free HEX-CORTEX cognitive circuit regression tests."""

from __future__ import annotations

import json

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task


def _setup() -> CognitiveCircuit:
    cells = CellRegistry([
        CellSpec(cell_id="logic", role=CellRole.LOGIC, domains=["coding"]),
        CellSpec(cell_id="evidence", role=CellRole.EVIDENCE, domains=["coding"]),
        CellSpec(cell_id="critic", role=CellRole.CRITIC, domains=["coding"]),
    ])
    return CognitiveCircuit(registry=cells)


def _good(cell_id: str, task: Task) -> CellResult:
    return CellResult(
        cell_id=cell_id, task_id=task.task_id,
        confidence=0.8, uncertainty=0.2,
        evidence_refs=["test:unit-verified"],
        payload={"answer": "unpersisted user private source"},
    )


def test_original_pillars_form_verified_model_free_circuit() -> None:
    circuit = _setup()
    task = Task(
        task_id="first", content="private input: should never persist",
        domain_hints=["coding"], novelty=0.8, risk=0.8, uncertainty=0.8,
        latency_budget_ms=2000,
    )
    result = circuit.run(task, cell_handler=_good,
                         verify_evidence=lambda x: "test:unit-verified" in x.evidence_refs,
                         approved=True)
    assert result["status"] == "verified"
    assert result["mode"] == "deep"
    assert len(result["selected_cells"]) == 3
    assert result["verified_cell_count"] == 3
    assert result["spine_verified"] is True
    assert result["model_used"] is False
    assert result["model_benchmark_required"] is False
    assert result["automatic_skill_promotion"] is False
    assert result["checkout_modified"] is False
    assert "unpersisted user private source" not in str(circuit.spine.events)
    assert "private input" not in str(circuit.spine.events)
    assert circuit.spine.verify_integrity().ok
    assert circuit.spine.project().event_type_counts["clock.started"] == 1


def test_without_operator_approval_no_cell_called_no_clock_events() -> None:
    circuit = _setup()
    calls = []
    result = circuit.run(
        Task(task_id="a", content="Test"),
        cell_handler=lambda cell, task: calls.append(cell),
        verify_evidence=lambda _: True,
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "operator_approval_required"
    assert calls == []
    assert circuit.spine.events == []


def test_missing_independent_verifier_denies_without_execution() -> None:
    circuit = _setup()
    calls = []
    result = circuit.run(
        Task(task_id="a", content="Test"), approved=True,
        cell_handler=lambda cell, task: calls.append(cell),
    )
    assert result["reason"] == "independent_verifier_required"
    assert calls == []


def test_invalid_result_fails_closed_and_is_sanitized() -> None:
    circuit = _setup()
    task = Task(task_id="bad", content="sensitive content",
                domain_hints=["coding"], novelty=0.1, risk=0.1, uncertainty=0.1)
    result = circuit.run(
        task, cell_handler=lambda _, t: CellResult(
            cell_id="wrong-id", task_id=t.task_id, confidence=1,
            uncertainty=0, evidence_refs=["false:evidence"],
        ),
        verify_evidence=lambda _: True, approved=True,
    )
    assert result["status"] == "blocked"
    assert result["outcomes"][0]["status"] == "rejected"
    assert result["outcomes"][0]["reason"] == "verification_failed"
    assert "sensitive content" not in str(circuit.spine.events)
    assert circuit.spine.verify_integrity().ok


def test_untrusted_exception_never_leaks_into_receipts() -> None:
    circuit = _setup()
    secret = "secret_cloud_api_key_12345"

    def bad(cell, task):
        raise RuntimeError("sensitive error " + secret)

    result = circuit.run(
        Task(task_id="confidential", content="test", domain_hints=["coding"]),
        cell_handler=bad, verify_evidence=lambda _: True, approved=True,
    )
    assert result["status"] == "blocked"
    assert secret not in json.dumps(result)
    assert secret not in str(circuit.spine.events)
    assert circuit.spine.verify_integrity().ok


def test_duplicate_task_ids_deny_second_run() -> None:
    circuit = _setup()
    task = Task(task_id="duplicate", content="Inspect", domain_hints=["coding"])
    first = circuit.run(task, cell_handler=_good, verify_evidence=lambda _: True,
                        approved=True)
    assert first["status"] == "verified"
    count = len(circuit.spine.events)
    second = circuit.run(task, cell_handler=_good, verify_evidence=lambda _: True,
                         approved=True)
    assert second["reason"] == "duplicate_task_id"
    assert len(circuit.spine.events) == count


def test_quarantined_cell_does_not_get_routed() -> None:
    circuit = _setup()
    for _ in range(3):
        circuit.registry.record_failure("logic", "repeated_failure")
    task = Task(task_id="quarantine", content="Inspect",
                domain_hints=["coding"], novelty=0.1, risk=0.1, uncertainty=0.1)
    result = circuit.run(task, cell_handler=_good,
                         verify_evidence=lambda _: True, approved=True)
    assert result["status"] == "verified"
    assert "logic" not in result["selected_cells"]
    assert len(result["selected_cells"]) <= 2


def test_wrong_domain_no_network_or_llm_needed() -> None:
    circuit = _setup()
    task = Task(task_id="generic", content="Read only", domain_hints=["unknown"])
    result = circuit.run(task, cell_handler=_good,
                         verify_evidence=lambda _: True, approved=True)
    assert result["status"] == "verified"
    assert result["model_used"] is False

def test_degraded_cell_requires_separate_secondary_verification() -> None:
    circuit = _setup()
    circuit.registry.record_failure("logic", "prior_failure")
    circuit.registry.record_failure("logic", "prior_failure")
    task = Task(task_id="degraded", content="Review", domain_hints=["coding"],
                novelty=0.9, risk=0.9, uncertainty=0.9)
    def primary(_):
        return True
    rejected = circuit.run(
        task, cell_handler=_good, verify_evidence=primary, approved=True,
    )
    assert rejected["status"] == "blocked"
    assert any(row["reason"] == "verification_failed" for row in rejected["outcomes"] if row["status"] == "rejected")
    # Because the degraded cell had another rejection, it may now be quarantined.
    # Use another fresh registry to exercise the permitted double-check path.
    circuit = _setup()
    circuit.registry.record_failure("logic", "prior_failure")
    circuit.registry.record_failure("logic", "prior_failure")
    verified = circuit.run(
        Task(task_id="degraded-verified", content="Review", domain_hints=["coding"],
             novelty=0.9, risk=0.9, uncertainty=0.9),
        cell_handler=_good, verify_evidence=primary,
        secondary_verifier=lambda _: True, approved=True,
    )
    assert verified["status"] == "verified"
    assert verified["verified_cell_count"] == 3


def test_secondary_verifier_cannot_be_same_callback() -> None:
    circuit = _setup()
    circuit.registry.record_failure("logic", "bad")
    circuit.registry.record_failure("logic", "bad")
    def verifier(_):
        return True
    report = circuit.run(
        Task(task_id="same-callback", content="Review", domain_hints=["coding"],
             novelty=0.9, risk=0.9, uncertainty=0.9),
        cell_handler=_good,
        verify_evidence=verifier, secondary_verifier=verifier,
        approved=True,
    )
    assert report["status"] == "blocked"

