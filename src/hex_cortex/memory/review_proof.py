"""End-to-end proof reports for the review path."""

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

REVIEW_PROOF_FILENAME = "review-proof.jsonl"


class ReviewProofRecord(BaseModel):
    """One persisted end-to-end proof report."""

    proof_id: str = Field(default_factory=lambda: f"review_proof_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_bundle_id: str | None
    source_ledger_id: str | None
    source_closeout_id: str | None
    bundle_hash: str | None
    ledger_hash: str | None
    closeout_hash: str
    proof_hash: str
    proof_status: str
    proof_decision: str
    proof_complete: bool
    next_action: str
    reasons: list[str]


class ReviewProofSummary(BaseModel):
    """Summary of persisted review proof reports."""

    inspect_type: str = "review_proof"
    path: str
    exists: bool
    total_proof_count: int = Field(ge=0)
    latest_proof_id: str | None
    latest_selected_skill: str | None
    latest_proof_status: str | None
    latest_proof_decision: str | None
    latest_proof_complete: bool | None
    latest_next_action: str | None
    latest_proof_hash: str | None


class ReviewProofJsonlStore:
    """Persist review proof reports as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewProofRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReviewProofRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review proof at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewProofRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewProofRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_proof(profile: Path) -> dict[str, object]:
    """Build one review proof report."""

    bundles = ReviewAuditBundleJsonlStore(profile / REVIEW_AUDIT_BUNDLE_FILENAME).load()
    ledgers = OperatorSignatureLedgerJsonlStore(
        profile / OPERATOR_SIGNATURE_LEDGER_FILENAME
    ).load()
    closeouts = ReviewCloseoutReportJsonlStore(
        profile / REVIEW_CLOSEOUT_REPORT_FILENAME
    ).load()
    record = _proof_from_sources(
        profile,
        bundles[-1] if bundles else None,
        ledgers[-1] if ledgers else None,
        closeouts[-1] if closeouts else None,
    )
    path = profile / REVIEW_PROOF_FILENAME
    count = ReviewProofJsonlStore(path).append(record)
    return {
        "proof_type": "review_proof",
        "profile_path": str(profile),
        "proof_path": str(path),
        "proof_count": count,
        "proof_record": record.model_dump(mode="json"),
    }


def summarize_review_proofs(path: Path) -> dict[str, object]:
    records = ReviewProofJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewProofSummary(
        path=str(path),
        exists=path.exists(),
        total_proof_count=len(records),
        latest_proof_id=latest.proof_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_proof_status=latest.proof_status if latest else None,
        latest_proof_decision=latest.proof_decision if latest else None,
        latest_proof_complete=latest.proof_complete if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_proof_hash=latest.proof_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _proof_from_sources(profile: Path, bundle, ledger, closeout) -> ReviewProofRecord:
    selected_skill = _selected_skill(bundle, ledger, closeout)
    closeout_hash = _closeout_hash(closeout)
    status, decision, complete, next_action, reasons = _proof_decision(
        bundle,
        ledger,
        closeout,
    )
    proof_hash = _proof_hash(bundle, ledger, closeout, closeout_hash)
    return ReviewProofRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_bundle_id=bundle.bundle_id if bundle else None,
        source_ledger_id=ledger.ledger_id if ledger else None,
        source_closeout_id=closeout.closeout_id if closeout else None,
        bundle_hash=bundle.bundle_hash if bundle else None,
        ledger_hash=ledger.ledger_hash if ledger else None,
        closeout_hash=closeout_hash,
        proof_hash=proof_hash,
        proof_status=status,
        proof_decision=decision,
        proof_complete=complete,
        next_action=next_action,
        reasons=reasons,
    )


def _selected_skill(bundle, ledger, closeout) -> str:
    if closeout:
        return closeout.selected_skill
    if ledger:
        return ledger.selected_skill
    if bundle:
        return bundle.selected_skill
    return "review_proof_sources_missing"


def _proof_decision(bundle, ledger, closeout):
    complete = bool(bundle and ledger and closeout)
    if not complete:
        return (
            "blocked",
            "proof_blocked",
            False,
            "build_missing_review_records",
            ["review_proof_sources_missing"],
        )
    if closeout.closeout_decision == "closeout_ready":
        return (
            "ready",
            "proof_ready",
            True,
            "prepare_review_archive_export",
            ["review_proof_ready"],
        )
    if closeout.closeout_decision == "closeout_watch":
        return (
            "watch",
            "proof_watch",
            True,
            closeout.operator_next_action,
            ["review_proof_waiting_for_operator", *closeout.reasons],
        )
    return (
        "blocked",
        "proof_blocked",
        True,
        closeout.operator_next_action,
        ["review_proof_blocked", *closeout.reasons],
    )


def _closeout_hash(closeout) -> str:
    if not closeout:
        return ""
    payload = "|".join(
        [
            closeout.closeout_id,
            closeout.selected_skill,
            closeout.closeout_decision,
            closeout.final_state,
            closeout.operator_next_action,
            *closeout.evidence_hashes,
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _proof_hash(bundle, ledger, closeout, closeout_hash: str) -> str:
    parts = [
        bundle.bundle_hash if bundle else "missing_bundle",
        ledger.ledger_hash if ledger else "missing_ledger",
        closeout.closeout_id if closeout else "missing_closeout",
        closeout_hash or "missing_closeout_hash",
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
