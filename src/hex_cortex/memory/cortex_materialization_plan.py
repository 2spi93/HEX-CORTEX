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
from hex_cortex.memory.cortex_packet_acknowledgement import (
    CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME,
    CortexPacketAcknowledgementJsonlStore,
    CortexPacketAcknowledgementRecord,
)

CORTEX_MATERIALIZATION_PLAN_FILENAME = "cortex-materialization-plan.jsonl"


class CortexMaterializationPlanRecord(BaseModel):
    materialization_id: str = Field(default_factory=lambda: f"cortex_materialization_plan_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_ack_id: str | None
    source_ack_hash: str | None
    source_packet_id: str | None
    source_packet_hash: str | None
    source_review_hash: str | None
    source_plan_hash: str | None
    target_branch_type: str | None
    best_node_id: str | None
    materialization_scope: str
    allowed_files: list[str]
    planned_operations: list[str]
    required_tests: list[str]
    safety_constraints: list[str]
    stop_conditions: list[str]
    materialization_status: str
    materialization_decision: str
    materialization_allowed: bool
    next_action: str
    blockers: list[str]
    materialization_hash: str
    reasons: list[str]


class CortexMaterializationPlanJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMaterializationPlanRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMaterializationPlanRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex materialization plan {line_number}") from exc
        return records

    def save(self, records: list[CortexMaterializationPlanRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_materialization_plan(profile: Path) -> dict[str, object]:
    ack = _latest_ack(profile)
    packet = _matching_packet(profile, ack)
    record = _materialization_record(profile, ack, packet)
    path = profile / CORTEX_MATERIALIZATION_PLAN_FILENAME
    store = CortexMaterializationPlanJsonlStore(path)
    current = store.load()
    if record.source_ack_hash and any(item.source_ack_hash == record.source_ack_hash for item in current):
        records: list[CortexMaterializationPlanRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "materialization_type": "cortex_materialization_plan",
        "profile_path": str(profile),
        "materialization_path": str(path),
        "materialization_count": count,
        "materialization_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_materialization_plans(path: Path) -> dict[str, object]:
    records = CortexMaterializationPlanJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.materialization_allowed]
    return {
        "inspect_type": "cortex_materialization_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_materialization_count": len(records),
        "allowed_materialization_count": len(allowed),
        "latest_materialization_id": latest.materialization_id if latest else None,
        "latest_materialization_status": latest.materialization_status if latest else None,
        "latest_materialization_decision": latest.materialization_decision if latest else None,
        "latest_materialization_allowed": latest.materialization_allowed if latest else None,
        "latest_target_branch_type": latest.target_branch_type if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_materialization_hash": latest.materialization_hash if latest else None,
    }


def _latest_ack(profile: Path) -> CortexPacketAcknowledgementRecord | None:
    records = CortexPacketAcknowledgementJsonlStore(profile / CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME).load()
    return records[-1] if records else None


def _matching_packet(
    profile: Path,
    ack: CortexPacketAcknowledgementRecord | None,
) -> CortexBranchBuildPacketRecord | None:
    if ack is None or not ack.source_packet_hash:
        return None
    records = CortexBranchBuildPacketJsonlStore(profile / CORTEX_BRANCH_BUILD_PACKET_FILENAME).load()
    for record in reversed(records):
        if record.packet_hash == ack.source_packet_hash:
            return record
    return None


def _materialization_record(
    profile: Path,
    ack: CortexPacketAcknowledgementRecord | None,
    packet: CortexBranchBuildPacketRecord | None,
) -> CortexMaterializationPlanRecord:
    blockers = _materialization_blockers(ack, packet)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "materialization_plan_ready" if allowed else "materialization_plan_blocked"
    next_action = "await_materialization_review" if allowed else "repair_packet_acknowledgement"
    reasons = ["packet_ack_ready", "materialization_plan_prepared"] if allowed else blockers
    allowed_files = list(packet.authorized_files) if allowed and packet else []
    required_tests = list(packet.required_tests) if allowed and packet else []
    stop_conditions = list(packet.stop_conditions) if allowed and packet else []
    planned_operations = _planned_operations(packet) if allowed and packet else []
    safety_constraints = _safety_constraints(packet) if allowed and packet else []
    materialization_hash = _hash(
        str(profile),
        ack.ack_hash if ack else "missing_ack",
        packet.packet_hash if packet else "missing_packet",
        decision,
        next_action,
        *allowed_files,
        *planned_operations,
        *required_tests,
        *reasons,
    )
    return CortexMaterializationPlanRecord(
        profile_path=str(profile),
        source_ack_id=ack.ack_id if ack else None,
        source_ack_hash=ack.ack_hash if ack else None,
        source_packet_id=packet.packet_id if packet else None,
        source_packet_hash=packet.packet_hash if packet else None,
        source_review_hash=packet.source_review_hash if packet else None,
        source_plan_hash=packet.source_plan_hash if packet else None,
        target_branch_type=packet.target_branch_type if packet else None,
        best_node_id=packet.best_node_id if packet else None,
        materialization_scope="declarative_only",
        allowed_files=allowed_files,
        planned_operations=planned_operations,
        required_tests=required_tests,
        safety_constraints=safety_constraints,
        stop_conditions=stop_conditions,
        materialization_status=status,
        materialization_decision=decision,
        materialization_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        materialization_hash=materialization_hash,
        reasons=reasons,
    )


def _planned_operations(packet: CortexBranchBuildPacketRecord) -> list[str]:
    return [f"prepare:{path}" for path in packet.authorized_files]


def _safety_constraints(packet: CortexBranchBuildPacketRecord) -> list[str]:
    return [
        "declarative plan only",
        "do not modify files from this step",
        "materialize only listed files after a separate review",
        "run required tests after materialization",
        f"target_branch_type={packet.target_branch_type}",
    ]


def _materialization_blockers(
    ack: CortexPacketAcknowledgementRecord | None,
    packet: CortexBranchBuildPacketRecord | None,
) -> list[str]:
    blockers = []
    if ack is None:
        return ["missing_packet_acknowledgement"]
    if ack.ack_allowed is not True:
        blockers.append("packet_acknowledgement_not_allowed")
    if ack.ack_decision != "packet_acknowledgement_ready":
        blockers.append("packet_acknowledgement_not_ready")
    if ack.next_action != "prepare_materialization_plan":
        blockers.append("ack_not_waiting_materialization_plan")
    if packet is None:
        blockers.append("missing_source_branch_build_packet")
    elif ack.source_packet_hash != packet.packet_hash:
        blockers.append("source_packet_hash_mismatch")
    if packet is not None and (not packet.authorized_files or not packet.required_tests):
        blockers.append("missing_packet_files_or_tests")
    if packet is not None and not packet.stop_conditions:
        blockers.append("missing_packet_stop_conditions")
    return blockers


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
