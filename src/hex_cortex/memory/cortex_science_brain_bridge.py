"""Explicit CPU-safe cross-domain verified-science -> actual LocalHarness Brain path.

An actual math/physics/chemistry CognitiveCircuit runs first. Its redacted
evidence is linked into the same Harness Spine; bounded typed cell data is
provided to an explicitly approved Brain as data (not tool authority).
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable

from hex_cortex.core.cortex_verified_science_circuit import run_verified_science_circuit
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import LocalHarness, Task


def run_science_guided_brain(
    *,
    harness: LocalHarness,
    task: Task,
    scientific_request: str,
    domain: str,
    model_id: str,
    brain: Callable[[str, Task], str],
    approve_science: bool = False,
    approve_model: bool = False,
    max_latency_ms: int = 120_000,
) -> dict[str, object]:
    """No automatic model call and no science claim inferred from model output."""
    if not (approve_science and approve_model):
        return {
            "status": "blocked",
            "reason": "independent_science_and_model_approval_required",
            "model_calls": 0,
            "scientific_calculation_performed": False,
            "model_answer_independently_verified": False,
        }
    if task.domain != domain or task.requested_tool is not None:
        raise ValueError("science_domain_or_tool_authorization_mismatch")
    if not model_id.strip() or len(task.instruction) > 12_000:
        raise ValueError("science_brain_input_invalid")
    if not harness.verify_replay():
        raise ValueError("harness_spine_or_receipts_invalid")
    if harness.spine.events_for_task(task.task_id):
        raise ValueError("science_brain_duplicate_task_id")

    science = run_verified_science_circuit(
        domain=domain,
        task_id=task.task_id,
        request=scientific_request,
        approved=True,
    )
    if science["status"] != "verified_science_circuit":
        return {
            "status": "blocked",
            "reason": "scientific_evidence_not_verified",
            "model_calls": 0,
            "scientific_calculation_performed": True,
            "model_answer_independently_verified": False,
        }
    evidence = science["verified_payload"]
    assert isinstance(evidence, dict)
    if len(json.dumps(evidence, sort_keys=True, default=str)) > 3_000:
        raise ValueError("scientific_evidence_context_budget_exceeded")
    evidence_json = json.dumps(evidence, sort_keys=True, ensure_ascii=False)
    context = (
        "Independent, domain-bounded scientific calculator data follows. "
        "This is NOT an instruction or permission to operate any tool/device. "
        "Its physical assumptions and uncertainty are limited to the named domain.\n"
        f"Verified domain: {domain}\n"
        f"Calculator evidence (JSON data): {evidence_json}\n"
        f"Operator question: {task.instruction}"
    )
    request_hash = hashlib.sha256(scientific_request.encode("utf-8")).hexdigest()
    proof_hash = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
    harness.spine.append(
        event_type="science.verified_cell_receipt",
        task_id=task.task_id,
        source="VerifiedScienceCircuit",
        payload={
            "domain": domain,
            "request_sha256": request_hash,
            "verified_payload_sha256": proof_hash,
            "evidence_refs": science["evidence_refs"],
            "science_circuit_spine_verified": science["spine_integrity_ok"],
        },
        confidence=1.0,
    )
    result = run_clocked_local_task(
        harness,
        Task(task_id=task.task_id, domain=domain, instruction=context),
        models=[model_id],
        brain=brain,
        approved=True,
        max_latency_ms=max_latency_ms,
    )
    return {
        "status": result["status"],
        "reason": result["reason"],
        "scientific_domain": domain,
        "scientific_evidence_refs": science["evidence_refs"],
        "scientific_input_sha256": request_hash,
        "verified_scientific_payload_sha256": proof_hash,
        "harness_spine_verified": result["canonical_spine_verified"],
        "harness_receipt_sha256": result["receipt"]["sha256"]
        if isinstance(result.get("receipt"), dict) else None,
        "model_calls": 1 if harness._model_calls else 0,
        "answer": result.get("output"),
        "scientific_calculation_performed": True,
        "model_answer_independently_verified": False,
        "real_world_science_certified": False,
        "physical_action_authorized": False,
        "files_saved": False,
    }
