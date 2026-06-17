"""Replay learning from planner decision packets."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.planner_decision_packet import (
    PLANNER_PACKET_FILENAME,
    PlannerDecisionPacketJsonlStore,
)

PLANNER_REPLAY_FILENAME = "planner-replay-learning.jsonl"


class PlannerReplayLearningRecord(BaseModel):
    """One persisted replay-learning summary from planner packets."""

    replay_id: str = Field(default_factory=lambda: f"planner_replay_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    packet_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    watch_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    dominant_status: str
    missing_skills: list[str]
    repeated_next_actions: list[str]
    latest_planner_decision: str | None
    latest_next_action: str | None
    replay_recommendation: str
    replay_score: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class PlannerReplayLearningSummary(BaseModel):
    """Summary of persisted replay-learning records."""

    inspect_type: str = "planner_replay_learning"
    path: str
    exists: bool
    total_replay_count: int = Field(ge=0)
    latest_replay_id: str | None
    latest_packet_count: int | None
    latest_dominant_status: str | None
    latest_replay_recommendation: str | None
    latest_replay_score: float | None


class PlannerReplayLearningJsonlStore:
    """Persist replay-learning records as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[PlannerReplayLearningRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(PlannerReplayLearningRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    message = f"invalid planner learning record at line {line_number}"
                    raise ValueError(message) from exc
        return records

    def save(self, records: list[PlannerReplayLearningRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: PlannerReplayLearningRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def learn_from_planner_packets(profile: Path) -> dict[str, object]:
    """Learn signals from planner packets."""

    packets = PlannerDecisionPacketJsonlStore(profile / PLANNER_PACKET_FILENAME).load()
    record = _learn(profile, packets)
    path = profile / PLANNER_REPLAY_FILENAME
    count = PlannerReplayLearningJsonlStore(path).append(record)
    return {
        "replay_type": "planner_replay_learning",
        "profile_path": str(profile),
        "replay_path": str(path),
        "replay_count": count,
        "replay_record": record.model_dump(mode="json"),
    }


def summarize_planner_replay_learning(path: Path) -> dict[str, object]:
    records = PlannerReplayLearningJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = PlannerReplayLearningSummary(
        path=str(path),
        exists=path.exists(),
        total_replay_count=len(records),
        latest_replay_id=latest.replay_id if latest else None,
        latest_packet_count=latest.packet_count if latest else None,
        latest_dominant_status=latest.dominant_status if latest else None,
        latest_replay_recommendation=latest.replay_recommendation if latest else None,
        latest_replay_score=latest.replay_score if latest else None,
    )
    return summary.model_dump(mode="json")


def _learn(profile: Path, packets) -> PlannerReplayLearningRecord:
    if not packets:
        return _missing_packets(profile)
    status_counts = Counter(packet.planner_status for packet in packets)
    registry_counts = Counter(packet.registry_status for packet in packets)
    action_counts = Counter(packet.next_action for packet in packets)
    missing_skills = _missing_skills(packets)
    latest = packets[-1]
    fallback_count = registry_counts.get("fallback", 0)
    recommendation, score, reasons = _recommendation(
        packets,
        fallback_count,
        missing_skills,
    )
    return PlannerReplayLearningRecord(
        profile_path=str(profile),
        packet_count=len(packets),
        ready_count=status_counts.get("ready", 0),
        watch_count=status_counts.get("watch", 0),
        blocked_count=status_counts.get("blocked", 0),
        fallback_count=fallback_count,
        dominant_status=status_counts.most_common(1)[0][0],
        missing_skills=missing_skills,
        repeated_next_actions=_repeated_actions(action_counts),
        latest_planner_decision=latest.planner_decision,
        latest_next_action=latest.next_action,
        replay_recommendation=recommendation,
        replay_score=score,
        reasons=reasons,
    )


def _missing_packets(profile: Path) -> PlannerReplayLearningRecord:
    return PlannerReplayLearningRecord(
        profile_path=str(profile),
        packet_count=0,
        ready_count=0,
        watch_count=0,
        blocked_count=0,
        fallback_count=0,
        dominant_status="missing",
        missing_skills=[],
        repeated_next_actions=[],
        latest_planner_decision=None,
        latest_next_action=None,
        replay_recommendation="build_planner_decision_packet",
        replay_score=0.0,
        reasons=["planner_packets_missing"],
    )


def _missing_skills(packets) -> list[str]:
    return sorted(
        {
            packet.selected_skill
            for packet in packets
            if packet.registry_status == "fallback"
        }
    )


def _recommendation(packets, fallback_count: int, missing_skills: list[str]):
    if fallback_count:
        reasons = ["planner_fallback_repeated"]
        reasons.append("missing_skills:" + ",".join(missing_skills))
        return "register_or_activate_missing_skills", 0.8, reasons
    if any(packet.planner_status == "ready" for packet in packets):
        return "stage_controlled_skill_execution_gate", 1.0, ["planner_ready_seen"]
    if any(packet.planner_status == "blocked" for packet in packets):
        return "repair_blocking_planner_inputs", 0.4, ["planner_blocked_seen"]
    return "continue_planner_observation", 0.6, ["planner_watch_only"]


def _repeated_actions(counter: Counter) -> list[str]:
    return sorted(action for action, count in counter.items() if count > 1)
