from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_branch_build_packet import (
    CORTEX_BRANCH_BUILD_PACKET_FILENAME,
    CortexBranchBuildPacketJsonlStore,
    CortexBranchBuildPacketRecord,
)

CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME = "cortex-packet-acknowledgement.jsonl"
REQUIRED_PACKET_ACK = "ACK_PACKET_READY"


class CortexPacketAcknowledgementRecord(BaseModel):
    ack_id: str = Field(default_factory=lambda: f"cortex_packet_acknowledgement_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_packet_id: str | None
    source_packet_hash: str | None
    source_review_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    ack_required: str
    ack_received: str | None
    ack_status: str
    ack_decision: str
    ack_allowed: bool
    next_action: str
    blockers: list[str]
    ack_hash: str
    reasons: list[str]


class CortexPacketAcknowledgementJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexPacketAcknowledgementRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexPacketAcknowledgementRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex packet acknowledgement {line_number}") from exc
        return records

    def save(self, records: list[CortexPacketAcknowledgementRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_packet_acknowledgement(profile: Path, ack: str | None = None) -> dict[str, object]:
    packet = _latest_packet(profile)
    record = _ack_record(profile, packet, ack)
    path = profile / CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME
    store = CortexPacketAcknowledgementJsonlStore(path)
    current = store.load()
    records = [record]
    count = store.save([*current, *records])
    return {
        "ack_type": "cortex_packet_acknowledgement",
        "profile_path": str(profile),
        "ack_path": str(path),
        "ack_count": count,
        "ack_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_packet_acknowledgements(path: Path) -> dict[str, object]:
    records = CortexPacketAcknowledgementJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.ack_allowed]
    return {
        "inspect_type": "cortex_packet_acknowledgement",
        "path": str(path),
        "exists": path.exists(),
        "total_ack_count": len(records),
        "allowed_ack_count": len(allowed),
        "latest_ack_id": latest.ack_id if latest else None,
        "latest_ack_status": latest.ack_status if latest else None,
        "latest_ack_decision": latest.ack_decision if latest else None,
        "latest_ack_allowed": latest.ack_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_ack_hash": latest.ack_hash if latest else None,
    }


def _latest_packet(profile: Path) -> CortexBranchBuildPacketRecord | None:
    records = CortexBranchBuildPacketJsonlStore(profile / CORTEX_BRANCH_BUILD_PACKET_FILENAME).load()
    return records[-1] if records else None


def _ack_record(
    profile: Path,
    packet: CortexBranchBuildPacketRecord | None,
    ack: str | None,
) -> CortexPacketAcknowledgementRecord:
    blockers = _ack_blockers(packet, ack)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "packet_acknowledgement_ready" if allowed else "packet_acknowledgement_blocked"
    next_action = "prepare_materialization_plan" if allowed else "await_packet_acknowledgement"
    reasons = ["ack_matched", "packet_acknowledgement_ready"] if allowed else blockers
    ack_hash = _hash(
        str(profile),
        packet.packet_hash if packet else "missing_packet",
        ack or "missing_ack",
        decision,
        next_action,
        *reasons,
    )
    return CortexPacketAcknowledgementRecord(
        profile_path=str(profile),
        source_packet_id=packet.packet_id if packet else None,
        source_packet_hash=packet.packet_hash if packet else None,
        source_review_hash=packet.source_review_hash if packet else None,
        source_plan_hash=packet.source_plan_hash if packet else None,
        target_branch_type=packet.target_branch_type if packet else None,
        ack_required=REQUIRED_PACKET_ACK,
        ack_received=ack,
        ack_status=status,
        ack_decision=decision,
        ack_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        ack_hash=ack_hash,
        reasons=reasons,
    )


def _ack_blockers(packet: CortexBranchBuildPacketRecord | None, ack: str | None) -> list[str]:
    blockers = []
    if packet is None:
        return ["missing_packet"]
    if packet.packet_allowed is not True:
        blockers.append("packet_not_allowed")
    if packet.packet_decision != "branch_build_packet_ready":
        blockers.append("packet_not_ready")
    if ack != REQUIRED_PACKET_ACK:
        blockers.append("ack_missing_or_mismatch")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
