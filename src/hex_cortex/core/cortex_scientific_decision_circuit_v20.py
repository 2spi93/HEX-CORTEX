"""V20 scientific decision cell through real Router → Critic → CanonicalSpine.

A scientifically uncertified *provisional* policy verdict is separate from
the fact that the cognitive execution and source bytes were verified.
At each second-pass Critic check, redo governance, source integrity,
unit normalization and conservative interval decision.
"""
from __future__ import annotations

import json
from collections.abc import Callable

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_scientific_decision_v20 import (
    ScientificDecisionSpec,
    evaluate_scientific_decision,
)
from hex_cortex.core.cortex_scientific_evidence_circuit_v18 import (
    scientific_query_from_task,
)
from hex_cortex.core.cortex_scientific_knowledge_v16 import EvidenceRecord
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task


class ScientificDecisionRefusal(ValueError):
    """Fail closed without embedding source material."""


def _compute_candidate(
    cell_id: str,
    task: Task,
    *,
    spec: ScientificDecisionSpec,
    records: list[EvidenceRecord],
    verify_source: Callable[[EvidenceRecord], bool] | None,
) -> tuple[CellResult, dict[str, object]]:
    try:
        query = scientific_query_from_task(task)
    except (ValueError, TypeError) as exc:
        raise ScientificDecisionRefusal("decision_task_invalid") from exc
    if query != spec.query:
        raise ScientificDecisionRefusal("decision_task_policy_mismatch")
    result = evaluate_scientific_decision(
        spec, records, operator_approved=True, verify_source=verify_source,
    )
    if result["status"] == "blocked":
        raise ScientificDecisionRefusal("decision_source_or_policy_blocked")
    # Confidence (0) in the generic cell model means uncalibrated here,
    # NOT that the estimate is certainly false; the structured interval
    # is the sole supported uncertainty representation.
    cell = CellResult(
        cell_id=cell_id, task_id=task.task_id,
        confidence=0.0, uncertainty=1.0,
        payload={
            "scientific_decision_status": result["status"],
            "evidence_status": result["evidence_status"],
            "unit": result["unit"],
            "interval_lower": result["conservative_lower"],
            "interval_upper": result["conservative_upper"],
            "policy_sha256": result["policy_sha256"],
            "evidence_receipt_sha256": result["evidence_receipt_sha256"],
            "no_calibrated_confidence": True,
            "scientific_truth_certified": False,
            "physical_action_authorized": False,
        },
        evidence_refs=["scientific-decision:v20:" + str(result["receipt_sha256"])],
    )
    return cell, result


def run_scientific_decision_circuit(
    task: Task,
    *,
    spec: ScientificDecisionSpec,
    records: list[EvidenceRecord],
    verify_source: Callable[[EvidenceRecord], bool] | None,
    approved: bool = False,
) -> tuple[dict[str, object], CognitiveCircuit]:
    """Return separate evidence validity and provisional decision status.

    No skill promotion, source write, remote model or real-world action.
    The verifier is executed again at the Critic boundary; the decision
    outcome is not returned as a successful scientific truth claim.
    """
    circuit = CognitiveCircuit(CellRegistry([
        CellSpec(cell_id="scientific-decision", role=CellRole.EVIDENCE,
                 domains=[spec.query.domain.value])
    ]))
    proposed: dict[str, object] = {}
    checked: dict[str, object] = {}

    def handler(cell_id: str, request: Task) -> CellResult:
        cell, report = _compute_candidate(
            cell_id, request, spec=spec,
            records=records, verify_source=verify_source,
        )
        proposed.clear()
        proposed.update(report)
        return cell

    def critic(candidate: CellResult) -> bool:
        try:
            fresh, receipt = _compute_candidate(
                candidate.cell_id, task, spec=spec,
                records=records, verify_source=verify_source,
            )
        except (ScientificDecisionRefusal, ValueError, TypeError):
            return False
        ok = (
            candidate.task_id == task.task_id
            and fresh.payload == candidate.payload
            and fresh.evidence_refs == candidate.evidence_refs
            and receipt == proposed
        )
        if ok:
            checked.clear()
            checked.update(receipt)
        return ok

    result = circuit.run(
        task, cell_handler=handler, verify_evidence=critic, approved=approved,
    )
    if result["status"] == "verified" and checked:
        result["cognitive_evidence_status"] = "verified"
        result["status"] = str(checked["status"])
        result["reason"] = str(checked["reason"])
        result["scientific_decision"] = dict(checked)
    else:
        result["cognitive_evidence_status"] = "blocked"
        result["status"] = "blocked"
        result["reason"] = "decision_not_independently_reverified"
        result["scientific_decision"] = None
    result["calibrated_confidence_available"] = False
    result["scientific_truth_certified"] = False
    result["physical_action_authorized"] = False
    result["model_used"] = False
    return result, circuit


def decision_task(spec: ScientificDecisionSpec, *, task_id: str) -> Task:
    """Construct the bounded JSON envelope for the original science Router."""
    return Task(
        task_id=task_id,
        content=json.dumps(spec.query.model_dump(mode="json"), sort_keys=True),
        domain_hints=[spec.query.domain.value],
        risk=0.1, novelty=0.1, uncertainty=0.1,
    )
