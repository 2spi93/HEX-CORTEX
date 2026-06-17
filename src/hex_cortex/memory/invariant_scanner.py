"""Invariant scanner for HEX-CORTEX review state."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.construction_freeze_stamp import (
    CONSTRUCTION_FREEZE_STAMP_FILENAME,
    ConstructionFreezeStampJsonlStore,
)
from hex_cortex.memory.construction_status_report import (
    CONSTRUCTION_STATUS_REPORT_FILENAME,
    ConstructionStatusReportJsonlStore,
)
from hex_cortex.memory.review_export_pack import (
    REVIEW_EXPORT_PACK_FILENAME,
    ReviewExportPackJsonlStore,
)
from hex_cortex.memory.review_proof import REVIEW_PROOF_FILENAME, ReviewProofJsonlStore

INVARIANT_SCAN_FILENAME = "invariant-scan.jsonl"


class InvariantScanRecord(BaseModel):
    """One persisted invariant scan."""

    scan_id: str = Field(default_factory=lambda: f"invariant_scan_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    invariant_status: str
    invariant_decision: str
    violation_count: int = Field(ge=0)
    violations: list[str]
    next_action: str


class InvariantScanJsonlStore:
    """Persist invariant scans as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[InvariantScanRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(InvariantScanRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid invariant scan at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[InvariantScanRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: InvariantScanRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def scan_profile_invariants(profile: Path) -> dict[str, object]:
    """Scan profile-level review invariants."""

    statuses = ConstructionStatusReportJsonlStore(
        profile / CONSTRUCTION_STATUS_REPORT_FILENAME
    ).load()
    freezes = ConstructionFreezeStampJsonlStore(
        profile / CONSTRUCTION_FREEZE_STAMP_FILENAME
    ).load()
    packs = ReviewExportPackJsonlStore(profile / REVIEW_EXPORT_PACK_FILENAME).load()
    proofs = ReviewProofJsonlStore(profile / REVIEW_PROOF_FILENAME).load()
    status = statuses[-1] if statuses else None
    freeze = freezes[-1] if freezes else None
    pack = packs[-1] if packs else None
    proof = proofs[-1] if proofs else None
    violations = _violations(status, freeze, pack, proof)
    selected_skill = _selected_skill(status, freeze, pack, proof)
    record = InvariantScanRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        invariant_status="ready" if not violations else "blocked",
        invariant_decision="invariants_ok" if not violations else "invariants_failed",
        violation_count=len(violations),
        violations=violations,
        next_action="continue" if not violations else "repair_invariants",
    )
    path = profile / INVARIANT_SCAN_FILENAME
    count = InvariantScanJsonlStore(path).append(record)
    return {
        "scan_type": "invariant_scan",
        "profile_path": str(profile),
        "scan_path": str(path),
        "scan_count": count,
        "scan_record": record.model_dump(mode="json"),
    }


def _selected_skill(status, freeze, pack, proof) -> str:
    for record in (status, freeze, pack, proof):
        if record and record.selected_skill:
            return record.selected_skill
    return "invariant_sources_missing"


def _violations(status, freeze, pack, proof) -> list[str]:
    violations: list[str] = []
    if freeze and freeze.freeze_allowed and not freeze.construction_complete:
        violations.append("freeze_allowed_without_construction_complete")
    if status and status.construction_decision == "construction_ready":
        if status.blocker_count != 0:
            violations.append("construction_ready_with_blockers")
    if pack and proof:
        if pack.pack_decision == "pack_ready" and proof.proof_decision != "proof_ready":
            violations.append("pack_ready_without_proof_ready")
    if freeze and status:
        if (
            freeze.freeze_decision == "freeze_ready"
            and status.construction_decision != "construction_ready"
        ):
            violations.append("freeze_ready_without_construction_ready")
    return violations
