"""Review activation artifacts built from registry review simulations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.registry_review_dry_run import (
    REGISTRY_REVIEW_DRY_RUN_FILENAME,
    RegistryReviewDryRunJsonlStore,
)

REVIEW_ACTIVATION_ARTIFACT_FILENAME = "review-activation-artifact.jsonl"


class ReviewActivationArtifactRecord(BaseModel):
    """One persisted activation review artifact."""

    artifact_id: str = Field(default_factory=lambda: f"review_artifact_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_dry_run_id: str | None
    source_document_id: str | None
    document_hash: str | None
    dry_run_decision: str | None
    dry_run_allowed: bool
    proposed_operation: str | None
    artifact_status: str
    artifact_decision: str
    artifact_allowed: bool
    artifact_kind: str
    artifact_payload: dict[str, object]
    next_action: str
    reasons: list[str]


class ReviewActivationArtifactSummary(BaseModel):
    """Summary of persisted activation review artifacts."""

    inspect_type: str = "review_activation_artifact"
    path: str
    exists: bool
    total_artifact_count: int = Field(ge=0)
    latest_artifact_id: str | None
    latest_selected_skill: str | None
    latest_artifact_status: str | None
    latest_artifact_decision: str | None
    latest_artifact_allowed: bool | None
    latest_artifact_kind: str | None
    latest_next_action: str | None


class ReviewActivationArtifactJsonlStore:
    """Persist activation review artifacts as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewActivationArtifactRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ReviewActivationArtifactRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review activation artifact at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewActivationArtifactRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewActivationArtifactRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_activation_artifact(profile: Path) -> dict[str, object]:
    """Build a review artifact from the latest registry review simulation."""

    dry_runs = RegistryReviewDryRunJsonlStore(
        profile / REGISTRY_REVIEW_DRY_RUN_FILENAME
    ).load()
    if not dry_runs:
        record = _missing_dry_run_artifact(profile)
    else:
        record = _artifact_from_dry_run(profile, dry_runs[-1])
    path = profile / REVIEW_ACTIVATION_ARTIFACT_FILENAME
    count = ReviewActivationArtifactJsonlStore(path).append(record)
    return {
        "artifact_type": "review_activation_artifact",
        "profile_path": str(profile),
        "artifact_path": str(path),
        "artifact_count": count,
        "artifact_record": record.model_dump(mode="json"),
    }


def summarize_review_activation_artifacts(path: Path) -> dict[str, object]:
    records = ReviewActivationArtifactJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewActivationArtifactSummary(
        path=str(path),
        exists=path.exists(),
        total_artifact_count=len(records),
        latest_artifact_id=latest.artifact_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_artifact_status=latest.artifact_status if latest else None,
        latest_artifact_decision=latest.artifact_decision if latest else None,
        latest_artifact_allowed=latest.artifact_allowed if latest else None,
        latest_artifact_kind=latest.artifact_kind if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_dry_run_artifact(profile: Path) -> ReviewActivationArtifactRecord:
    return ReviewActivationArtifactRecord(
        profile_path=str(profile),
        selected_skill="review_dry_run_missing",
        source_dry_run_id=None,
        source_document_id=None,
        document_hash=None,
        dry_run_decision=None,
        dry_run_allowed=False,
        proposed_operation=None,
        artifact_status="blocked",
        artifact_decision="artifact_blocked",
        artifact_allowed=False,
        artifact_kind="none",
        artifact_payload={},
        next_action="build_registry_review_dry_run",
        reasons=["registry_review_dry_run_missing"],
    )


def _artifact_from_dry_run(profile: Path, dry_run) -> ReviewActivationArtifactRecord:
    if not dry_run.dry_run_allowed:
        return _watch_artifact(profile, dry_run)
    return _ready_artifact(profile, dry_run)


def _watch_artifact(profile: Path, dry_run) -> ReviewActivationArtifactRecord:
    return ReviewActivationArtifactRecord(
        profile_path=str(profile),
        selected_skill=dry_run.selected_skill,
        source_dry_run_id=dry_run.dry_run_id,
        source_document_id=dry_run.source_document_id,
        document_hash=dry_run.document_hash,
        dry_run_decision=dry_run.dry_run_decision,
        dry_run_allowed=dry_run.dry_run_allowed,
        proposed_operation=dry_run.proposed_operation,
        artifact_status="watch",
        artifact_decision="artifact_watch",
        artifact_allowed=False,
        artifact_kind="manual_review_required",
        artifact_payload={
            "selected_skill": dry_run.selected_skill,
            "required_action": dry_run.next_action,
            "reason": "dry_run_not_allowed",
            "document_hash": dry_run.document_hash,
        },
        next_action=dry_run.next_action,
        reasons=["dry_run_not_allowed", *dry_run.reasons],
    )


def _ready_artifact(profile: Path, dry_run) -> ReviewActivationArtifactRecord:
    return ReviewActivationArtifactRecord(
        profile_path=str(profile),
        selected_skill=dry_run.selected_skill,
        source_dry_run_id=dry_run.dry_run_id,
        source_document_id=dry_run.source_document_id,
        document_hash=dry_run.document_hash,
        dry_run_decision=dry_run.dry_run_decision,
        dry_run_allowed=dry_run.dry_run_allowed,
        proposed_operation=dry_run.proposed_operation,
        artifact_status="ready",
        artifact_decision="artifact_ready",
        artifact_allowed=True,
        artifact_kind=dry_run.proposed_operation,
        artifact_payload={
            "selected_skill": dry_run.selected_skill,
            "operation": dry_run.proposed_operation,
            "document_hash": dry_run.document_hash,
            "source_dry_run_id": dry_run.dry_run_id,
            "proposed_record": dry_run.proposed_record,
        },
        next_action="prepare_operator_signature_ledger",
        reasons=["dry_run_allowed"],
    )
