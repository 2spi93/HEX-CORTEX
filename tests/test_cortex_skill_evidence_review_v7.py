"""Independent outcome review: candidate lineage, context diversity, no activation."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_learning_event import (
    CORTEX_LEARNING_EVENT_FILENAME,
    CortexLearningEventJsonlStore,
    CortexLearningEventRecord,
)
from hex_cortex.memory.cortex_skill_candidate import (
    CORTEX_SKILL_CANDIDATE_FILENAME,
    CortexSkillCandidateJsonlStore,
    _candidate_from_group,
)
from hex_cortex.memory.cortex_skill_evidence_review_v7 import review_skill_evidence
from hex_cortex.memory.cortex_skill_library import build_cortex_skill_library


def _record(profile: Path, index: int, *, context: str | None = None) -> CortexLearningEventRecord:
    return CortexLearningEventRecord(
        learning_id=f"source-event-{index}",
        profile_path=str(profile), outcome="correction", domain="coding", scope="repo",
        source_ref=context or f"isolated-test-context-{index % 2}",
        problem="Recurrent error demonstrated by real verification",
        action_taken="Applied a correction during a controlled test",
        result="Independent functional test produced expected output",
        lesson="We must verify behavior before claiming the fix",
        reusable_rule="Run deterministic tests on all changed error paths",
        confidence=0.9, promote_to_skill=True,
        event_status="accepted", event_decision="learning_event_accepted",
        event_allowed=True, blockers=[], learning_hash=f"{index:064x}",
        reasons=["external_verified"],
    )


def _prepare(profile: Path, count: int, *, contexts: bool = True):
    records = [_record(profile, i, context=(
        None if contexts else "same-context"
    )) for i in range(1, count + 1)]
    store = CortexLearningEventJsonlStore(profile / CORTEX_LEARNING_EVENT_FILENAME)
    for record in records:
        store.append(record)
    candidate = _candidate_from_group(
        profile, "coding", records[0].reusable_rule, records
    )
    CortexSkillCandidateJsonlStore(
        profile / CORTEX_SKILL_CANDIDATE_FILENAME
    ).append_many([candidate])
    return candidate


def test_three_recurrent_sources_and_external_verifier_reviewable_not_active(
    tmp_path: Path,
) -> None:
    profile = tmp_path / "profile"
    candidate = _prepare(profile, 3)
    build_cortex_skill_library(profile)
    before = {
        str(path): path.read_bytes()
        for path in profile.iterdir() if path.is_file()
    }
    seen = []
    def independent(record):
        seen.append(record.learning_id)
        return record.learning_hash.startswith("0")
    review = review_skill_evidence(
        profile, candidate_hash=candidate.candidate_hash,
        operator_approved=True, outcome_verifier=independent,
    )
    assert review["status"] == "reviewable_not_promoted"
    assert review["source_count"] == 3
    assert review["context_count"] == 2
    assert review["independent_evidence_checked"] is True
    assert len(seen) == 3
    assert review["skill_promoted"] is False
    assert review["skill_activated"] is False
    assert review["model_required"] is False
    assert "Run deterministic tests" not in json.dumps(review)
    after = {
        str(path): path.read_bytes()
        for path in profile.iterdir() if path.is_file()
    }
    assert before == after


def test_single_learning_event_is_not_reliable_learning_proof(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    candidate = _prepare(profile, 1)
    review = review_skill_evidence(
        profile, candidate_hash=candidate.candidate_hash,
        operator_approved=True, outcome_verifier=lambda _: True,
    )
    assert review["status"] == "blocked"
    assert "insufficient_recurrent_evidence" in review["blockers"]


def test_same_context_is_not_cross_context_recurrence(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    candidate = _prepare(profile, 3, contexts=False)
    review = review_skill_evidence(
        profile, candidate_hash=candidate.candidate_hash,
        operator_approved=True, outcome_verifier=lambda _: True,
    )
    assert "insufficient_distinct_contexts" in review["blockers"]


def test_unapproved_read_and_no_trusted_verifier_do_not_access_disk(tmp_path: Path) -> None:
    profile = tmp_path / "missing"
    deny = review_skill_evidence(
        profile, candidate_hash="a" * 64,
        operator_approved=False, outcome_verifier=lambda _: True,
    )
    assert deny["blockers"] == ["operator_read_approval_required"]
    no_verifier = review_skill_evidence(
        profile, candidate_hash="a" * 64, operator_approved=True,
    )
    assert no_verifier["blockers"] == ["independent_outcome_verifier_required"]
    assert not profile.exists()


def test_candidate_lineage_hash_tampering_blocks_without_callback(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    candidate = _prepare(profile, 3)
    candidate.source_learning_hashes[1] = "a" * 64
    candidate.candidate_hash = "b" * 64
    store = CortexSkillCandidateJsonlStore(profile / "cortex-skill-candidate.jsonl")
    store.save([candidate])
    called = []
    review = review_skill_evidence(
        profile, candidate_hash=candidate.candidate_hash,
        operator_approved=True,
        outcome_verifier=lambda row: called.append(row) or True,
    )
    assert "source_events_missing_or_inconsistent" in review["blockers"]
    assert not called


def test_bad_external_verifier_never_claims_proof(tmp_path: Path) -> None:
    profile = tmp_path / "profile"
    candidate = _prepare(profile, 3)
    def raises(_):
        raise RuntimeError("PRIVATE_TOKEN secret")
    review = review_skill_evidence(
        profile, candidate_hash=candidate.candidate_hash,
        operator_approved=True, outcome_verifier=raises,
    )
    assert review["status"] == "blocked"
    assert "independent_outcome_verifier_failed" in review["blockers"]
    assert "PRIVATE_TOKEN" not in json.dumps(review)
