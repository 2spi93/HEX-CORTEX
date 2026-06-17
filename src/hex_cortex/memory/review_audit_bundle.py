"""Audit bundles for review artifacts and signatures."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.registry_review_dry_run import (
    REGISTRY_REVIEW_DRY_RUN_FILENAME,
    RegistryReviewDryRunJsonlStore,
)
from hex_cortex.memory.registry_review_signature_packet import (
    REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME,
    RegistryReviewSignaturePacketJsonlStore,
)
from hex_cortex.memory.review_activation_artifact import (
    REVIEW_ACTIVATION_ARTIFACT_FILENAME,
    ReviewActivationArtifactJsonlStore,
)

REVIEW_AUDIT_BUNDLE_FILENAME = "review-audit-bundle.jsonl"


class ReviewAuditBundleRecord(BaseModel):
    """One persisted audit bundle for the review path."""

    bundle_id: str = Field(default_factory=lambda: f"review_bundle_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_signature_id: str | None
    source_dry_run_id: str | None
    source_artifact_id: str | None
    signature_decision: str | None
    dry_run_decision: str | None
    artifact_decision: str | None
    document_hash: str | None
    bundle_hash: str
    bundle_status: str
    bundle_decision: str
    bundle_complete: bool
    next_action: str
    reasons: list[str]


class ReviewAuditBundleSummary(BaseModel):
    """Summary of persisted audit bundles."""

    inspect_type: str = "review_audit_bundle"
    path: str
    exists: bool
    total_bundle_count: int = Field(ge=0)
    latest_bundle_id: str | None
    latest_selected_skill: str | None
    latest_bundle_status: str | None
    latest_bundle_decision: str | None
    latest_bundle_complete: bool | None
    latest_next_action: str | None


class ReviewAuditBundleJsonlStore:
    """Persist audit bundles as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewAuditBundleRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReviewAuditBundleRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review audit bundle at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewAuditBundleRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewAuditBundleRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_audit_bundle(profile: Path) -> dict[str, object]:
    """Build an audit bundle from latest review path records."""

    signatures = RegistryReviewSignaturePacketJsonlStore(
        profile / REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME
    ).load()
    dry_runs = RegistryReviewDryRunJsonlStore(
        profile / REGISTRY_REVIEW_DRY_RUN_FILENAME
    ).load()
    artifacts = ReviewActivationArtifactJsonlStore(
        profile / REVIEW_ACTIVATION_ARTIFACT_FILENAME
    ).load()
    record = _bundle_from_sources(
        profile,
        signatures[-1] if signatures else None,
        dry_runs[-1] if dry_runs else None,
        artifacts[-1] if artifacts else None,
    )
    path = profile / REVIEW_AUDIT_BUNDLE_FILENAME
    count = ReviewAuditBundleJsonlStore(path).append(record)
    return {
        "bundle_type": "review_audit_bundle",
        "profile_path": str(profile),
        "bundle_path": str(path),
        "bundle_count": count,
        "bundle_record": record.model_dump(mode="json"),
    }


def summarize_review_audit_bundles(path: Path) -> dict[str, object]:
    records = ReviewAuditBundleJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewAuditBundleSummary(
        path=str(path),
        exists=path.exists(),
        total_bundle_count=len(records),
        latest_bundle_id=latest.bundle_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_bundle_status=latest.bundle_status if latest else None,
        latest_bundle_decision=latest.bundle_decision if latest else None,
        latest_bundle_complete=latest.bundle_complete if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _bundle_from_sources(profile: Path, signature, dry_run, artifact) -> ReviewAuditBundleRecord:
    selected_skill = _selected_skill(signature, dry_run, artifact)
    status, decision, complete, next_action, reasons = _bundle_decision(
        signature,
        dry_run,
        artifact,
    )
    return ReviewAuditBundleRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_signature_id=signature.signature_id if signature else None,
        source_dry_run_id=dry_run.dry_run_id if dry_run else None,
        source_artifact_id=artifact.artifact_id if artifact else None,
        signature_decision=signature.signature_decision if signature else None,
        dry_run_decision=dry_run.dry_run_decision if dry_run else None,
        artifact_decision=artifact.artifact_decision if artifact else None,
        document_hash=_document_hash(signature, dry_run, artifact),
        bundle_hash=_bundle_hash(signature, dry_run, artifact),
        bundle_status=status,
        bundle_decision=decision,
        bundle_complete=complete,
        next_action=next_action,
        reasons=reasons,
    )


def _selected_skill(signature, dry_run, artifact) -> str:
    if artifact:
        return artifact.selected_skill
    if dry_run:
        return dry_run.selected_skill
    if signature:
        return signature.selected_skill
    return "review_sources_missing"


def _document_hash(signature, dry_run, artifact) -> str | None:
    if artifact and artifact.document_hash:
        return artifact.document_hash
    if dry_run and dry_run.document_hash:
        return dry_run.document_hash
    if signature and signature.document_hash:
        return signature.document_hash
    return None


def _bundle_decision(signature, dry_run, artifact):
    if not signature or not dry_run or not artifact:
        return (
            "blocked",
            "bundle_blocked",
            False,
            "build_missing_review_sources",
            ["review_bundle_sources_missing"],
        )
    if artifact.artifact_decision == "artifact_ready" and artifact.artifact_allowed:
        return (
            "ready",
            "bundle_ready",
            True,
            "prepare_operator_signature_ledger",
            ["review_bundle_ready"],
        )
    if artifact.artifact_decision == "artifact_watch":
        return (
            "watch",
            "bundle_watch",
            True,
            artifact.next_action,
            ["review_bundle_waiting_for_operator", *artifact.reasons],
        )
    return (
        "blocked",
        "bundle_blocked",
        True,
        artifact.next_action,
        ["review_bundle_blocked", *artifact.reasons],
    )


def _bundle_hash(signature, dry_run, artifact) -> str:
    digest = hashlib.sha256()
    parts = [
        signature.signature_id if signature else "missing_signature",
        dry_run.dry_run_id if dry_run else "missing_dry_run",
        artifact.artifact_id if artifact else "missing_artifact",
        _document_hash(signature, dry_run, artifact) or "missing_document_hash",
    ]
    digest.update("|".join(parts).encode("utf-8"))
    return digest.hexdigest()
