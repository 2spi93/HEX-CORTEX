"""Deterministic end-to-end cognitive circuit → replay → memory proposal.

Uses existing HEX-CORTEX routing, registry, workspace, clock, spine,
replay compression and integrity checking. This does not trigger models,
retrieval providers, tool execution, filesystem writes or skill promotion.
It cannot establish verifier independence solely from the callback signature.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass

from hex_cortex.core.cognitive_circuit_v1 import CognitiveCircuit
from hex_cortex.core.schemas import CellResult, Task
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayStatus


@dataclass(frozen=True)
class MemoryWorkflowResult:
    status: str
    task_id_sha256: str
    circuit_completed: bool
    spine_verified: bool
    replay_event_count: int
    memory_proposal_sha256: str | None
    lineage_sha256: str | None
    skill_promoted: bool = False
    skill_activated: bool = False
    memory_persisted: bool = False
    checkout_modified: bool = False
    local_model_used: bool = False
    cloud_provider_called: bool = False
    real_independent_outcome_certified: bool = False
    retrieval_cycle_integrated: bool = False


def run_circuit_replay_memory(
    circuit: CognitiveCircuit,
    task: Task,
    *,
    cell_handler: Callable[[str, Task], CellResult],
    verify_evidence: Callable[[CellResult], bool] | None = None,
    approved: bool = False,
) -> MemoryWorkflowResult:
    """Materialize a proposed memory only when the entire trusted circuit completes.

    No model-generated result is allowed to promote itself; external truth
    and a separate gate are mandatory in the real runtime.
    """
    task_digest = hashlib.sha256(task.task_id.encode()).hexdigest()
    before_count = len(circuit.spine.events)
    verdict = circuit.run(
        task, cell_handler=cell_handler, verify_evidence=verify_evidence,
        approved=approved,
    )
    completed = verdict["status"] == "verified"
    if not completed:
        return MemoryWorkflowResult(
            status="blocked", task_id_sha256=task_digest,
            circuit_completed=False,
            spine_verified=circuit.spine.verify_integrity().ok,
            replay_event_count=len(circuit.spine.events) - before_count,
            memory_proposal_sha256=None, lineage_sha256=None,
        )
    if not circuit.spine.verify_integrity().ok:
        return MemoryWorkflowResult(
            status="blocked", task_id_sha256=task_digest,
            circuit_completed=False, spine_verified=False,
            replay_event_count=0,
            memory_proposal_sha256=None, lineage_sha256=None,
        )
    replay = ReplayEngine(spine=circuit.spine).replay_task(task.task_id)
    if (
        replay.status != ReplayStatus.CONSOLIDATED
        or replay.episode is None
        or replay.episode.outcome.value != "success"
        or replay.memory is None
        or replay.compression is None
        or not replay.source_event_ids
    ):
        return MemoryWorkflowResult(
            status="blocked", task_id_sha256=task_digest,
            circuit_completed=True,
            spine_verified=replay.spine_integrity_ok,
            replay_event_count=replay.event_count,
            memory_proposal_sha256=None, lineage_sha256=None,
        )
    # Hash complete proposed record, not just a field of possibly leaky text.
    memory_digest = hashlib.sha256(
        replay.memory.model_dump_json().encode()
    ).hexdigest()
    lineage = hashlib.sha256(
        json.dumps(replay.source_event_ids, sort_keys=True).encode()
    ).hexdigest()
    return MemoryWorkflowResult(
        status="memory_proposed_not_promoted",
        task_id_sha256=task_digest,
        circuit_completed=True,
        spine_verified=True,
        replay_event_count=replay.event_count,
        memory_proposal_sha256=memory_digest,
        lineage_sha256=lineage,
    )
