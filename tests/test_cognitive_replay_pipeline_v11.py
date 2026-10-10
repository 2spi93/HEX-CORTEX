"""End-to-end deterministic cells → spine → replay → memory, with fail-closed gates."""
from __future__ import annotations

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cognitive_replay_pipeline_v11 import run_circuit_replay_memory
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task


def _fixture():
    registry = CellRegistry([
        CellSpec(cell_id="logic", role=CellRole.LOGIC, domains=["coding"]),
        CellSpec(cell_id="critic", role=CellRole.CRITIC, domains=["coding"]),
    ])
    circuit = CognitiveCircuit(registry=registry)
    task = Task(
        task_id="replay-t01", content="private fix details must not appear in receipt",
        domain_hints=["coding"], novelty=0.1, risk=0.1, uncertainty=0.1,
        latency_budget_ms=1000,
    )
    return circuit, task


def _candidate(cell_id: str, task: Task) -> CellResult:
    return CellResult(
        cell_id=cell_id, task_id=task.task_id,
        confidence=0.9, uncertainty=0.1,
        evidence_refs=["fixture:isolated-independent-test"],
        payload={"secret_input": "private fix details must not appear in receipt"},
    )


def test_full_offline_circuit_produces_hash_only_memory_proposal() -> None:
    circuit, task = _fixture()
    report = run_circuit_replay_memory(
        circuit, task,
        cell_handler=_candidate,
        verify_evidence=lambda value: value.evidence_refs == [
            "fixture:isolated-independent-test"
        ],
        approved=True,
    )
    assert report.status == "memory_proposed_not_promoted"
    assert report.circuit_completed is True
    assert report.spine_verified is True
    assert report.replay_event_count > 0
    assert len(report.memory_proposal_sha256) == 64
    assert len(report.lineage_sha256) == 64
    assert report.skill_activated is False
    assert report.skill_promoted is False
    assert report.memory_persisted is False
    assert report.checkout_modified is False
    assert report.cloud_provider_called is False
    assert report.real_independent_outcome_certified is False
    assert report.retrieval_cycle_integrated is False
    assert "private fix details" not in str(report)
    assert "private fix details" not in str(circuit.spine.events)


def test_unapproved_path_produces_no_event_memory_or_cell_call() -> None:
    circuit, task = _fixture()
    calls = []
    def should_not_run(cell_id, task):
        calls.append(cell_id)
        return _candidate(cell_id, task)
    report = run_circuit_replay_memory(
        circuit, task, cell_handler=should_not_run,
        verify_evidence=lambda _: True, approved=False,
    )
    assert report.status == "blocked"
    assert report.memory_proposal_sha256 is None
    assert calls == []
    assert circuit.spine.events == []


def test_rejected_evidence_blocks_memory_proposal() -> None:
    circuit, task = _fixture()
    report = run_circuit_replay_memory(
        circuit, task, cell_handler=_candidate,
        verify_evidence=lambda _: False, approved=True,
    )
    assert report.status == "blocked"
    assert report.memory_proposal_sha256 is None
    assert report.skill_promoted is False
    assert circuit.spine.verify_integrity().ok


def test_duplicate_task_cannot_reenter_replay_pipeline() -> None:
    circuit, task = _fixture()
    first = run_circuit_replay_memory(
        circuit, task, cell_handler=_candidate,
        verify_evidence=lambda _: True, approved=True,
    )
    assert first.status == "memory_proposed_not_promoted"
    before_count = len(circuit.spine.events)
    second = run_circuit_replay_memory(
        circuit, task, cell_handler=_candidate,
        verify_evidence=lambda _: True, approved=True,
    )
    assert second.status == "blocked"
    assert second.memory_proposal_sha256 is None
    assert len(circuit.spine.events) == before_count
