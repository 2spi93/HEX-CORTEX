"""Compact summaries of controlled receipts."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.controlled_execution_receipt import (
    CONTROLLED_EXECUTION_RECEIPT_FILENAME,
    ControlledExecutionReceiptJsonlStore,
)

RECEIPT_SUMMARY_FILENAME = "receipt-summary.jsonl"


class ReceiptSummaryRecord(BaseModel):
    """One persisted compact receipt summary."""

    summary_id: str = Field(default_factory=lambda: f"receipt_summary_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    receipt_count: int = Field(ge=0)
    observed_count: int = Field(ge=0)
    prevented_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    latest_receipt_decision: str | None
    latest_certification: str | None
    latest_selected_skill: str | None
    summary_status: str
    summary_decision: str
    summary_score: float = Field(ge=0.0, le=1.0)
    next_action: str
    reasons: list[str]


class ReceiptSummaryInspect(BaseModel):
    """Summary of persisted receipt summaries."""

    inspect_type: str = "receipt_summary"
    path: str
    exists: bool
    total_summary_count: int = Field(ge=0)
    latest_summary_id: str | None
    latest_receipt_count: int | None
    latest_summary_status: str | None
    latest_summary_decision: str | None
    latest_summary_score: float | None
    latest_next_action: str | None


class ReceiptSummaryJsonlStore:
    """Persist receipt summaries as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ReceiptSummaryRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ReceiptSummaryRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid receipt summary at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ReceiptSummaryRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ReceiptSummaryRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_receipt_summary(profile: Path) -> dict[str, object]:
    """Build and persist a compact receipt summary."""

    receipts = ControlledExecutionReceiptJsonlStore(
        profile / CONTROLLED_EXECUTION_RECEIPT_FILENAME
    ).load()
    record = _summary_from_receipts(profile, receipts)
    path = profile / RECEIPT_SUMMARY_FILENAME
    count = ReceiptSummaryJsonlStore(path).append(record)
    return {
        "summary_type": "receipt_summary",
        "profile_path": str(profile),
        "summary_path": str(path),
        "summary_count": count,
        "summary_record": record.model_dump(mode="json"),
    }


def summarize_receipt_summaries(path: Path) -> dict[str, object]:
    records = ReceiptSummaryJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ReceiptSummaryInspect(
        path=str(path),
        exists=path.exists(),
        total_summary_count=len(records),
        latest_summary_id=latest.summary_id if latest else None,
        latest_receipt_count=latest.receipt_count if latest else None,
        latest_summary_status=latest.summary_status if latest else None,
        latest_summary_decision=latest.summary_decision if latest else None,
        latest_summary_score=latest.summary_score if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _summary_from_receipts(profile: Path, receipts) -> ReceiptSummaryRecord:
    if not receipts:
        return _missing_receipt_summary(profile)
    decisions = Counter(receipt.receipt_decision for receipt in receipts)
    certifications = Counter(receipt.certification for receipt in receipts)
    latest = receipts[-1]
    observed_count = sum(1 for receipt in receipts if receipt.execution_observed)
    prevented_count = certifications.get("execution_prevented_by_audit", 0)
    success_count = decisions.get("receipt_success", 0)
    failure_count = decisions.get("receipt_failure", 0)
    status, decision, score, next_action, reasons = _summary_decision(
        latest,
        success_count,
        failure_count,
        prevented_count,
    )
    return ReceiptSummaryRecord(
        profile_path=str(profile),
        receipt_count=len(receipts),
        observed_count=observed_count,
        prevented_count=prevented_count,
        success_count=success_count,
        failure_count=failure_count,
        latest_receipt_decision=latest.receipt_decision,
        latest_certification=latest.certification,
        latest_selected_skill=latest.selected_skill,
        summary_status=status,
        summary_decision=decision,
        summary_score=score,
        next_action=next_action,
        reasons=reasons,
    )


def _missing_receipt_summary(profile: Path) -> ReceiptSummaryRecord:
    return ReceiptSummaryRecord(
        profile_path=str(profile),
        receipt_count=0,
        observed_count=0,
        prevented_count=0,
        success_count=0,
        failure_count=0,
        latest_receipt_decision=None,
        latest_certification=None,
        latest_selected_skill=None,
        summary_status="blocked",
        summary_decision="summary_blocked",
        summary_score=0.0,
        next_action="build_controlled_execution_receipt",
        reasons=["controlled_receipts_missing"],
    )


def _summary_decision(latest, success_count: int, failure_count: int, prevented_count: int):
    if failure_count:
        return (
            "blocked",
            "summary_blocked",
            0.1,
            "repair_skill_or_gate",
            ["receipt_failure_seen"],
        )
    if success_count:
        return (
            "ready",
            "summary_ready",
            1.0,
            "prepare_operator_review_packet",
            ["receipt_success_seen"],
        )
    if prevented_count:
        return (
            "watch",
            "summary_watch",
            0.7,
            latest.next_action,
            ["receipt_prevented_by_audit"],
        )
    return (
        "watch",
        "summary_watch",
        0.5,
        "observe_skill_outcome",
        ["receipt_not_observed"],
    )
