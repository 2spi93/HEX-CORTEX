"""Statistics from planner decision packets."""

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

PLANNER_STATS_FILENAME = "planner-packet-stats.jsonl"


class PlannerPacketStatsRecord(BaseModel):
    """One persisted planner packet statistics record."""

    stats_id: str = Field(default_factory=lambda: f"planner_stats_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_packet_count: int = Field(ge=0)
    ready_count: int = Field(ge=0)
    watch_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    fallback_count: int = Field(ge=0)
    allowed_count: int = Field(ge=0)
    dominant_status: str
    dominant_next_action: str | None
    missing_skills: list[str]
    packet_score: float = Field(ge=0.0, le=1.0)
    recommended_action: str
    reasons: list[str]


class PlannerPacketStatsSummary(BaseModel):
    """Summary of persisted planner packet statistics."""

    inspect_type: str = "planner_packet_stats"
    path: str
    exists: bool
    total_stats_count: int = Field(ge=0)
    latest_stats_id: str | None
    latest_source_packet_count: int | None
    latest_dominant_status: str | None
    latest_recommended_action: str | None
    latest_packet_score: float | None
    latest_missing_skills: list[str]


class PlannerPacketStatsJsonlStore:
    """Persist planner packet statistics as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[PlannerPacketStatsRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(PlannerPacketStatsRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid planner packet stats at line {line_number}") from exc
        return records

    def save(self, records: list[PlannerPacketStatsRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: PlannerPacketStatsRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_planner_packet_stats(profile: Path) -> dict[str, object]:
    """Build and persist statistics from planner decision packets."""

    packets = PlannerDecisionPacketJsonlStore(profile / PLANNER_PACKET_FILENAME).load()
    record = _record_from_packets(profile, packets)
    path = profile / PLANNER_STATS_FILENAME
    count = PlannerPacketStatsJsonlStore(path).append(record)
    return {
        "stats_type": "planner_packet_stats",
        "profile_path": str(profile),
        "stats_path": str(path),
        "stats_count": count,
        "stats_record": record.model_dump(mode="json"),
    }


def summarize_planner_packet_stats(path: Path) -> dict[str, object]:
    records = PlannerPacketStatsJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = PlannerPacketStatsSummary(
        path=str(path),
        exists=path.exists(),
        total_stats_count=len(records),
        latest_stats_id=latest.stats_id if latest else None,
        latest_source_packet_count=latest.source_packet_count if latest else None,
        latest_dominant_status=latest.dominant_status if latest else None,
        latest_recommended_action=latest.recommended_action if latest else None,
        latest_packet_score=latest.packet_score if latest else None,
        latest_missing_skills=latest.missing_skills if latest else [],
    )
    return summary.model_dump(mode="json")


def _record_from_packets(profile: Path, packets) -> PlannerPacketStatsRecord:
    if not packets:
        return PlannerPacketStatsRecord(
            profile_path=str(profile),
            source_packet_count=0,
            ready_count=0,
            watch_count=0,
            blocked_count=0,
            fallback_count=0,
            allowed_count=0,
            dominant_status="missing",
            dominant_next_action="build_planner_decision_packet",
            missing_skills=[],
            packet_score=0.0,
            recommended_action="build_planner_decision_packet",
            reasons=["planner_packets_missing"],
        )
    status_counts = Counter(packet.planner_status for packet in packets)
    next_action_counts = Counter(packet.next_action for packet in packets)
    fallback_packets = [packet for packet in packets if packet.registry_status == "fallback"]
    missing_skills = sorted({packet.selected_skill for packet in fallback_packets})
    allowed_count = sum(1 for packet in packets if packet.action_allowed)
    packet_score = _packet_score(packets, allowed_count, len(fallback_packets))
    recommended_action, reasons = _recommended_action(packets, missing_skills, packet_score)
    return PlannerPacketStatsRecord(
        profile_path=str(profile),
        source_packet_count=len(packets),
        ready_count=status_counts.get("ready", 0),
        watch_count=status_counts.get("watch", 0),
        blocked_count=status_counts.get("blocked", 0),
        fallback_count=len(fallback_packets),
        allowed_count=allowed_count,
        dominant_status=status_counts.most_common(1)[0][0],
        dominant_next_action=next_action_counts.most_common(1)[0][0],
        missing_skills=missing_skills,
        packet_score=packet_score,
        recommended_action=recommended_action,
        reasons=reasons,
    )


def _packet_score(packets, allowed_count: int, fallback_count: int) -> float:
    if not packets:
        return 0.0
    allowed_ratio = allowed_count / len(packets)
    fallback_penalty = fallback_count / len(packets)
    return round(max(0.0, allowed_ratio - (0.5 * fallback_penalty)), 4)


def _recommended_action(packets, missing_skills: list[str], packet_score: float):
    if missing_skills:
        return "register_or_activate_missing_skills", ["planner_fallback_observed"]
    if packet_score >= 0.8:
        return "stage_execution_gate_review", ["planner_ready_observed"]
    if any(packet.planner_status == "blocked" for packet in packets):
        return "inspect_blocked_planner_packets", ["planner_blocked_observed"]
    return "continue_planner_observation", ["planner_watch_observed"]
