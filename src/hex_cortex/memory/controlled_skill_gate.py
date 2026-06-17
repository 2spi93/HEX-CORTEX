"""Controlled gate for staged skill execution readiness."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.planner_decision_packet import (
    PLANNER_PACKET_FILENAME,
    PlannerDecisionPacketJsonlStore,
)
from hex_cortex.memory.planner_replay_learning import (
    PLANNER_REPLAY_FILENAME,
    PlannerReplayLearningJsonlStore,
)

CONTROLLED_SKILL_GATE_FILENAME = "controlled-skill-gate.jsonl"


class ControlledSkillGateRecord(BaseModel):
    """One persisted controlled skill gate decision."""

    gate_id: str = Field(default_factory=lambda: f"skill_gate_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_packet_id: str | None
    source_replay_id: str | None
    selected_skill: str
    selected_action: str
    gate_status: str
    gate_decision: str
    execution_allowed: bool
    execution_mode: str
    next_action: str
    planner_decision: str | None
    replay_recommendation: str | None
    gate_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class ControlledSkillGateSummary(BaseModel):
    """Summary of persisted controlled skill gate decisions."""

    inspect_type: str = "controlled_skill_gate"
    path: str
    exists: bool
    total_gate_count: int = Field(ge=0)
    latest_gate_id: str | None
    latest_selected_skill: str | None
    latest_gate_status: str | None
    latest_gate_decision: str | None
    latest_execution_allowed: bool | None
    latest_next_action: str | None
    latest_gate_confidence: float | None


class ControlledSkillGateJsonlStore:
    """Persist controlled skill gate decisions as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[ControlledSkillGateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(ControlledSkillGateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid controlled skill gate record at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[ControlledSkillGateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: ControlledSkillGateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def evaluate_controlled_skill_gate(profile: Path) -> dict[str, object]:
    """Evaluate whether a skill may reach controlled execution staging."""

    packets = PlannerDecisionPacketJsonlStore(profile / PLANNER_PACKET_FILENAME).load()
    replays = PlannerReplayLearningJsonlStore(profile / PLANNER_REPLAY_FILENAME).load()
    if not packets:
        record = _missing_packet_gate(profile, replays[-1] if replays else None)
    else:
        record = _gate_from_sources(profile, packets[-1], replays[-1] if replays else None)
    path = profile / CONTROLLED_SKILL_GATE_FILENAME
    count = ControlledSkillGateJsonlStore(path).append(record)
    return {
        "gate_type": "controlled_skill_gate",
        "profile_path": str(profile),
        "gate_path": str(path),
        "gate_count": count,
        "gate_record": record.model_dump(mode="json"),
    }


def summarize_controlled_skill_gates(path: Path) -> dict[str, object]:
    records = ControlledSkillGateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = ControlledSkillGateSummary(
        path=str(path),
        exists=path.exists(),
        total_gate_count=len(records),
        latest_gate_id=latest.gate_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_gate_status=latest.gate_status if latest else None,
        latest_gate_decision=latest.gate_decision if latest else None,
        latest_execution_allowed=latest.execution_allowed if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_gate_confidence=latest.gate_confidence if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_packet_gate(profile: Path, replay) -> ControlledSkillGateRecord:
    return ControlledSkillGateRecord(
        profile_path=str(profile),
        source_packet_id=None,
        source_replay_id=replay.replay_id if replay else None,
        selected_skill="planner_packet_missing",
        selected_action="build_planner_decision_packet",
        gate_status="blocked",
        gate_decision="gate_blocked",
        execution_allowed=False,
        execution_mode="none",
        next_action="build_planner_decision_packet",
        planner_decision=None,
        replay_recommendation=replay.replay_recommendation if replay else None,
        gate_confidence=0.0,
        reasons=["planner_packet_missing"],
    )


def _gate_from_sources(profile: Path, packet, replay) -> ControlledSkillGateRecord:
    replay_recommendation = replay.replay_recommendation if replay else None
    can_stage = (
        packet.action_allowed
        and packet.planner_decision == "planner_ready"
        and replay_recommendation == "stage_controlled_skill_execution_gate"
    )
    if can_stage:
        return _ready_gate(profile, packet, replay)
    if packet.planner_decision == "planner_watch":
        return _watch_gate(profile, packet, replay)
    return _blocked_gate(profile, packet, replay)


def _ready_gate(profile: Path, packet, replay) -> ControlledSkillGateRecord:
    return ControlledSkillGateRecord(
        profile_path=str(profile),
        source_packet_id=packet.packet_id,
        source_replay_id=replay.replay_id if replay else None,
        selected_skill=packet.selected_skill,
        selected_action=packet.selected_action,
        gate_status="ready",
        gate_decision="gate_ready",
        execution_allowed=True,
        execution_mode="controlled_staging_only",
        next_action="stage_controlled_skill_execution_audit",
        planner_decision=packet.planner_decision,
        replay_recommendation=replay.replay_recommendation if replay else None,
        gate_confidence=packet.overall_confidence,
        reasons=["controlled_gate_quality_ok"],
    )


def _watch_gate(profile: Path, packet, replay) -> ControlledSkillGateRecord:
    next_action = packet.next_action
    reasons = ["planner_watch"]
    if packet.registry_status == "fallback":
        next_action = "register_or_activate_skill"
        reasons.append("skill_registry_fallback")
    return ControlledSkillGateRecord(
        profile_path=str(profile),
        source_packet_id=packet.packet_id,
        source_replay_id=replay.replay_id if replay else None,
        selected_skill=packet.selected_skill,
        selected_action=packet.selected_action,
        gate_status="watch",
        gate_decision="gate_watch",
        execution_allowed=False,
        execution_mode="none",
        next_action=next_action,
        planner_decision=packet.planner_decision,
        replay_recommendation=replay.replay_recommendation if replay else None,
        gate_confidence=packet.overall_confidence,
        reasons=reasons,
    )


def _blocked_gate(profile: Path, packet, replay) -> ControlledSkillGateRecord:
    return ControlledSkillGateRecord(
        profile_path=str(profile),
        source_packet_id=packet.packet_id,
        source_replay_id=replay.replay_id if replay else None,
        selected_skill=packet.selected_skill,
        selected_action=packet.selected_action,
        gate_status="blocked",
        gate_decision="gate_blocked",
        execution_allowed=False,
        execution_mode="none",
        next_action="repair_planner_inputs",
        planner_decision=packet.planner_decision,
        replay_recommendation=replay.replay_recommendation if replay else None,
        gate_confidence=packet.overall_confidence,
        reasons=["planner_not_ready"],
    )
