"""Closeout reports for the operator review path."""

from __future__ import annotations

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

REVIEW_CLOSEOUT_REPORT_FILENAME = "review-closeout-report.jsonl"


class ReviewCloseoutReportRecord(BaseModel):
    """One persisted operator review closeout report."""

    closeout_id: str = Field(default_factory=lambda: f"review_closeout_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_ledger_id: str | None
    source_ledger_hash: str | None
    source_bundle_id: str | None
    source_bundle_hash: str | None
    ledger_decision: str | None
    bundle_decision: str | None
    closeout_status: str
    closeout_decision: str
    closeout_complete: bool
    final_state: str
    operator_next_action: str
    evidence_hashes: list[str]
    reasons: list[str]


class ReviewCloseoutReportSummary(BaseModel):
    """Summary of persisted operator review closeout reports."""

    inspect_type: str = "review_closeout_report"
    path: str
    exists: bool
    total_closeout_count: int = Field(ge=0)
    latest_closeout_id: str | None
    latest_selected_skill: str | None
    latest_closeout_status: str | None
    latest_closeout_decision: str | None
    latest_closeout_complete: bool | None
    latest_final_state: str | None
    latest_operator_next_action: str | None


class ReviewCloseoutReportJsonlStore:
    """Persist closeout reports as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReviewCloseoutReportRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        ReviewCloseoutReportRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid review closeout report at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReviewCloseoutReportRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReviewCloseoutReportRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_review_closeout_report(profile: Path) -> dict[str, object]:
    """Build one closeout report from the latest ledger and bundle."""

    ledgers = OperatorSignatureLedgerJsonlStore(
        profile / OPERATOR_SIGNATURE_LEDGER_FILENAME
    ).load()
    bundles = ReviewAuditBundleJsonlStore(
        profile / REVIEW_AUDIT_BUNDLE_FILENAME
    ).load()
    record = _closeout_from_sources(
        profile,
        ledgers[-1] if ledgers else None,
        bundles[-1] if bundles else None,
    )
    path = profile / REVIEW_CLOSEOUT_REPORT_FILENAME
    count = ReviewCloseoutReportJsonlStore(path).append(record)
    return {
        "closeout_type": "review_closeout_report",
        "profile_path": str(profile),
        "closeout_path": str(path),
        "closeout_count": count,
        "closeout_record": record.model_dump(mode="json"),
    }


def summarize_review_closeout_reports(path: Path) -> dict[str, object]:
    records = ReviewCloseoutReportJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReviewCloseoutReportSummary(
        path=str(path),
        exists=path.exists(),
        total_closeout_count=len(records),
        latest_closeout_id=latest.closeout_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_closeout_status=latest.closeout_status if latest else None,
        latest_closeout_decision=latest.closeout_decision if latest else None,
        latest_closeout_complete=latest.closeout_complete if latest else None,
        latest_final_state=latest.final_state if latest else None,
        latest_operator_next_action=latest.operator_next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _closeout_from_sources(profile: Path, ledger, bundle) -> ReviewCloseoutReportRecord:
    if not ledger:
        return _missing_ledger_closeout(profile, bundle)
    status, decision, complete, final_state, next_action, reasons = _closeout_decision(
        ledger,
        bundle,
    )
    return ReviewCloseoutReportRecord(
        profile_path=str(profile),
        selected_skill=ledger.selected_skill,
        source_ledger_id=ledger.ledger_id,
        source_ledger_hash=ledger.ledger_hash,
        source_bundle_id=ledger.source_bundle_id,
        source_bundle_hash=ledger.source_bundle_hash,
        ledger_decision=ledger.ledger_decision,
        bundle_decision=bundle.bundle_decision if bundle else ledger.bundle_decision,
        closeout_status=status,
        closeout_decision=decision,
        closeout_complete=complete,
        final_state=final_state,
        operator_next_action=next_action,
        evidence_hashes=_evidence_hashes(ledger, bundle),
        reasons=reasons,
    )


def _missing_ledger_closeout(profile: Path, bundle) -> ReviewCloseoutReportRecord:
    selected_skill = bundle.selected_skill if bundle else "operator_ledger_missing"
    return ReviewCloseoutReportRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_ledger_id=None,
        source_ledger_hash=None,
        source_bundle_id=bundle.bundle_id if bundle else None,
        source_bundle_hash=bundle.bundle_hash if bundle else None,
        ledger_decision=None,
        bundle_decision=bundle.bundle_decision if bundle else None,
        closeout_status="blocked",
        closeout_decision="closeout_blocked",
        closeout_complete=False,
        final_state="missing_operator_ledger",
        operator_next_action="build_operator_signature_ledger",
        evidence_hashes=[bundle.bundle_hash] if bundle else [],
        reasons=["operator_signature_ledger_missing"],
    )


def _closeout_decision(ledger, bundle):
    if ledger.ledger_decision == "ledger_ready" and ledger.ledger_allowed:
        return (
            "ready",
            "closeout_ready",
            True,
            "operator_review_ready_for_archive",
            "build_review_archive_index",
            ["ledger_ready_for_closeout"],
        )
    if ledger.ledger_decision == "ledger_watch":
        return (
            "watch",
            "closeout_watch",
            True,
            "operator_review_waiting_for_manual_step",
            ledger.next_action,
            ["ledger_watch", *ledger.reasons],
        )
    return (
        "blocked",
        "closeout_blocked",
        bool(bundle),
        "operator_review_blocked",
        ledger.next_action,
        ["ledger_blocked", *ledger.reasons],
    )


def _evidence_hashes(ledger, bundle) -> list[str]:
    hashes = [ledger.ledger_hash]
    if ledger.source_bundle_hash:
        hashes.append(ledger.source_bundle_hash)
    if bundle and bundle.document_hash:
        hashes.append(bundle.document_hash)
    return hashes
