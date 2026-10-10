"""Cross-domain science evidence wired into the real HEX-CORTEX cognitive circuit.

The scientific cell computes a redacted evidence receipt; CognitiveCircuit
runs the independent host-supplied verifier AGAIN at the critic boundary.
This catches source changes during a run but is not a publisher attestation,
a cryptographic signature, a new scientific oracle, or a network client.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from pydantic import ValidationError

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceQuery,
    EvidenceRecord,
    review_scientific_knowledge,
)
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain

SourceVerifier = Callable[[EvidenceRecord], bool]


class ScientificCircuitRefusal(ValueError):
    """Fail closed without echoing source errors, prompts or raw documents."""


def scientific_query_from_task(task: Task) -> EvidenceQuery:
    if not isinstance(task.content, str) or len(task.content) > 512:
        raise ScientificCircuitRefusal("scientific_task_bounded_json_required")
    try:
        payload = json.loads(task.content)
    except (ValueError, TypeError) as exc:
        raise ScientificCircuitRefusal("scientific_task_json_invalid") from exc
    if not isinstance(payload, dict) or set(payload) != {
        "claim_id", "domain", "result_unit"
    }:
        raise ScientificCircuitRefusal("scientific_task_shape_invalid")
    try:
        query = EvidenceQuery.model_validate(payload)
    except (ValidationError, ValueError, TypeError) as exc:
        raise ScientificCircuitRefusal("scientific_task_query_invalid") from exc
    if query.domain.value not in task.domain_hints:
        raise ScientificCircuitRefusal("scientific_task_domain_mismatch")
    return query


def scientific_evidence_cell_result(
    cell_id: str,
    task: Task,
    *,
    records: list[EvidenceRecord],
    verify_source: SourceVerifier | None = None,
    operator_approved: bool = False,
) -> CellResult:
    """Propose only a consistent, host-checked and redacted knowledge report."""
    if not operator_approved:
        raise ScientificCircuitRefusal("scientific_cell_operator_approval_required")
    query = scientific_query_from_task(task)
    report = review_scientific_knowledge(
        query, records,
        operator_approved=operator_approved,
        verify_source=verify_source,
    )
    if report["status"] != "consistent_evidence_not_certified":
        raise ScientificCircuitRefusal("scientific_evidence_not_consistent")
    return CellResult(
        cell_id=cell_id, task_id=task.task_id,
        confidence=0.5, uncertainty=0.5,
        evidence_refs=["scientific:v18:" + str(report["receipt_sha256"])],
        payload={
            "claim_sha256": report["claim_sha256"],
            "source_manifest_sha256": report["source_manifest_sha256"],
            "interval_lower": report["interval_lower"],
            "interval_upper": report["interval_upper"],
            "unit": report["unit"],
            "truth_certified": False,
            "source_independence_certified": False,
            "physical_action_authorized": False,
        },
    )


def verify_scientific_evidence_cell_result(
    candidate: CellResult, task: Task, *,
    records: list[EvidenceRecord],
    verify_source: SourceVerifier | None,
) -> bool:
    """Recheck source bytes/claims on each independent circuit verification."""
    try:
        expected = scientific_evidence_cell_result(
            candidate.cell_id, task, records=records,
            verify_source=verify_source, operator_approved=True,
        )
    except (ScientificCircuitRefusal, ValidationError, ValueError, TypeError):
        return False
    return (
        candidate.task_id == task.task_id
        and candidate.payload == expected.payload
        and candidate.evidence_refs == expected.evidence_refs
    )


def run_scientific_evidence_circuit(
    task: Task,
    *,
    records: list[EvidenceRecord],
    verify_source: SourceVerifier | None,
    approved: bool = False,
) -> tuple[dict[str, object], CognitiveCircuit]:
    """Full deterministic route → evidence cell → critic → replayable spine.

    This creates a fresh single-task circuit. The caller must manage durable
    multi-task memory separately; no implicit storage or source writes.
    """
    if not approved:
        circuit = CognitiveCircuit(registry=CellRegistry([
            CellSpec(cell_id="scientific-evidence", role=CellRole.EVIDENCE,
                     domains=[d.value for d in KnowledgeDomain])
        ]))
        return circuit.run(
            task, cell_handler=lambda _cid, _task: None,
            approved=False,
        ), circuit
    try:
        query = scientific_query_from_task(task)
    except ScientificCircuitRefusal:
        circuit = CognitiveCircuit(registry=CellRegistry([
            CellSpec(cell_id="scientific-evidence", role=CellRole.EVIDENCE,
                     domains=[d.value for d in KnowledgeDomain])
        ]))
        return {"status": "blocked", "reason": "scientific_task_invalid",
                "checkout_modified": False, "model_used": False}, circuit
    circuit = CognitiveCircuit(registry=CellRegistry([
        CellSpec(
            cell_id="scientific-evidence",
            role=CellRole.EVIDENCE,
            domains=[query.domain.value],
        ),
    ]))
    output = circuit.run(
        task, approved=True,
        cell_handler=lambda cell_id, item: scientific_evidence_cell_result(
            cell_id, item, records=records, verify_source=verify_source,
            operator_approved=True,
        ),
        verify_evidence=lambda candidate: verify_scientific_evidence_cell_result(
            candidate, task, records=records, verify_source=verify_source,
        ),
    )
    return output, circuit
