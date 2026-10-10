"""Read-only, model-free evidence review of learned skill candidates.

The historical candidate/library pipeline is deliberately permissive for
staging: a single event may create an *inactive* skill record. This stricter
independent review NEVER activates or promotes it. All inputs remain local.

The trusted host must provide an independent callback that verifies real
external outcome evidence; an LLM's unsupported confidence is not proof.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from pathlib import Path

from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    CortexLearningEventJsonlStore,
    CortexLearningEventRecord,
)
from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME,
    CortexSkillCandidateJsonlStore,
    CortexSkillCandidateRecord,
)
from hex_cortex.memory.cortex_skill_library import (
    CORTEX_SKILL_LIBRARY_FILENAME,
    CortexSkillLibraryJsonlStore,
)

OutcomeVerifier = Callable[[CortexLearningEventRecord], bool]


def review_skill_evidence(
    profile: Path,
    *,
    candidate_hash: str,
    operator_approved: bool = False,
    outcome_verifier: OutcomeVerifier | None = None,
) -> dict[str, object]:
    """Inspect existing skill lineage without writing, network or inference."""
    verdict = {
        "review_type": "hex_cortex_skill_evidence_review_v7",
        "candidate_hash": candidate_hash if len(candidate_hash) == 64 else None,
        "status": "blocked",
        "blockers": [],
        "model_required": False,
        "benchmark_required": False,
        "checkout_modified": False,
        "skill_activated": False,
        "skill_promoted": False,
        "independent_evidence_checked": False,
        "operator_promotion_authorized": False,
    }
    blockers: list[str] = verdict["blockers"]
    if not operator_approved:
        blockers.append("operator_read_approval_required")
        return verdict
    if outcome_verifier is None or not callable(outcome_verifier):
        blockers.append("independent_outcome_verifier_required")
        return verdict
    if (
        len(candidate_hash) != 64
        or any(char not in "0123456789abcdef" for char in candidate_hash)
    ):
        blockers.append("invalid_candidate_hash")
        return verdict

    profile = Path(profile).resolve()
    candidates = [
        row for row in CortexSkillCandidateJsonlStore(
            profile / CORTEX_SKILL_CANDIDATE_FILENAME
        ).load() if row.candidate_hash == candidate_hash
    ]
    if len(candidates) != 1:
        blockers.append("candidate_missing_or_duplicate")
        return verdict
    candidate: CortexSkillCandidateRecord = candidates[0]
    if not candidate.candidate_allowed or not candidate.promote_to_library:
        blockers.append("candidate_not_eligible")
    source_ids = candidate.source_learning_ids
    source_hashes = candidate.source_learning_hashes
    if (
        len(source_ids) != len(source_hashes)
        or candidate.evidence_count != len(source_ids)
        or len(set(source_ids)) != len(source_ids)
    ):
        blockers.append("candidate_lineage_mismatch")
    if len(source_ids) < 3:
        blockers.append("insufficient_recurrent_evidence")

    events = CortexLearningEventJsonlStore(
        profile / CORTEX_LEARNING_EVENT_FILENAME
    ).load()
    matching = [row for row in events if row.learning_id in set(source_ids)]
    if (
        len(matching) != len(source_ids)
        or len({row.learning_id for row in matching}) != len(matching)
        or any(row.learning_hash != expected for expected, row in zip(
            source_hashes,
            (next((ev for ev in matching if ev.learning_id == source_id), None)
             for source_id in source_ids),
            strict=True,
        ) if row is None or row.learning_hash != expected)
    ):
        blockers.append("source_events_missing_or_inconsistent")

    contexts = {row.source_ref for row in matching if row.source_ref}
    if len(contexts) < 2:
        blockers.append("insufficient_distinct_contexts")
    if any(
        row.profile_path != str(profile) or row.domain != candidate.domain
        or row.reusable_rule != candidate.reusable_rule
        or row.event_allowed is not True
        or row.promote_to_skill is not True
        or row.outcome not in {"success", "correction", "reuse"}
        for row in matching
    ):
        blockers.append("unverified_or_cross_scoped_learning_event")

    if blockers:
        return verdict

    checked = 0
    for row in matching:
        try:
            if not outcome_verifier(row):
                blockers.append("independent_outcome_evidence_failed")
                break
        except Exception:  # noqa: BLE001 - source exception may contain secrets
            blockers.append("independent_outcome_verifier_failed")
            break
        checked += 1
    verdict["independent_evidence_checked"] = checked == len(matching) and not blockers
    if blockers:
        return verdict

    registered = CortexSkillLibraryJsonlStore(
        profile / CORTEX_SKILL_LIBRARY_FILENAME
    ).load()
    linked = [
        row for row in registered if row.source_candidate_hash == candidate_hash
    ]
    if any(row.active for row in linked):
        blockers.append("existing_active_skill_requires_separate_audit")
        return verdict
    receipt = {
        "candidate_hash": candidate_hash,
        "source_hashes": sorted(source_hashes),
        "source_count": len(source_ids),
        "context_count": len(contexts),
        "inactive_library_entry_count": len(linked),
    }
    verdict.update({
        "status": "reviewable_not_promoted",
        "source_count": len(source_ids),
        "context_count": len(contexts),
        "inactive_library_entry_count": len(linked),
        "lineage_sha256": hashlib.sha256(
            json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "next_action": "human_review_then_separate_promotion_gate",
        "proof_limitations": [
            "external verifier reliability is the trusted caller's responsibility",
            "source records do not attest multiple independent model identities",
            "this review does not activate skills or modify any repository",
        ],
    })
    return verdict
