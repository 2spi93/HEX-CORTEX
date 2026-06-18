from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.cortex_learning_event import CORTEX_LEARNING_EVENT_FILENAME
from hex_cortex.memory.cortex_learning_event import record_cortex_learning_event
from hex_cortex.memory.cortex_learning_event import summarize_cortex_learning_events
from hex_cortex.memory.cortex_tree_evidence_update import (
    CORTEX_TREE_EVIDENCE_UPDATE_FILENAME,
    CortexTreeEvidenceUpdateJsonlStore,
    CortexTreeEvidenceUpdateRecord,
)


def build_cortex_outcome_learning_event(profile: Path) -> dict[str, object]:
    update = _latest_update(profile)
    if update is None:
        return _blocked_payload(profile, ["missing_tree_evidence_update"])
    if update.update_allowed is not True:
        return _blocked_payload(profile, ["tree_evidence_update_not_allowed"])
    if update.next_action != "create_outcome_learning_event":
        return _blocked_payload(profile, ["tree_evidence_update_not_waiting_outcome_learning_event"])
    payload = record_cortex_learning_event(
        profile,
        outcome="success",
        domain="architecture",
        scope="repo",
        source_ref=update.update_hash,
        problem="Convert a validated memory-first build branch into reusable architecture learning.",
        action_taken=_action_taken(update),
        result=_result(update),
        lesson=_lesson(update),
        reusable_rule=_reusable_rule(update),
        confidence=_confidence(update),
    )
    payload["outcome_learning_type"] = "cortex_outcome_learning_event"
    payload["source_update_hash"] = update.update_hash
    payload["next_action"] = "inspect_skill_candidate_readiness"
    return payload


def summarize_cortex_outcome_learning_events(profile: Path) -> dict[str, object]:
    return summarize_cortex_learning_events(profile / CORTEX_LEARNING_EVENT_FILENAME)


def _latest_update(profile: Path) -> CortexTreeEvidenceUpdateRecord | None:
    records = CortexTreeEvidenceUpdateJsonlStore(profile / CORTEX_TREE_EVIDENCE_UPDATE_FILENAME).load()
    return records[-1] if records else None


def _action_taken(update: CortexTreeEvidenceUpdateRecord) -> str:
    return (
        "Ran the gated memory-first rail through local patch plan, test receipt, "
        f"and tree evidence update for {update.target_frontier_node_id}."
    )


def _result(update: CortexTreeEvidenceUpdateRecord) -> str:
    return (
        f"Tests passed with {update.passed_count} passing checks; evidence_score={update.evidence_score}; "
        f"updated_nodes={update.updated_node_count}."
    )


def _lesson(update: CortexTreeEvidenceUpdateRecord) -> str:
    return (
        "A memory-first branch should be promoted only after a receipt-backed tree evidence update proves the selected path."
    )


def _reusable_rule(update: CortexTreeEvidenceUpdateRecord) -> str:
    return (
        "For HEX-CORTEX architecture work, close each branch by recording test receipt, updating the hypothesis tree path, "
        "then converting the outcome into a reusable learning event before proposing broader execution layers."
    )


def _confidence(update: CortexTreeEvidenceUpdateRecord) -> float:
    base = 0.80
    if update.evidence_score >= 1.0 and update.passed_count > 0:
        return 0.92
    return base


def _blocked_payload(profile: Path, blockers: list[str]) -> dict[str, object]:
    return {
        "outcome_learning_type": "cortex_outcome_learning_event",
        "profile_path": str(profile),
        "learning_record": None,
        "event_allowed": False,
        "event_status": "blocked",
        "event_decision": "outcome_learning_event_blocked",
        "blockers": blockers,
        "next_action": "repair_tree_evidence_update",
    }
