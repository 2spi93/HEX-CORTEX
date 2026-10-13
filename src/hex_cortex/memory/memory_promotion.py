"""Controlled promotion of replayed experiences to reusable memory.

This module implements the minimal integration needed to promote a MemoryRecord
to the local knowledge index when its provenance and integrity are validated.

Key distinctions preserved:
- Successful execution ≠ reliable rule (requires verification across contexts)
- Hypothesis ≠ verified rule (tracked separately until confirmed)
- Error observation ≠ failure pattern (requires recurrence)

Safety guarantees:
- No secrets, raw outputs, or untrusted instructions persisted without explicit approval
- Read-only mode NEVER modifies the index (even with explicit_approval)
- Durable persistence requires explicit authorization
- Duplicate prevention on repeated replay
- Source event references preserved for audit trail

Security model:
- explicit_approval ONLY bypasses: low confidence deferral
- explicit_approval NEVER bypasses: integrity, provenance, content bans, sensitivity ceiling, read-only mode
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import (
    IndexEntry,
    MemoryRecord,
    MemorySensitivity,
    MemoryType,
    ReplayOutcome,
)
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayReport, ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


class PromotionStatus(StrEnum):
    """Status of a memory promotion attempt."""

    PROMOTED = "promoted"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    DUPLICATE = "duplicate"


class RejectionReason(StrEnum):
    """Reason for rejecting a memory promotion.

    These are ordered by severity - integrity and provenance issues
    are never bypassable, while low_confidence can be overridden.
    """

    # Non-bypassable (security-critical)
    INTEGRITY_FAILED = "integrity_failed"
    MISSING_PROVENANCE = "missing_provenance"
    INADMISSIBLE_CONTENT = "inadmissible_content"
    SENSITIVE_CONTENT = "sensitive_content"
    READ_ONLY_MODE = "read_only_mode"
    # Bypassable with explicit_approval
    LOW_CONFIDENCE = "low_confidence"
    # State-based (not a security check)
    DUPLICATE = "duplicate"


# Strict sensitivity ordering: LOW < MEDIUM < HIGH
_SENSITIVITY_ORDER: dict[MemorySensitivity, int] = {
    MemorySensitivity.LOW: 0,
    MemorySensitivity.MEDIUM: 1,
    MemorySensitivity.HIGH: 2,
}


def _sensitivity_exceeds_limit(sensitivity: MemorySensitivity, limit: MemorySensitivity) -> bool:
    """Check if sensitivity exceeds the allowed limit using strict ordering.

    Args:
        sensitivity: The memory's sensitivity level
        limit: The maximum allowed sensitivity level

    Returns:
        True if sensitivity > limit (strict ordering)
    """
    return _SENSITIVITY_ORDER.get(sensitivity, 1) > _SENSITIVITY_ORDER.get(limit, 1)


@dataclass(frozen=True)
class PromotionCriteria:
    """Criteria for promoting a memory record to the index.

    Security-critical criteria (never bypassable):
    - require_source_events: Must have source_event_ids
    - allowed_outcomes: Which outcomes are admissible
    - max_sensitivity: Maximum sensitivity level allowed
    - blocked_tags: Tags that always cause rejection

    Bypassable criteria (can be overridden with explicit_approval):
    - min_confidence: Minimum confidence threshold
    """

    min_confidence: float = 0.5
    require_source_events: bool = True
    require_outcome: bool = True
    allowed_outcomes: frozenset[ReplayOutcome] = field(
        default_factory=lambda: frozenset({ReplayOutcome.SUCCESS, ReplayOutcome.FAILURE})
    )
    max_sensitivity: MemorySensitivity = MemorySensitivity.MEDIUM
    blocked_tags: frozenset[str] = field(
        default_factory=lambda: frozenset({"secret", "credential", "password", "token", "api_key"})
    )


@dataclass
class PromotionResult:
    """Result of a memory promotion attempt."""

    status: PromotionStatus
    memory: MemoryRecord | None
    index_entry: IndexEntry | None
    rejection_reason: RejectionReason | None = None
    details: dict[str, Any] = field(default_factory=dict)
    bypassable: bool = True  # False if rejection reason cannot be bypassed


class MemoryPromoter:
    """Controlled promotion of replayed experiences to reusable memory.

    This class implements the promotion boundary between:
    1. ReplayEngine output (MemoryRecord from consolidation)
    2. LocalKnowledgeIndex (searchable, retrievable memory)

    FAIL-CLOSED SECURITY MODEL:
    - NO spine provided = ALL promotions REJECTED (fail-closed default)
    - Spine MUST have verified cryptographic integrity
    - ALL source_event_ids MUST exist in spine and match task/episode
    - explicit_approval NEVER bypasses integrity, provenance, or spine requirements
    - Custom criteria CANNOT weaken spine/provenance requirements

    Promotion is NOT automatic. A MemoryRecord must pass:
    - Spine MUST be provided and non-null - NEVER BYPASSED
    - Spine integrity MUST be cryptographically verified - NEVER BYPASSED
    - ALL source events MUST exist in spine and match task - NEVER BYPASSED
    - Content admissibility (no secrets, credentials, or blocked patterns) - NEVER BYPASSED
    - Sensitivity check (not HIGH sensitivity) - NEVER BYPASSED
    - Read-only mode check - NEVER BYPASSED
    - Confidence threshold (minimum confidence level) - BYPASSABLE with explicit_approval
    - Duplicate detection (not already promoted) - State check, not security

    Security model:
    - read_only=True ALWAYS prevents index mutation, even with explicit_approval=True
    - spine=None ALWAYS prevents ANY promotion (fail-closed)
    - explicit_approval ONLY allows low-confidence memories to be promoted
    - explicit_approval NEVER allows: missing spine, integrity failures, missing provenance,
      inadmissible content, sensitivity violations, or read-only mode bypass
    """

    # Set of rejection reasons that can NEVER be bypassed
    NON_BYPASSABLE_REASONS: frozenset[RejectionReason] = frozenset({
        RejectionReason.INTEGRITY_FAILED,
        RejectionReason.MISSING_PROVENANCE,
        RejectionReason.INADMISSIBLE_CONTENT,
        RejectionReason.SENSITIVE_CONTENT,
        RejectionReason.READ_ONLY_MODE,
    })

    def __init__(
        self,
        index: LocalKnowledgeIndex,
        spine: CanonicalSpine | None = None,
        criteria: PromotionCriteria | None = None,
        read_only: bool = False,
        require_spine: bool = True,  # FAIL-CLOSED: spine required by default
    ) -> None:
        self.index = index
        self.spine = spine
        self.criteria = criteria or PromotionCriteria()
        self.read_only = read_only
        # Compatibility argument retained, but provenance is always mandatory.
        # Passing require_spine=False cannot weaken the security boundary.
        self.require_spine = True
        self._promoted_ids: set[str] = set()
        self._promotion_history: list[PromotionResult] = []
        # Snapshot of index entry count before each promotion attempt
        self._index_snapshot_count: int | None = None

    def promote_from_replay(
        self,
        replay_report: ReplayReport,
        *,
        explicit_approval: bool = False,
    ) -> PromotionResult:
        """Promote a memory record from a replay report.

        Args:
            replay_report: The replay report containing the consolidated memory
            explicit_approval: If True, allows bypass of LOW_CONFIDENCE only.
                Does NOT bypass: spine requirement, integrity, provenance, content bans,
                sensitivity, read-only, or falsified reports.

        Returns:
            PromotionResult with status, memory, and any rejection reason

        Security guarantees (FAIL-CLOSED):
        - Rejects if self.spine is None (fail-closed default)
        - Rejects if replay_report.status != CONSOLIDATED (integrity check)
        - Rejects if replay_report.spine_integrity_ok is False (even if status=CONSOLIDATED)
        - Rejects if memory is None (missing provenance)
        - Rejects if memory.task_id does not match events in spine
        - explicit_approval does NOT bypass any of these checks
        """
        # CRITICAL FAIL-CLOSED: Spine MUST be provided regardless of options.
        if self.spine is None:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=None,
                index_entry=None,
                rejection_reason=RejectionReason.INTEGRITY_FAILED,
                details={"reason": "spine_required_fail_closed"},
                bypassable=False,
            )

        # CRITICAL: Check replay status first (integrity gate)
        if replay_report.status != ReplayStatus.CONSOLIDATED:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=None,
                index_entry=None,
                rejection_reason=RejectionReason.INTEGRITY_FAILED,
                details={"replay_status": replay_report.status.value},
                bypassable=False,
            )

        # CRITICAL: Check spine integrity - even if status says CONSOLIDATED
        # This prevents falsified reports with spine_integrity_ok=True from bypassing checks
        spine_integrity_ok = getattr(replay_report, "spine_integrity_ok", None)
        if spine_integrity_ok is False:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=None,
                index_entry=None,
                rejection_reason=RejectionReason.INTEGRITY_FAILED,
                details={"reason": "spine_integrity_check_failed"},
                bypassable=False,
            )

        # Never trust the report's integrity flag without checking the actual spine.
        actual_integrity = self.spine.verify_integrity()
        if not actual_integrity.ok:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=None,
                index_entry=None,
                rejection_reason=RejectionReason.INTEGRITY_FAILED,
                details={
                    "reason": "report_claims_integrity_but_spine_tampered",
                    "actual_integrity_reason": actual_integrity.reason,
                },
                bypassable=False,
            )

        memory = replay_report.memory
        if memory is None:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=None,
                index_entry=None,
                rejection_reason=RejectionReason.MISSING_PROVENANCE,
                details={"reason": "no_memory_in_replay_report"},
                bypassable=False,
            )

        # A ReplayReport must be bound to exactly the task and event set that
        # produced the memory. An integrity flag is NOT proof of that binding.
        reported_ids = replay_report.source_event_ids
        if (
            not reported_ids
            or len(reported_ids) != replay_report.event_count
            or len(set(reported_ids)) != len(reported_ids)
            or set(reported_ids) != set(memory.source_event_ids)
            or replay_report.episode is None
            or replay_report.episode.task_id != replay_report.task_id
            or (
                replay_report.compression is not None
                and set(replay_report.compression.source_event_ids) != set(reported_ids)
            )
        ):
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.MISSING_PROVENANCE,
                details={"reason": "replay_report_lineage_mismatch"},
                bypassable=False,
            )
        # Independently reconstruct the report from the checked event chain.
        # source_event_ids alone do not authenticate arbitrary report text.
        reconstructed = ReplayEngine(spine=self.spine).replay_task(replay_report.task_id)
        expected_memory = reconstructed.memory
        if (
            reconstructed.status != ReplayStatus.CONSOLIDATED
            or expected_memory is None
            or set(reconstructed.source_event_ids) != set(reported_ids)
            or memory.title != expected_memory.title
            or memory.body != expected_memory.body
            or memory.memory_type != expected_memory.memory_type
            or memory.tags != expected_memory.tags
            or memory.confidence != expected_memory.confidence
            or memory.sensitivity != expected_memory.sensitivity
            or replay_report.episode.outcome != reconstructed.episode.outcome
        ):
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.MISSING_PROVENANCE,
                details={"reason": "replay_report_content_mismatch"},
                bypassable=False,
            )
        if (
            self.criteria.require_outcome
            and replay_report.episode.outcome not in self.criteria.allowed_outcomes
        ):
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.MISSING_PROVENANCE,
                details={"reason": "replay_outcome_not_admissible"},
                bypassable=False,
            )
        return self.promote_memory(
            memory, explicit_approval=explicit_approval, expected_task_id=replay_report.task_id
        )

    def promote_memory(
        self,
        memory: MemoryRecord,
        *,
        explicit_approval: bool = False,
        expected_task_id: str | None = None,
    ) -> PromotionResult:
        """Promote a memory record to the index.

        Args:
            memory: The memory record to promote
            explicit_approval: If True, allows bypass of LOW_CONFIDENCE only.
                Does NOT bypass: integrity, provenance, content bans, sensitivity, read-only.

        Returns:
            PromotionResult with status, memory, and any rejection reason

        Security guarantees:
        - read_only=True ALWAYS prevents mutation, even with explicit_approval=True
        - Integrity, provenance, content, and sensitivity checks are NEVER bypassed
        - Only min_confidence threshold can be bypassed with explicit_approval
        - Rejected operations leave the index unchanged
        """
        # Take snapshot of index state for rollback verification
        self._index_snapshot_count = len(self.index.entries)

        # CRITICAL: Read-only mode check - NEVER bypassable
        # explicit_approval does NOT allow bypassing read-only mode
        if self.read_only:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.READ_ONLY_MODE,
                details={"reason": "read_only_mode_active_no_bypass"},
                bypassable=False,
            )

        # CRITICAL: Validate provenance - NEVER bypassable
        provenance_valid, provenance_details = self._validate_provenance(
            memory, expected_task_id=expected_task_id
        )
        if not provenance_valid:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.MISSING_PROVENANCE,
                details=provenance_details,
                bypassable=False,
            )

        # CRITICAL: Validate content admissibility - NEVER bypassable
        admissibility = self._check_content_admissibility(memory)
        if not admissibility["admissible"]:
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.INADMISSIBLE_CONTENT,
                details=admissibility,
                bypassable=False,
            )

        # Detect repeated promotions across repeated replays and new promoter
        # instances sharing an index. The content digest excludes generated IDs.
        promotion_hash = self.compute_promotion_hash(memory)
        if memory.memory_id in self._promoted_ids or any(
            entry.metadata.get("memory_id") == memory.memory_id
            or entry.metadata.get("promotion_hash") == promotion_hash
            for entry in self.index.entries
        ):
            return PromotionResult(
                status=PromotionStatus.DUPLICATE,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.DUPLICATE,
                details={"reason": "memory_already_promoted"},
                bypassable=False,
            )

        # CRITICAL: Check sensitivity - NEVER bypassable
        if _sensitivity_exceeds_limit(memory.sensitivity, self.criteria.max_sensitivity):
            return PromotionResult(
                status=PromotionStatus.REJECTED,
                memory=memory,
                index_entry=None,
                rejection_reason=RejectionReason.SENSITIVE_CONTENT,
                details={
                    "sensitivity": memory.sensitivity.value,
                    "max_allowed": self.criteria.max_sensitivity.value,
                },
                bypassable=False,
            )

        # BYPASSABLE: Check confidence threshold
        # explicit_approval allows bypassing this check only
        if memory.confidence < self.criteria.min_confidence:
            if not explicit_approval:
                return PromotionResult(
                    status=PromotionStatus.DEFERRED,
                    memory=memory,
                    index_entry=None,
                    rejection_reason=RejectionReason.LOW_CONFIDENCE,
                    details={
                        "confidence": memory.confidence,
                        "threshold": self.criteria.min_confidence,
                    },
                    bypassable=True,
                )
            # explicit_approval allows proceeding despite low confidence
            # Log this for audit purposes
            details_low_conf = {
                "confidence": memory.confidence,
                "threshold": self.criteria.min_confidence,
                "bypassed_with_approval": True,
            }
        else:
            details_low_conf = {}

        # Build index entry
        index_entry = self._build_index_entry(memory)

        # Add to index (in-memory, not persisted unless explicitly saved)
        self.index.add_entry(index_entry)
        self._promoted_ids.add(memory.memory_id)

        result = PromotionResult(
            status=PromotionStatus.PROMOTED,
            memory=memory,
            index_entry=index_entry,
            details={
                "index_entry_id": index_entry.entry_id,
                "source_event_count": len(memory.source_event_ids),
                **details_low_conf,
            },
            bypassable=False,  # Promotion succeeded, no bypass involved
        )
        self._promotion_history.append(result)
        return result

    def _validate_provenance(
        self, memory: MemoryRecord, *, expected_task_id: str | None = None
    ) -> tuple[bool, dict[str, Any]]:
        """Fail closed unless the complete source set belongs to one verified task.

        MemoryRecord has no task_id; promote_from_replay supplies the trusted
        expected task explicitly, while direct promotion enforces a single task.
        """
        if self.spine is None:
            return False, {"reason": "spine_required_not_provided"}
        if not memory.source_event_ids:
            return False, {"reason": "empty_source_event_ids"}
        if len(memory.source_event_ids) != len(set(memory.source_event_ids)):
            return False, {"reason": "duplicate_source_event_ids"}

        integrity = self.spine.verify_integrity()
        if not integrity.ok:
            return False, {
                "reason": "spine_integrity_verification_failed",
                "integrity_reason": integrity.reason,
            }

        events = self.spine.events
        event_map = {event.event_id: event for event in events}
        if len(event_map) != len(events):
            return False, {"reason": "duplicate_spine_event_ids"}
        source_ids = set(memory.source_event_ids)
        missing = source_ids - event_map.keys()
        if missing:
            return False, {
                "reason": "source_events_not_in_spine",
                "missing_event_ids": sorted(missing)[:10],
                "total_missing": len(missing),
                "source_event_ids_provided": len(source_ids),
                "events_in_spine": len(events),
            }

        task_ids = {event_map[event_id].task_id for event_id in source_ids}
        if len(task_ids) != 1 or not next(iter(task_ids), ""):
            return False, {
                "reason": "source_events_mixed_tasks",
                "task_count": len(task_ids),
            }
        source_task_id = next(iter(task_ids))
        if expected_task_id is not None and source_task_id != expected_task_id:
            return False, {
                "reason": "source_task_id_mismatch",
                "expected_task_id": expected_task_id,
                "source_task_id": source_task_id,
            }
        # A valid hash chain proves history consistency, not arithmetic truth.
        # Math-tagged source episodes must be rechecked by the actual ExactMathCell
        # before any memory index mutation, including checkpoint restore.
        task_events = self.spine.events_for_task(source_task_id)
        if any(e.event_type == "math.exact_verified" for e in task_events):
            from hex_cortex.memory.cortex_verified_math_memory import verify_math_fact_task

            if not verify_math_fact_task(self.spine, source_task_id):
                return False, {"reason": "math_fact_source_not_verified"}
        return True, {
            "provenance_validated": True,
            "source_event_count": len(memory.source_event_ids),
            "source_task_id": source_task_id,
            "spine_integrity_ok": True,
        }

    def _check_content_admissibility(self, memory: MemoryRecord) -> dict[str, Any]:
        """Check if memory content is admissible for promotion.

        This check is NEVER bypassable, even with explicit_approval.

        Args:
            memory: The memory record to check

        Returns:
            Dict with admissible bool and details
        """
        issues: list[str] = []
        blocked_found: list[str] = []

        # Check for blocked tags
        mandatory_blocked_tags = {"secret", "credential", "password", "token", "api_key"}
        blocked_tags = mandatory_blocked_tags | {
            tag.casefold() for tag in self.criteria.blocked_tags
        }
        for tag in memory.tags:
            if tag.casefold() in blocked_tags:
                blocked_found.append(tag)

        # Check title and body for sensitive patterns
        sensitive_patterns = [
            "password",
            "secret",
            "credential",
            "api_key",
            "token",
            "private_key",
            "access_token",
            "refresh_token",
        ]

        searchable_text = f"{memory.title} {memory.body}".lower()
        for pattern in sensitive_patterns:
            if pattern in searchable_text:
                issues.append(f"sensitive_pattern:{pattern}")

        # Check for raw outputs that should not be persisted
        if "raw_output" in searchable_text or "unredacted" in searchable_text:
            issues.append("raw_output_detected")

        # Check for untrusted instructions without verification markers
        if "instruction" in searchable_text and "verified" not in searchable_text:
            if memory.memory_type == MemoryType.DECISION_RULE:
                issues.append("unverified_instruction_in_rule")

        admissible = len(issues) == 0 and len(blocked_found) == 0

        return {
            "admissible": admissible,
            "issues": issues,
            "blocked_tags_found": blocked_found,
        }

    def _build_index_entry(self, memory: MemoryRecord) -> IndexEntry:
        """Build an index entry from a memory record."""
        # Build searchable text from memory
        searchable_parts = [memory.title, memory.body]

        # Add rule claims if present
        if "tacit-rule" in memory.tags:
            # Extract rule claims from body
            for line in memory.body.split("\n"):
                if line.startswith("Rule:"):
                    searchable_parts.append(line)

        searchable_text = "\n".join(searchable_parts)

        # Build metadata for audit trail
        metadata: dict[str, Any] = {
            "memory_id": memory.memory_id,
            "memory_type": memory.memory_type.value,
            "sensitivity": memory.sensitivity.value,
            "confidence": memory.confidence,
            "source_event_count": len(memory.source_event_ids),
            "source_event_ids": list(memory.source_event_ids),
            "promotion_hash": self.compute_promotion_hash(memory),
            "promoted_at": "pending_persistence",  # Will be updated on save
        }

        if memory.supersedes_memory_ids:
            metadata["supersedes"] = memory.supersedes_memory_ids

        # Build path for index entry (virtual path, not filesystem)
        path = f"memory://{memory.memory_type.value}/{memory.memory_id}"

        return IndexEntry(
            path=path,
            title=memory.title,
            text=searchable_text,
            tags=[*memory.tags, "promoted"],
            metadata=metadata,
        )

    def get_promotion_history(self) -> list[PromotionResult]:
        """Get the history of all promotion attempts."""
        return list(self._promotion_history)

    def get_promoted_ids(self) -> set[str]:
        """Get the set of promoted memory IDs."""
        return set(self._promoted_ids)

    def compute_promotion_hash(self, memory: MemoryRecord) -> str:
        """Compute a hash for duplicate detection across sessions."""
        # Generated memory IDs must not affect deduplication. Include the
        # semantic classification so distinct memory types are not conflated.
        content = json.dumps(
            {
                "title": memory.title,
                "body": memory.body,
                "source_event_ids": sorted(memory.source_event_ids),
                "tags": sorted(memory.tags),
                "memory_type": memory.memory_type.value,
                "sensitivity": memory.sensitivity.value,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def verify_index_unchanged(self) -> bool:
        """Verify that the index was not modified since the last operation.

        Returns:
            True if index entry count matches the snapshot taken before last operation
        """
        if self._index_snapshot_count is None:
            return True  # No snapshot to compare against
        return len(self.index.entries) == self._index_snapshot_count


class PersistenceNotImplementedError(Exception):
    """Raised when persistence is requested but not implemented."""

    pass


@dataclass
class PromotionSession:
    """A session for managing memory promotion with persistence.

    This class wraps MemoryPromoter with JSONL persistence support.

    Security: If persist=True is requested but persistence is not properly
    configured, the operation is REFUSED rather than silently succeeding.
    """

    promoter: MemoryPromoter
    spine_store: CanonicalSpineJsonlStore | None
    promotion_log_path: str | None
    _persistence_implemented: bool = False  # Set to True when fully implemented

    def promote_and_log(
        self,
        replay_report: ReplayReport,
        *,
        explicit_approval: bool = False,
        persist: bool = False,
    ) -> PromotionResult:
        """Promote a memory and log the promotion.

        Args:
            replay_report: The replay report to promote from
            explicit_approval: Operator override flag (only bypasses LOW_CONFIDENCE)
            persist: If True, persist to JSONL after promotion

        Returns:
            PromotionResult with the promotion outcome

        Security guarantees:
        - If persist=True but persistence is not implemented, raises PersistenceNotImplementedError
        - Does NOT silently succeed when persistence is requested but unavailable
        - Read-only mode is enforced by the underlying promoter
        """
        # Persistence is not implemented. A caller must not be able to toggle
        # _persistence_implemented and cause index mutation before a failed write.
        if persist:
            raise PersistenceNotImplementedError(
                "persist=True requested but persistence is not implemented. "
                "Set _persistence_implemented=True only after implementing _log_promotion."
            )

        # Also refuse if required components are missing
        if persist and (self.promotion_log_path is None or self.spine_store is None):
            raise PersistenceNotImplementedError(
                "persist=True requested but required components are not configured. "
                "Set spine_store and promotion_log_path before using persist=True."
            )

        result = self.promoter.promote_from_replay(
            replay_report, explicit_approval=explicit_approval
        )

        if result.status == PromotionStatus.PROMOTED and persist:
            # Log promotion to JSONL
            self._log_promotion(result)

        return result

    def _log_promotion(self, result: PromotionResult) -> None:
        """Log a promotion event to JSONL.

        Note: This is a placeholder. Full implementation requires:
        - atomic_jsonl_snapshot with proper hash chain
        - Integration with CanonicalSpine for audit trail
        - Proper error handling and rollback

        Until fully implemented, _persistence_implemented must remain False,
        which will cause promote_and_log(persist=True) to raise an error.
        """
        if self.promotion_log_path is None or self.spine_store is None:
            # This should not be reached due to checks in promote_and_log
            raise PersistenceNotImplementedError(
                "_log_promotion called without required configuration"
            )

        # Placeholder: In a full implementation, this would:
        # 1. Create a proper spine event for the promotion
        # 2. Use atomic_jsonl_snapshot to append with hash chain verification
        # 3. Handle concurrent writes and crash recovery
        # 4. Return success/failure status

        # For now, raise an error to indicate this is not implemented
        raise PersistenceNotImplementedError(
            "_log_promotion is a placeholder. Full implementation required before use."
        )