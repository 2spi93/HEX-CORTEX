"""Signature packets for skill registry review documents."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.skill_registry_review_document import (
    SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME,
    SkillRegistryReviewDocumentJsonlStore,
)

REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME = "registry-review-signature-packet.jsonl"
ALLOWED_SIGNATURE_DECISIONS = {
    "auto",
    "signed",
    "rejected",
    "deferred",
    "needs_more_evidence",
}


class RegistryReviewSignaturePacketRecord(BaseModel):
    """One persisted review signature packet."""

    signature_id: str = Field(default_factory=lambda: f"review_signature_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_document_id: str | None
    selected_skill: str
    signer: str
    requested_signature: str
    document_decision: str | None
    document_status: str | None
    registry_action: str | None
    document_hash: str
    signature_status: str
    signature_decision: str
    signature_allowed: bool
    next_action: str
    reasons: list[str]


class RegistryReviewSignaturePacketSummary(BaseModel):
    """Summary of persisted review signature packets."""

    inspect_type: str = "registry_review_signature_packet"
    path: str
    exists: bool
    total_signature_count: int = Field(ge=0)
    latest_signature_id: str | None
    latest_selected_skill: str | None
    latest_signer: str | None
    latest_signature_status: str | None
    latest_signature_decision: str | None
    latest_signature_allowed: bool | None
    latest_next_action: str | None


class RegistryReviewSignaturePacketJsonlStore:
    """Persist registry review signature packets as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[RegistryReviewSignaturePacketRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        RegistryReviewSignaturePacketRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        "invalid registry review signature packet "
                        f"at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[RegistryReviewSignaturePacketRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: RegistryReviewSignaturePacketRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_registry_review_signature_packet(
    profile: Path,
    *,
    signer: str = "operator_local",
    requested_signature: str = "auto",
) -> dict[str, object]:
    """Build a signature packet from the latest registry review document."""

    if requested_signature not in ALLOWED_SIGNATURE_DECISIONS:
        raise ValueError(
            f"unsupported review signature decision: {requested_signature}"
        )
    documents = SkillRegistryReviewDocumentJsonlStore(
        profile / SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME
    ).load()
    if not documents:
        record = _missing_document_signature(profile, signer, requested_signature)
    else:
        record = _signature_from_document(
            profile,
            documents[-1],
            signer,
            requested_signature,
        )
    path = profile / REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME
    count = RegistryReviewSignaturePacketJsonlStore(path).append(record)
    return {
        "signature_type": "registry_review_signature_packet",
        "profile_path": str(profile),
        "signature_path": str(path),
        "signature_count": count,
        "signature_record": record.model_dump(mode="json"),
    }


def summarize_registry_review_signature_packets(path: Path) -> dict[str, object]:
    records = RegistryReviewSignaturePacketJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = RegistryReviewSignaturePacketSummary(
        path=str(path),
        exists=path.exists(),
        total_signature_count=len(records),
        latest_signature_id=latest.signature_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_signer=latest.signer if latest else None,
        latest_signature_status=latest.signature_status if latest else None,
        latest_signature_decision=latest.signature_decision if latest else None,
        latest_signature_allowed=latest.signature_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_document_signature(
    profile: Path,
    signer: str,
    requested_signature: str,
) -> RegistryReviewSignaturePacketRecord:
    return RegistryReviewSignaturePacketRecord(
        profile_path=str(profile),
        source_document_id=None,
        selected_skill="skill_registry_review_document_missing",
        signer=signer,
        requested_signature=requested_signature,
        document_decision=None,
        document_status=None,
        registry_action=None,
        document_hash="",
        signature_status="blocked",
        signature_decision="signature_blocked",
        signature_allowed=False,
        next_action="build_skill_registry_review_document",
        reasons=["skill_registry_review_document_missing"],
    )


def _signature_from_document(
    profile: Path,
    document,
    signer: str,
    requested_signature: str,
) -> RegistryReviewSignaturePacketRecord:
    effective = _effective_signature(document, requested_signature)
    status, decision, allowed, next_action, reasons = _signature_decision(
        document,
        effective,
    )
    return RegistryReviewSignaturePacketRecord(
        profile_path=str(profile),
        source_document_id=document.document_id,
        selected_skill=document.selected_skill,
        signer=signer,
        requested_signature=effective,
        document_decision=document.document_decision,
        document_status=document.document_status,
        registry_action=document.registry_action,
        document_hash=_document_hash(document),
        signature_status=status,
        signature_decision=decision,
        signature_allowed=allowed,
        next_action=next_action,
        reasons=reasons,
    )


def _effective_signature(document, requested_signature: str) -> str:
    if requested_signature != "auto":
        return requested_signature
    if document.document_decision == "document_ready":
        return "signed"
    if document.document_decision == "document_needs_registry_activation":
        return "needs_more_evidence"
    if document.document_decision == "document_deferred":
        return "deferred"
    return "rejected"


def _signature_decision(document, effective: str):
    if effective == "signed" and document.document_decision == "document_ready":
        return (
            "ready",
            "signature_signed",
            True,
            "prepare_registry_review_dry_run",
            ["operator_signature_ready"],
        )
    if effective == "needs_more_evidence":
        return (
            "watch",
            "signature_needs_more_evidence",
            False,
            document.next_action,
            ["signature_requires_more_evidence"],
        )
    if effective == "deferred":
        return (
            "watch",
            "signature_deferred",
            False,
            document.next_action,
            ["operator_signature_deferred"],
        )
    return (
        "blocked",
        "signature_rejected",
        False,
        "repair_registry_review_document",
        ["operator_signature_rejected_or_blocked"],
    )


def _document_hash(document) -> str:
    digest = hashlib.sha256()
    fields = [
        document.document_id,
        document.selected_skill,
        document.document_decision,
        document.registry_action,
        document.next_action,
        *document.evidence_lines,
    ]
    digest.update("|".join(fields).encode("utf-8"))
    return digest.hexdigest()
