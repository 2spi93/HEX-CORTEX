"""One typed CognitiveCircuit entry point for existing Math/Physics/Chemistry cells.

No new science simulator, network client, model inference, file writes or
physical actuation. Scientific assumptions remain those of the original cells.
"""
from __future__ import annotations

from collections.abc import Callable

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.cortex_chemistry_cell_v15 import (
    chemistry_cell_result,
    verify_chemistry_cell_result,
)
from hex_cortex.core.cortex_exact_math_v13 import (
    math_cell_result,
    verify_math_cell_result,
)
from hex_cortex.core.cortex_physics_cell_v14 import physics_cell_result
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task

_DOMAINS = {
    "mathematics": CellRole.MATH,
    "physics": CellRole.PHYSICS,
    "chemistry": CellRole.CHEMISTRY,
}


def run_verified_science_circuit(
    *,
    domain: str,
    task_id: str,
    request: str,
    approved: bool = False,
    verifier_override: Callable[[CellResult], bool] | None = None,
) -> dict[str, object]:
    """Route, compute, recheck and audit an explicit task via existing cells."""
    if domain not in _DOMAINS or not task_id.strip() or not request.strip():
        raise ValueError("unsupported_or_empty_science_request")
    if len(request) > 4096:
        raise ValueError("science_request_too_large")
    registry = CellRegistry([
        CellSpec(
            cell_id=f"exact-{domain}", role=_DOMAINS[domain],
            domains=[domain], trust_score=0.95,
        )
    ])
    circuit = CognitiveCircuit(registry=registry)
    if not approved:
        return {
            "status": "blocked",
            "reason": "science_circuit_requires_operator_approval",
            "model_called": False,
            "spine_event_count": 0,
        }

    task = Task(task_id=task_id, content=request, domain_hints=[domain])
    evidence: dict[str, CellResult] = {}

    def handler(cell_id: str, t: Task) -> CellResult:
        if domain == "mathematics":
            result = math_cell_result(cell_id, t, approved=True)
        elif domain == "physics":
            result = physics_cell_result(cell_id, t, approved=True)
        else:
            result = chemistry_cell_result(cell_id, t, approved=True)
        evidence["result"] = result
        return result

    def verify(candidate: CellResult) -> bool:
        # The verifier runs again, not just trusting the producer's confidence.
        try:
            if domain == "mathematics":
                accepted = verify_math_cell_result(candidate, request)
            elif domain == "physics":
                checked = physics_cell_result(candidate.cell_id, task, approved=True)
                accepted = (
                    checked.payload == candidate.payload
                    and checked.evidence_refs == candidate.evidence_refs
                    and checked.task_id == candidate.task_id
                )
            else:
                accepted = verify_chemistry_cell_result(candidate, request)
            if verifier_override is not None:
                accepted = accepted and verifier_override(candidate)
            return accepted
        except (ValueError, TypeError, OverflowError, RecursionError):
            return False

    report = circuit.run(
        task, approved=True, cell_handler=handler, verify_evidence=verify
    )
    verified = report["status"] == "verified"
    result = evidence.get("result") if verified else None
    return {
        "status": "verified_science_circuit" if verified else "blocked",
        "reason": report["reason"],
        "domain": domain,
        "circuit_status": report["status"],
        "selected_cells": report.get("selected_cells", []),
        "verified_cell_count": report.get("verified_cell_count", 0),
        "evidence_refs": list(result.evidence_refs) if result else [],
        "verified_payload": result.payload if result else None,
        "spine_integrity_ok": circuit.spine.verify_integrity().ok,
        "spine_event_count": len(circuit.spine.events),
        "model_called": False,
        "scientific_truth_independently_certified": False,
        "real_world_measurement_verified": False,
        "physical_action_authorized": False,
        "files_written": False,
    }
