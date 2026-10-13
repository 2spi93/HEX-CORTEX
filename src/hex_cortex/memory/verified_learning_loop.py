"""Local, explicitly gated replay -> promotion -> retrieval integration.

No model call, hidden scheduling, raw model output persistence, or device action.
Only promotions produced by ReplayEngine can be recorded in a checkpoint.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from hex_cortex.memory.cortex_durable_jsonl_v7 import (
    atomic_jsonl_snapshot,
    exclusive_jsonl_writer,
)
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.memory_promotion import (
    MemoryPromoter,
    PromotionResult,
    PromotionStatus,
)
from hex_cortex.memory.retrieval_router import RetrievalRouter
from hex_cortex.memory.schemas import ContextPacket, RetrievalQuery
from hex_cortex.replay.replay_engine import ReplayEngine
from hex_cortex.replay.schemas import ReplayReport, ReplayStatus
from hex_cortex.spine.canonical_spine import CanonicalSpine


@dataclass(frozen=True)
class LearningCycleResult:
    replay: ReplayReport
    promotion: PromotionResult | None
    context: ContextPacket


class VerifiedLearningLoop:
    """An opt-in memory circuit; all other repository paths remain unchanged.

    A checkpoint is a compact manifest of task IDs and content fingerprints,
    not a serialized index or a trusted knowledge source. Loading independently
    reconstructs memory from a verified CanonicalSpine and re-applies policy.
    These fingerprints are NOT signatures against a malicious local writer.
    """

    def __init__(
        self,
        *,
        spine: CanonicalSpine,
        index: LocalKnowledgeIndex | None = None,
    ) -> None:
        self.spine = spine
        self.index = index if index is not None else LocalKnowledgeIndex()
        self._records: dict[str, dict[str, object]] = {}

    def run(
        self,
        *,
        task_id: str,
        query: RetrievalQuery,
        approve_promotion: bool = False,
        override_low_confidence: bool = False,
    ) -> LearningCycleResult:
        """Replay a task and retrieve context; index mutation requires approval."""
        report = ReplayEngine(spine=self.spine).replay_task(task_id)
        promotion: PromotionResult | None = None
        if approve_promotion and report.status == ReplayStatus.CONSOLIDATED:
            promoter = MemoryPromoter(index=self.index, spine=self.spine)
            promotion = promoter.promote_from_replay(
                report, explicit_approval=override_low_confidence
            )
            if promotion.status == PromotionStatus.PROMOTED and report.memory is not None:
                self._records[task_id] = {
                    "task_id": task_id,
                    "source_event_ids": list(report.source_event_ids),
                    "promotion_hash": promoter.compute_promotion_hash(report.memory),
                }
        packet = RetrievalRouter(self.index).retrieve(query)
        return LearningCycleResult(replay=report, promotion=promotion, context=packet)

    def run_from_harness(
        self,
        *,
        harness: object,
        task_id: str,
        query: RetrievalQuery,
        approve_promotion: bool = False,
        override_low_confidence: bool = False,
    ) -> LearningCycleResult:
        """Only accept completed receipts from the exact same verified harness."""
        if (
            getattr(harness, "spine", None) is not self.spine
            or not callable(getattr(harness, "verify_replay", None))
            or not harness.verify_replay()
            or not any(
                row.get("task_id") == task_id and row.get("status") == "complete"
                for row in getattr(harness, "receipts", [])
            )
        ):
            raise ValueError("unverified_or_incomplete_harness_task")
        return self.run(
            task_id=task_id,
            query=query,
            approve_promotion=approve_promotion,
            override_low_confidence=override_low_confidence,
        )

    @property
    def checkpoint_records(self) -> list[dict[str, object]]:
        """Redacted, copied provenance manifests for successful promotions."""
        return [dict(row) for row in self._records.values()]

    @staticmethod
    def _target(project_root: Path, relative_path: Path) -> Path:
        root = Path(project_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("project_root_must_be_directory")
        requested = root / relative_path
        if requested.is_symlink() or requested.parent.is_symlink():
            raise ValueError("checkpoint_symlink_denied")
        target = requested.resolve()
        if not target.is_relative_to(root):
            raise ValueError("checkpoint_outside_project_root")
        return target

    def save_checkpoint(
        self,
        *,
        project_root: Path,
        relative_path: Path,
        approved: bool = False,
    ) -> Path:
        """Create a new, immutable checkpoint with explicit operator approval."""
        if not approved:
            raise PermissionError("checkpoint_save_requires_explicit_approval")
        if not self.spine.verify_integrity().ok:
            raise ValueError("invalid_spine")
        events = self.spine.events
        payload = {
            "format": "hex_cortex_verified_learning_checkpoint_v1",
            "spine_tip": events[-1].event_hash if events else None,
            "spine_event_count": len(events),
            "records": self.checkpoint_records,
        }
        # Revalidate every stored task against current events before committing.
        for record in payload["records"]:
            task = str(record["task_id"])
            replay = ReplayEngine(spine=self.spine).replay_task(task)
            if (
                replay.status != ReplayStatus.CONSOLIDATED
                or replay.memory is None
                or replay.source_event_ids != record["source_event_ids"]
                or MemoryPromoter(index=LocalKnowledgeIndex(), spine=self.spine)
                .compute_promotion_hash(replay.memory) != record["promotion_hash"]
            ):
                raise ValueError("checkpoint_replay_mismatch")
        target = self._target(project_root, relative_path)
        with exclusive_jsonl_writer(target):
            if target.exists():
                raise FileExistsError("checkpoint_already_exists_use_new_filename")
            atomic_jsonl_snapshot(
                target, [json.dumps(payload, sort_keys=True, separators=(",", ":"))]
            )
        return target

    @classmethod
    def restore_checkpoint(
        cls,
        *,
        project_root: Path,
        relative_path: Path,
        spine: CanonicalSpine,
    ) -> VerifiedLearningLoop:
        """Build a fresh index atomically in memory, never trusting stored text."""
        target = cls._target(project_root, relative_path)
        if not target.is_file() or target.stat().st_size > 1_000_000:
            raise ValueError("checkpoint_missing_or_oversize")
        if not spine.verify_integrity().ok:
            raise ValueError("invalid_spine")
        with target.open("r", encoding="utf-8") as handle:
            lines = handle.readlines()
        if len(lines) != 1:
            raise ValueError("invalid_checkpoint_line_count")
        try:
            payload = json.loads(lines[0])
        except (ValueError, TypeError) as exc:
            raise ValueError("invalid_checkpoint_json") from exc
        events = spine.events
        if (
            not isinstance(payload, dict)
            or payload.get("format") != "hex_cortex_verified_learning_checkpoint_v1"
            or payload.get("spine_event_count") != len(events)
            or payload.get("spine_tip") != (events[-1].event_hash if events else None)
            or not isinstance(payload.get("records"), list)
            or len(payload["records"]) > 1024
        ):
            raise ValueError("checkpoint_spine_or_format_mismatch")
        candidate = cls(spine=spine)
        for record in payload["records"]:
            if not isinstance(record, dict) or set(record) != {
                "task_id", "source_event_ids", "promotion_hash"
            }:
                raise ValueError("invalid_checkpoint_record")
            task = record["task_id"]
            if (
                not isinstance(task, str)
                or not task.strip()
                or task in candidate._records
                or not isinstance(record["source_event_ids"], list)
                or not isinstance(record["promotion_hash"], str)
            ):
                raise ValueError("invalid_or_duplicate_checkpoint_task")
            replay = ReplayEngine(spine=spine).replay_task(task)
            if (
                replay.status != ReplayStatus.CONSOLIDATED
                or replay.memory is None
                or replay.source_event_ids != record["source_event_ids"]
            ):
                raise ValueError("checkpoint_provenance_mismatch")
            promoter = MemoryPromoter(index=candidate.index, spine=spine)
            if promoter.compute_promotion_hash(replay.memory) != record["promotion_hash"]:
                raise ValueError("checkpoint_content_mismatch")
            outcome = promoter.promote_from_replay(replay)
            if outcome.status != PromotionStatus.PROMOTED:
                raise ValueError("checkpoint_promotion_policy_rejected")
            candidate._records[task] = {
                "task_id": task,
                "source_event_ids": list(replay.source_event_ids),
                "promotion_hash": record["promotion_hash"],
            }
        return candidate
