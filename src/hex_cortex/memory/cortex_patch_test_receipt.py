from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_PATCH_TEST_RECEIPT_FILENAME = "cortex-patch-test-receipt.jsonl"


class CortexPatchTestReceiptRecord(BaseModel):
    receipt_id: str = Field(default_factory=lambda: f"cortex_patch_test_receipt_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    test_status: str
    pytest_summary: str
    passed_count: int = Field(ge=0)
    source_artifact_hash: str | None = None
    receipt_status: str
    receipt_decision: str
    receipt_allowed: bool
    next_action: str
    blockers: list[str]
    receipt_hash: str
    reasons: list[str]


class CortexPatchTestReceiptJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexPatchTestReceiptRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexPatchTestReceiptRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex patch test receipt {line_number}") from exc
        return records

    def save(self, records: list[CortexPatchTestReceiptRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_patch_test_receipt(
    profile: Path,
    *,
    test_status: str,
    pytest_summary: str,
    passed_count: int,
    source_artifact_hash: str | None = None,
) -> dict[str, object]:
    record = _receipt_record(
        profile,
        test_status=test_status,
        pytest_summary=pytest_summary,
        passed_count=passed_count,
        source_artifact_hash=source_artifact_hash,
    )
    path = profile / CORTEX_PATCH_TEST_RECEIPT_FILENAME
    store = CortexPatchTestReceiptJsonlStore(path)
    current = store.load()
    count = store.save([*current, record])
    return {
        "receipt_type": "cortex_patch_test_receipt",
        "profile_path": str(profile),
        "receipt_path": str(path),
        "receipt_count": count,
        "receipt_records": [record.model_dump(mode="json")],
    }


def summarize_cortex_patch_test_receipts(path: Path) -> dict[str, object]:
    records = CortexPatchTestReceiptJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.receipt_allowed]
    return {
        "inspect_type": "cortex_patch_test_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_receipt_count": len(records),
        "allowed_receipt_count": len(allowed),
        "latest_receipt_id": latest.receipt_id if latest else None,
        "latest_receipt_status": latest.receipt_status if latest else None,
        "latest_receipt_decision": latest.receipt_decision if latest else None,
        "latest_receipt_allowed": latest.receipt_allowed if latest else None,
        "latest_passed_count": latest.passed_count if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_receipt_hash": latest.receipt_hash if latest else None,
    }


def _receipt_record(
    profile: Path,
    *,
    test_status: str,
    pytest_summary: str,
    passed_count: int,
    source_artifact_hash: str | None,
) -> CortexPatchTestReceiptRecord:
    blockers = _receipt_blockers(test_status, passed_count)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "patch_test_receipt_ready" if allowed else "patch_test_receipt_blocked"
    next_action = "backpropagate_hypothesis_tree" if allowed else "repair_patch_test_result"
    reasons = ["tests_passed", "patch_test_receipt_ready"] if allowed else blockers
    receipt_hash = _hash(str(profile), test_status, pytest_summary, str(passed_count), source_artifact_hash or "no_artifact", decision, next_action, *reasons)
    return CortexPatchTestReceiptRecord(
        profile_path=str(profile),
        test_status=test_status,
        pytest_summary=pytest_summary,
        passed_count=passed_count,
        source_artifact_hash=source_artifact_hash,
        receipt_status=status,
        receipt_decision=decision,
        receipt_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        receipt_hash=receipt_hash,
        reasons=reasons,
    )


def _receipt_blockers(test_status: str, passed_count: int) -> list[str]:
    blockers = []
    if test_status != "passed":
        blockers.append("tests_not_passed")
    if passed_count <= 0:
        blockers.append("missing_passed_count")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
