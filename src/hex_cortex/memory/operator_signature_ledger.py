"""Append-only operator signature ledger records."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.review_audit_bundle import (
    REVIEW_AUDIT_BUNDLE_FILENAME,
    ReviewAuditBundleJsonlStore,
)

OPERATOR_SIGNATURE_LEDGER_FILENAME = "operator-signature-ledger.jsonl"


class OperatorSignatureLedgerRecord(BaseModel):
    """One persisted operator signature ledger record."""

    ledger_id: str = Field(default_factory=lambda: f"operator_ledger_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_bundle_id: str | None
    source_bundle_hash: str | None
    previous_ledger_hash: str | None
    ledger_hash: str
    bundle_decision: str | None
    bundle_complete: bool
    ledger_status: str
    ledger_decision: str
    ledger_allowed: bool
    signature_scope: str
    next_action: str
    reasons: list[str]


class OperatorSignatureLedgerSummary(BaseModel):
    """Summary of persisted operator signature ledger records."""

    inspect_type: str = "operator_signature_ledger"
    path: str
    exists: bool
    total_ledger_count: int = Field(ge=0)
    latest_ledger_id: str | None
    latest_selected_skill: str | None
    latest_ledger_status: str | None
    latest_ledger_decision: str | None
    latest_ledger_allowed: bool | None
    latest_signature_scope: str | None
    latest_next_action: str | None
    latest_ledger_hash: str | None


class OperatorSignatureLedgerJsonlStore:
    """Persist operator signature ledger records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorSignatureLedgerRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(
                        OperatorSignatureLedgerRecord.model_validate_json(line)
                    )
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid operator signature ledger at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[OperatorSignatureLedgerRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorSignatureLedgerRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_operator_signature_ledger(profile: Path) -> dict[str, object]:
    """Build and append one operator signature ledger record."""

    bundles = ReviewAuditBundleJsonlStore(
        profile / REVIEW_AUDIT_BUNDLE_FILENAME
    ).load()
    ledger_path = profile / OPERATOR_SIGNATURE_LEDGER_FILENAME
    previous = OperatorSignatureLedgerJsonlStore(ledger_path).load()
    previous_hash = previous[-1].ledger_hash if previous else None
    if not bundles:
        record = _missing_bundle_ledger(profile, previous_hash)
    else:
        record = _ledger_from_bundle(profile, bundles[-1], previous_hash)
    count = OperatorSignatureLedgerJsonlStore(ledger_path).append(record)
    return {
        "ledger_type": "operator_signature_ledger",
        "profile_path": str(profile),
        "ledger_path": str(ledger_path),
        "ledger_count": count,
        "ledger_record": record.model_dump(mode="json"),
    }


def summarize_operator_signature_ledgers(path: Path) -> dict[str, object]:
    records = OperatorSignatureLedgerJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = OperatorSignatureLedgerSummary(
        path=str(path),
        exists=path.exists(),
        total_ledger_count=len(records),
        latest_ledger_id=latest.ledger_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_ledger_status=latest.ledger_status if latest else None,
        latest_ledger_decision=latest.ledger_decision if latest else None,
        latest_ledger_allowed=latest.ledger_allowed if latest else None,
        latest_signature_scope=latest.signature_scope if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_ledger_hash=latest.ledger_hash if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_bundle_ledger(
    profile: Path,
    previous_hash: str | None,
) -> OperatorSignatureLedgerRecord:
    payload = _hash_payload(
        selected_skill="review_bundle_missing",
        source_bundle_id=None,
        source_bundle_hash=None,
        previous_ledger_hash=previous_hash,
        bundle_decision=None,
        ledger_decision="ledger_blocked",
        signature_scope="none",
    )
    return OperatorSignatureLedgerRecord(
        profile_path=str(profile),
        selected_skill="review_bundle_missing",
        source_bundle_id=None,
        source_bundle_hash=None,
        previous_ledger_hash=previous_hash,
        ledger_hash=_sha256(payload),
        bundle_decision=None,
        bundle_complete=False,
        ledger_status="blocked",
        ledger_decision="ledger_blocked",
        ledger_allowed=False,
        signature_scope="none",
        next_action="build_review_audit_bundle",
        reasons=["review_audit_bundle_missing"],
    )


def _ledger_from_bundle(
    profile: Path,
    bundle,
    previous_hash: str | None,
) -> OperatorSignatureLedgerRecord:
    status, decision, allowed, scope, next_action, reasons = _ledger_decision(bundle)
    payload = _hash_payload(
        selected_skill=bundle.selected_skill,
        source_bundle_id=bundle.bundle_id,
        source_bundle_hash=bundle.bundle_hash,
        previous_ledger_hash=previous_hash,
        bundle_decision=bundle.bundle_decision,
        ledger_decision=decision,
        signature_scope=scope,
    )
    return OperatorSignatureLedgerRecord(
        profile_path=str(profile),
        selected_skill=bundle.selected_skill,
        source_bundle_id=bundle.bundle_id,
        source_bundle_hash=bundle.bundle_hash,
        previous_ledger_hash=previous_hash,
        ledger_hash=_sha256(payload),
        bundle_decision=bundle.bundle_decision,
        bundle_complete=bundle.bundle_complete,
        ledger_status=status,
        ledger_decision=decision,
        ledger_allowed=allowed,
        signature_scope=scope,
        next_action=next_action,
        reasons=reasons,
    )


def _ledger_decision(bundle):
    if bundle.bundle_decision == "bundle_ready" and bundle.bundle_complete:
        return (
            "ready",
            "ledger_ready",
            True,
            "operator_signed_review_bundle",
            "prepare_review_closeout_report",
            ["bundle_ready_for_operator_ledger"],
        )
    if bundle.bundle_decision == "bundle_watch" and bundle.bundle_complete:
        return (
            "watch",
            "ledger_watch",
            False,
            "operator_watch_review_bundle",
            bundle.next_action,
            ["bundle_waiting_for_operator", *bundle.reasons],
        )
    return (
        "blocked",
        "ledger_blocked",
        False,
        "none",
        bundle.next_action,
        ["bundle_not_ledger_ready", *bundle.reasons],
    )


def _hash_payload(
    *,
    selected_skill: str,
    source_bundle_id: str | None,
    source_bundle_hash: str | None,
    previous_ledger_hash: str | None,
    bundle_decision: str | None,
    ledger_decision: str,
    signature_scope: str,
) -> str:
    return "|".join(
        [
            selected_skill,
            source_bundle_id or "none",
            source_bundle_hash or "none",
            previous_ledger_hash or "none",
            bundle_decision or "none",
            ledger_decision,
            signature_scope,
        ]
    )


def _sha256(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
