"""Operator-facing export packs for the review path."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.review_archive_index import (
    REVIEW_ARCHIVE_INDEX_FILENAME,
    ReviewArchiveIndexJsonlStore,
)
from hex_cortex.memory.review_closeout_report import (
    REVIEW_CLOSEOUT_REPORT_FILENAME,
    ReviewCloseoutReportJsonlStore,
)
from hex_cortex.memory.review_proof import REVIEW_PROOF_FILENAME, ReviewProofJsonlStore

REVIEW_EXPORT_PACK_FILENAME = "review-export-pack.jsonl"


class ReviewExportPackRecord(BaseModel):
    """One persisted operator-facing review export pack."""

    export_id: str = Field(default_factory=lambda: f"review_export_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_closeout_id: str | None
    source_index_id: str | None
    source_proof_id: str | None
    closeout_decision: str | None
    index_decision: str | None
    proof_decision: str | None
    pack_status: str
    pack_decision: str
    pack_complete: bool
    pack_hash: str
    operator_summary: dict[str, object]
    next_action: str
    reasons: list[str]


class ReviewExportPackSummary(BaseModel):
    """Summary of persisted review export packs."""

    inspect_type: str = "review_export_pack"
    path: str
    exists: bool
    total_pack_count: int = Field(ge=0)
    latest_export_id: str | None
    latest_selected_skill: str | None
    latest_pack_status: str | None
    latest_pack_decision: str | None
    latest_pack_complete: bool | None
    latest_next_action: str | None
    latest_pack_hash: str | None


class ReviewExportPackJsonlStore:
    """Persist review export packs as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewExportPackRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReviewExportPackRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review export pack at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewExportPackRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewExportPackRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_export_pack(profile: Path) -> dict[str, object]:
    """Build one operator-facing review export pack."""

    closeouts = ReviewCloseoutReportJsonlStore(
        profile / REVIEW_CLOSEOUT_REPORT_FILENAME
    ).load()
    indexes = ReviewArchiveIndexJsonlStore(
        profile / REVIEW_ARCHIVE_INDEX_FILENAME
    ).load()
    proofs = ReviewProofJsonlStore(profile / REVIEW_PROOF_FILENAME).load()
    record = _pack_from_sources(
        profile,
        closeouts[-1] if closeouts else None,
        indexes[-1] if indexes else None,
        proofs[-1] if proofs else None,
    )
    path = profile / REVIEW_EXPORT_PACK_FILENAME
    count = ReviewExportPackJsonlStore(path).append(record)
    return {
        "pack_type": "review_export_pack",
        "profile_path": str(profile),
        "pack_path": str(path),
        "pack_count": count,
        "pack_record": record.model_dump(mode="json"),
    }


def summarize_review_export_packs(path: Path) -> dict[str, object]:
    records = ReviewExportPackJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewExportPackSummary(
        path=str(path),
        exists=path.exists(),
        total_pack_count=len(records),
        latest_export_id=latest.export_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_pack_status=latest.pack_status if latest else None,
        latest_pack_decision=latest.pack_decision if latest else None,
        latest_pack_complete=latest.pack_complete if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_pack_hash=latest.pack_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _pack_from_sources(
    profile: Path,
    closeout,
    index,
    proof,
) -> ReviewExportPackRecord:
    selected_skill = _selected_skill(closeout, index, proof)
    complete = bool(closeout and index and proof)
    status, decision, next_action, reasons = _pack_decision(closeout, index, proof)
    summary = _operator_summary(selected_skill, closeout, index, proof)
    return ReviewExportPackRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_closeout_id=closeout.closeout_id if closeout else None,
        source_index_id=index.index_id if index else None,
        source_proof_id=proof.proof_id if proof else None,
        closeout_decision=closeout.closeout_decision if closeout else None,
        index_decision=index.index_decision if index else None,
        proof_decision=proof.proof_decision if proof else None,
        pack_status=status,
        pack_decision=decision,
        pack_complete=complete,
        pack_hash=_pack_hash(closeout, index, proof),
        operator_summary=summary,
        next_action=next_action,
        reasons=reasons,
    )


def _selected_skill(closeout, index, proof) -> str:
    if proof:
        return proof.selected_skill
    if index:
        return index.selected_skill
    if closeout:
        return closeout.selected_skill
    return "review_export_sources_missing"


def _pack_decision(closeout, index, proof):
    if not closeout or not index or not proof:
        return (
            "blocked",
            "pack_blocked",
            "build_missing_review_records",
            ["review_export_sources_missing"],
        )
    if proof.proof_decision == "proof_ready" and index.index_decision == "index_ready":
        return (
            "ready",
            "pack_ready",
            "build_construction_status_report",
            ["review_export_pack_ready"],
        )
    if proof.proof_decision == "proof_watch" or index.index_decision == "index_watch":
        return (
            "watch",
            "pack_watch",
            proof.next_action,
            ["review_export_pack_waiting", *proof.reasons],
        )
    return (
        "blocked",
        "pack_blocked",
        proof.next_action,
        ["review_export_pack_blocked", *proof.reasons],
    )


def _operator_summary(
    selected_skill: str,
    closeout,
    index,
    proof,
) -> dict[str, object]:
    return {
        "selected_skill": selected_skill,
        "closeout_decision": closeout.closeout_decision if closeout else None,
        "index_decision": index.index_decision if index else None,
        "proof_decision": proof.proof_decision if proof else None,
        "final_state": closeout.final_state if closeout else None,
        "operator_next_action": proof.next_action if proof else None,
        "closeout_hashes": closeout.evidence_hashes if closeout else [],
        "index_hash": index.index_hash if index else None,
        "proof_hash": proof.proof_hash if proof else None,
    }


def _pack_hash(closeout, index, proof) -> str:
    parts = [
        closeout.closeout_id if closeout else "missing_closeout",
        index.index_id if index else "missing_index",
        proof.proof_id if proof else "missing_proof",
        proof.proof_hash if proof else "missing_proof_hash",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
