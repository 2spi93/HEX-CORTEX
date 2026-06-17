"""Dry-run registry review decisions without applying changes."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.registry_review_signature_packet import (
    REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME,
    RegistryReviewSignaturePacketJsonlStore,
)
from hex_cortex.memory.skill_registry_review_document import (
    SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME,
    SkillRegistryReviewDocumentJsonlStore,
)

REGISTRY_REVIEW_DRY_RUN_FILENAME = "registry-review-dry-run.jsonl"


class RegistryReviewDryRunRecord(BaseModel):
    """One persisted dry-run record for registry review."""

    dry_run_id: str = Field(default_factory=lambda: f"registry_dry_run_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_signature_id: str | None
    source_document_id: str | None
    signer: str | None
    signature_decision: str | None
    signature_allowed: bool
    document_decision: str | None
    registry_action: str | None
    document_hash: str | None
    dry_run_status: str
    dry_run_decision: str
    dry_run_allowed: bool
    proposed_operation: str
    proposed_record: dict[str, object]
    next_action: str
    reasons: list[str]


class RegistryReviewDryRunSummary(BaseModel):
    """Summary of persisted registry review dry runs."""

    inspect_type: str = "registry_review_dry_run"
    path: str
    exists: bool
    total_dry_run_count: int = Field(ge=0)
    latest_dry_run_id: str | None
    latest_selected_skill: str | None
    latest_dry_run_status: str | None
    latest_dry_run_decision: str | None
    latest_dry_run_allowed: bool | None
    latest_proposed_operation: str | None
    latest_next_action: str | None


class RegistryReviewDryRunJsonlStore:
    """Persist registry review dry runs as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[RegistryReviewDryRunRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(RegistryReviewDryRunRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid registry review dry run at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[RegistryReviewDryRunRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: RegistryReviewDryRunRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_registry_review_dry_run(profile: Path) -> dict[str, object]:
    """Build a dry-run record from the latest review signature packet."""

    signatures = RegistryReviewSignaturePacketJsonlStore(
        profile / REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME
    ).load()
    documents = SkillRegistryReviewDocumentJsonlStore(
        profile / SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME
    ).load()
    if not signatures:
        record = _missing_signature_dry_run(profile, documents[-1] if documents else None)
    else:
        record = _dry_run_from_sources(
            profile,
            signatures[-1],
            documents[-1] if documents else None,
        )
    path = profile / REGISTRY_REVIEW_DRY_RUN_FILENAME
    count = RegistryReviewDryRunJsonlStore(path).append(record)
    return {
        "dry_run_type": "registry_review_dry_run",
        "profile_path": str(profile),
        "dry_run_path": str(path),
        "dry_run_count": count,
        "dry_run_record": record.model_dump(mode="json"),
    }


def summarize_registry_review_dry_runs(path: Path) -> dict[str, object]:
    records = RegistryReviewDryRunJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = RegistryReviewDryRunSummary(
        path=str(path),
        exists=path.exists(),
        total_dry_run_count=len(records),
        latest_dry_run_id=latest.dry_run_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_dry_run_status=latest.dry_run_status if latest else None,
        latest_dry_run_decision=latest.dry_run_decision if latest else None,
        latest_dry_run_allowed=latest.dry_run_allowed if latest else None,
        latest_proposed_operation=latest.proposed_operation if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_signature_dry_run(profile: Path, document) -> RegistryReviewDryRunRecord:
    selected_skill = document.selected_skill if document else "review_signature_missing"
    return RegistryReviewDryRunRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_signature_id=None,
        source_document_id=document.document_id if document else None,
        signer=None,
        signature_decision=None,
        signature_allowed=False,
        document_decision=document.document_decision if document else None,
        registry_action=document.registry_action if document else None,
        document_hash=None,
        dry_run_status="blocked",
        dry_run_decision="dry_run_blocked",
        dry_run_allowed=False,
        proposed_operation="none",
        proposed_record={},
        next_action="build_registry_review_signature_packet",
        reasons=["registry_review_signature_packet_missing"],
    )


def _dry_run_from_sources(profile: Path, signature, document) -> RegistryReviewDryRunRecord:
    if signature.signature_allowed and signature.signature_decision == "signature_signed":
        return _signed_dry_run(profile, signature, document)
    if signature.signature_decision == "signature_needs_more_evidence":
        return _watch_dry_run(profile, signature, document)
    return _blocked_dry_run(profile, signature, document)


def _signed_dry_run(profile: Path, signature, document) -> RegistryReviewDryRunRecord:
    proposed_operation = _operation_from_document(document)
    return RegistryReviewDryRunRecord(
        profile_path=str(profile),
        selected_skill=signature.selected_skill,
        source_signature_id=signature.signature_id,
        source_document_id=signature.source_document_id,
        signer=signature.signer,
        signature_decision=signature.signature_decision,
        signature_allowed=signature.signature_allowed,
        document_decision=signature.document_decision,
        registry_action=signature.registry_action,
        document_hash=signature.document_hash,
        dry_run_status="ready",
        dry_run_decision="dry_run_ready",
        dry_run_allowed=True,
        proposed_operation=proposed_operation,
        proposed_record=_proposed_record(signature, document, proposed_operation),
        next_action="prepare_registry_activation_artifact",
        reasons=["signed_review_ready_for_dry_run"],
    )


def _watch_dry_run(profile: Path, signature, document) -> RegistryReviewDryRunRecord:
    return RegistryReviewDryRunRecord(
        profile_path=str(profile),
        selected_skill=signature.selected_skill,
        source_signature_id=signature.signature_id,
        source_document_id=signature.source_document_id,
        signer=signature.signer,
        signature_decision=signature.signature_decision,
        signature_allowed=signature.signature_allowed,
        document_decision=signature.document_decision,
        registry_action=signature.registry_action,
        document_hash=signature.document_hash,
        dry_run_status="watch",
        dry_run_decision="dry_run_watch",
        dry_run_allowed=False,
        proposed_operation="none",
        proposed_record=_proposed_record(signature, document, "none"),
        next_action=signature.next_action,
        reasons=["signature_requires_more_evidence", *signature.reasons],
    )


def _blocked_dry_run(profile: Path, signature, document) -> RegistryReviewDryRunRecord:
    return RegistryReviewDryRunRecord(
        profile_path=str(profile),
        selected_skill=signature.selected_skill,
        source_signature_id=signature.signature_id,
        source_document_id=signature.source_document_id,
        signer=signature.signer,
        signature_decision=signature.signature_decision,
        signature_allowed=signature.signature_allowed,
        document_decision=signature.document_decision,
        registry_action=signature.registry_action,
        document_hash=signature.document_hash,
        dry_run_status="blocked",
        dry_run_decision="dry_run_blocked",
        dry_run_allowed=False,
        proposed_operation="none",
        proposed_record=_proposed_record(signature, document, "none"),
        next_action="repair_registry_review_signature_packet",
        reasons=["signature_not_usable_for_dry_run", *signature.reasons],
    )


def _operation_from_document(document) -> str:
    if not document:
        return "review_without_document"
    if document.registry_action == "manual_activation_review":
        return "skill_activation_review"
    if document.registry_action == "confidence_review_only":
        return "skill_confidence_review"
    return "operator_review_only"


def _proposed_record(signature, document, operation: str) -> dict[str, object]:
    return {
        "operation": operation,
        "selected_skill": signature.selected_skill,
        "document_id": signature.source_document_id,
        "document_hash": signature.document_hash,
        "signer": signature.signer,
        "document_decision": signature.document_decision,
        "registry_action": signature.registry_action,
        "evidence_lines": document.evidence_lines if document else [],
    }
