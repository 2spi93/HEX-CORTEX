"""Archive indexes for the operator review path."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.operator_signature_ledger import (
    OPERATOR_SIGNATURE_LEDGER_FILENAME,
    OperatorSignatureLedgerJsonlStore,
)
from hex_cortex.memory.review_audit_bundle import (
    REVIEW_AUDIT_BUNDLE_FILENAME,
    ReviewAuditBundleJsonlStore,
)
from hex_cortex.memory.review_closeout_report import (
    REVIEW_CLOSEOUT_REPORT_FILENAME,
    ReviewCloseoutReportJsonlStore,
)
from hex_cortex.memory.skill_registry_review_document import (
    SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME,
    SkillRegistryReviewDocumentJsonlStore,
)

REVIEW_ARCHIVE_INDEX_FILENAME = "review-archive-index.jsonl"


class ReviewArchiveIndexRecord(BaseModel):
    """One persisted index for review records."""

    index_id: str = Field(default_factory=lambda: f"review_index_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_document_id: str | None
    source_bundle_id: str | None
    source_ledger_id: str | None
    source_closeout_id: str | None
    latest_document_decision: str | None
    latest_bundle_decision: str | None
    latest_ledger_decision: str | None
    latest_closeout_decision: str | None
    index_status: str
    index_decision: str
    index_complete: bool
    index_hash: str
    indexed_records: dict[str, str | None]
    next_action: str
    reasons: list[str]


class ReviewArchiveIndexSummary(BaseModel):
    """Summary of persisted review archive indexes."""

    inspect_type: str = "review_archive_index"
    path: str
    exists: bool
    total_index_count: int = Field(ge=0)
    latest_index_id: str | None
    latest_selected_skill: str | None
    latest_index_status: str | None
    latest_index_decision: str | None
    latest_index_complete: bool | None
    latest_next_action: str | None
    latest_index_hash: str | None


class ReviewArchiveIndexJsonlStore:
    """Persist archive indexes as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewArchiveIndexRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ReviewArchiveIndexRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review archive index at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewArchiveIndexRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewArchiveIndexRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_archive_index(profile: Path) -> dict[str, object]:
    """Build a local archive index for latest review records."""

    documents = SkillRegistryReviewDocumentJsonlStore(
        profile / SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME
    ).load()
    bundles = ReviewAuditBundleJsonlStore(
        profile / REVIEW_AUDIT_BUNDLE_FILENAME
    ).load()
    ledgers = OperatorSignatureLedgerJsonlStore(
        profile / OPERATOR_SIGNATURE_LEDGER_FILENAME
    ).load()
    closeouts = ReviewCloseoutReportJsonlStore(
        profile / REVIEW_CLOSEOUT_REPORT_FILENAME
    ).load()
    record = _index_from_sources(
        profile,
        documents[-1] if documents else None,
        bundles[-1] if bundles else None,
        ledgers[-1] if ledgers else None,
        closeouts[-1] if closeouts else None,
    )
    path = profile / REVIEW_ARCHIVE_INDEX_FILENAME
    count = ReviewArchiveIndexJsonlStore(path).append(record)
    return {
        "index_type": "review_archive_index",
        "profile_path": str(profile),
        "index_path": str(path),
        "index_count": count,
        "index_record": record.model_dump(mode="json"),
    }


def summarize_review_archive_indexes(path: Path) -> dict[str, object]:
    records = ReviewArchiveIndexJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewArchiveIndexSummary(
        path=str(path),
        exists=path.exists(),
        total_index_count=len(records),
        latest_index_id=latest.index_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_index_status=latest.index_status if latest else None,
        latest_index_decision=latest.index_decision if latest else None,
        latest_index_complete=latest.index_complete if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_index_hash=latest.index_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _index_from_sources(
    profile: Path,
    document,
    bundle,
    ledger,
    closeout,
) -> ReviewArchiveIndexRecord:
    selected_skill = _selected_skill(document, bundle, ledger, closeout)
    indexed_records = {
        "document_id": document.document_id if document else None,
        "bundle_id": bundle.bundle_id if bundle else None,
        "ledger_id": ledger.ledger_id if ledger else None,
        "closeout_id": closeout.closeout_id if closeout else None,
    }
    complete = all(indexed_records.values())
    status, decision, next_action, reasons = _index_decision(complete, closeout)
    return ReviewArchiveIndexRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_document_id=indexed_records["document_id"],
        source_bundle_id=indexed_records["bundle_id"],
        source_ledger_id=indexed_records["ledger_id"],
        source_closeout_id=indexed_records["closeout_id"],
        latest_document_decision=document.document_decision if document else None,
        latest_bundle_decision=bundle.bundle_decision if bundle else None,
        latest_ledger_decision=ledger.ledger_decision if ledger else None,
        latest_closeout_decision=closeout.closeout_decision if closeout else None,
        index_status=status,
        index_decision=decision,
        index_complete=complete,
        index_hash=_index_hash(indexed_records),
        indexed_records=indexed_records,
        next_action=next_action,
        reasons=reasons,
    )


def _selected_skill(document, bundle, ledger, closeout) -> str:
    if closeout:
        return closeout.selected_skill
    if ledger:
        return ledger.selected_skill
    if bundle:
        return bundle.selected_skill
    if document:
        return document.selected_skill
    return "review_archive_sources_missing"


def _index_decision(complete: bool, closeout):
    if not complete:
        return (
            "blocked",
            "index_blocked",
            "build_missing_review_records",
            ["review_archive_sources_missing"],
        )
    if closeout and closeout.closeout_decision == "closeout_ready":
        return (
            "ready",
            "index_ready",
            "build_end_to_end_review_proof",
            ["review_archive_index_ready"],
        )
    return (
        "watch",
        "index_watch",
        closeout.operator_next_action if closeout else "inspect_review_archive",
        ["review_archive_index_waiting"],
    )


def _index_hash(indexed_records: dict[str, str | None]) -> str:
    digest = hashlib.sha256()
    parts = [
        f"{key}={value or 'none'}"
        for key, value in sorted(indexed_records.items())
    ]
    digest.update("|".join(parts).encode("utf-8"))
    return digest.hexdigest()
