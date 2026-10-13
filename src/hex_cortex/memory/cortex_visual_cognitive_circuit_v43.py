"""V43 — Actual V42 visual events through the EXISTING cognitive circuit.

No trained intelligence is inferred: this exercises deterministic router,
workspace, clock, typed cell verification and canonical event recovery from
real operator-proven mask bytes. Real labels and inter-frame identity unknown.
"""
from __future__ import annotations

from pathlib import Path

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.schemas import CellResult, CellRole, CellSpec, Task
from hex_cortex.memory.cortex_object_memory_staging_v41 import (
    stage_verified_object_candidates_v41,
)
from hex_cortex.memory.cortex_visual_to_canonical_spine_v42 import (
    _LOCAL_LEDGER,
    _TYPE,
    _ledger_path,
    _payload,
)
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def run_visual_cognitive_circuit_v43(
    *, project_root: Path,
    inspection_run: str = "latest",
    approved_read: bool = False,
    approved_execution: bool = False,
    persist_circuit: bool = False,
    approved_write: bool = False,
) -> dict:
    """Operator-gated, bounded model-free circuit, not a quality benchmark."""
    if not approved_read:
        return {"status": "blocked", "reason": "v43_read_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    if not approved_execution:
        return {"status": "blocked", "reason": "v43_execution_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    if persist_circuit and not approved_write:
        return {"status": "blocked", "reason": "v43_write_approval_required",
                "files_read": False, "files_written": False, "model_called": False}
    root = Path(project_root).resolve(strict=True)
    stage = stage_verified_object_candidates_v41(
        project_root=root, inspection_run=inspection_run, approved_read=True,
    )
    if (
        stage.get("status") != "verified_pixels_pending_memory_lineage"
        or stage.get("v39_audit_rechecked") is not True
    ):
        raise ValueError("v43_upstream_evidence_unverified")
    receipt_sha = stage["inspection_receipt_sha256"]
    candidates = stage["candidates"]
    proposals = [
        _payload(item, receipt_sha) for item in candidates
    ]
    ledger_path = _ledger_path(root)
    if not ledger_path.is_file():
        raise ValueError("v43_v42_durable_spine_required")
    ledger = CanonicalSpineJsonlStore(ledger_path)
    spine = ledger.load()  # existing hash-chain verification, fail closed
    selected = [
        event for event in spine.events
        if event.event_type == _TYPE
        and event.payload.get("v40_inspection_receipt_sha256") == receipt_sha
    ]
    # Use exactly the persisted event payloads, not merely a claimed count.
    expected = {
        (p["scene_id"], p["scene_object_id"]): p for p in proposals
    }
    found = {
        (e.payload.get("scene_id"), e.payload.get("scene_object_id")): e
        for e in selected
    }
    if (
        len(expected) != len(proposals)
        or len(found) != len(selected)
        or not selected or set(found) != set(expected)
        or any(found[key].payload != value for key, value in expected.items())
    ):
        raise ValueError("v43_vision_spine_mismatch")
    # Deterministic ordering, independent of filesystem iteration.
    source_events = [found[key] for key in sorted(found)]
    refs = [event.event_hash for event in source_events]
    if len(refs) > 16:
        raise ValueError("v43_evidence_count_exceeds_circuit_budget")
    task_id = f"vision_review_{receipt_sha[:32]}"
    if spine.events_for_task(task_id):
        return {
            "status": "cognitive_circuit_task_already_recorded",
            "reason": "read_the_verified_spine_no_second_circuit_event",
            "task_id": task_id,
            "source_visual_events": len(source_events),
            "existing_spine_verified": True,
            "files_read": True, "files_written": False, "model_called": False,
            "independent_semantic_quality_attested": False,
        }
    registry = CellRegistry([
        CellSpec(
            cell_id="visual_evidence",
            role=CellRole.EVIDENCE, domains=["vision"],
            trust_score=0.75, latency_cost=0.2,
        )
    ])
    circuit = CognitiveCircuit(registry=registry, spine=spine)
    task = Task(
        task_id=task_id, content=f"Verify source image mask evidence {receipt_sha}",
        domain_hints=["vision"], novelty=0.55, risk=0.5,
        uncertainty=0.85, latency_budget_ms=10_000,
    )

    def evaluate(cell_id: str, work: Task) -> CellResult:
        return CellResult(
            cell_id=cell_id, task_id=work.task_id,
            confidence=0.0, uncertainty=1.0,
            evidence_refs=refs,
            payload={
                "verified_mask_predictions": len(refs),
                "inspection_receipt_sha256": receipt_sha,
                "pixels_and_chain_consistent": True,
                "semantic_label_correctness_verified": False,
                "identity_tracking_verified": False,
                "world_model_benchmark_verified": False,
            },
        )

    def verify(result: CellResult) -> bool:
        # Second independent local byte pass through V39->V40->V41, not
        # an external independent truth annotation or verifier authority.
        refreshed = stage_verified_object_candidates_v41(
            project_root=root, inspection_run=inspection_run, approved_read=True,
        )
        fresh = [_payload(item, refreshed["inspection_receipt_sha256"])
                 for item in refreshed["candidates"]]
        compare = {(p["scene_id"], p["scene_object_id"]): p for p in fresh}
        return (
            result.evidence_refs == refs
            and result.payload.get("inspection_receipt_sha256") == receipt_sha
            and result.payload.get("semantic_label_correctness_verified") is False
            and refreshed.get("v39_audit_rechecked") is True
            and compare == expected
        )

    report = circuit.run(
        task, cell_handler=evaluate, verify_evidence=verify, approved=True,
    )
    if report.get("status") != "verified" or not circuit.spine.verify_integrity().ok:
        raise ValueError("v43_cognitive_circuit_verification_failed")
    persisted_event_count = 0
    if persist_circuit:
        original = len(ledger.load().events)
        ledger.save(circuit.spine)
        reloaded = ledger.load()
        if not reloaded.verify_integrity().ok or len(reloaded.events) != len(circuit.spine.events):
            raise ValueError("v43_spine_readback_integrity_failed")
        persisted_event_count = len(reloaded.events) - original
    return {
        "schema": "hex.visual_cognitive_circuit.v43",
        "status": "visual_cognitive_circuit_events_persisted"
        if persist_circuit else "visual_cognitive_circuit_verified_in_memory",
        "real_source_v42_event_ids": [e.event_id for e in source_events],
        "source_mask_count": len(refs),
        "task_id": task_id,
        "cognitive_circuit_status": report["status"],
        "router_mode": report["mode"],
        "selected_cells": report["selected_cells"],
        "verified_cell_count": report["verified_cell_count"],
        "cognitive_spine_integrity": report["spine_verified"],
        "circuit_replay_events_written": persisted_event_count,
        "existing_canonical_store_reused": _LOCAL_LEDGER.as_posix(),
        "semantic_quality_independently_verified": False,
        "same_object_across_frames_verified": False,
        "world_model_improvement_attested": False,
        "automatic_skill_promotion": False,
        "model_used": False,
        "files_read": True,
        "files_written": persist_circuit and persisted_event_count > 0,
        "gpu_used": False,
        "external_network_used": False,
    }
