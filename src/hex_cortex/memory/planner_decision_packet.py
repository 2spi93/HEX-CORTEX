"""Planner decision packets from latent state, registry match, and action cost."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.action_cost_model import ACTION_COST_FILENAME, ActionCostJsonlStore
from hex_cortex.memory.latent_state_compression import LATENT_STATE_FILENAME, LatentStateJsonlStore
from hex_cortex.memory.skill_registry_integration import (
    SKILL_REGISTRY_MATCH_FILENAME,
    SkillRegistryMatchJsonlStore,
)

PLANNER_PACKET_FILENAME = "planner-decision-packet.jsonl"


class PlannerDecisionPacketRecord(BaseModel):
    """One persisted planner decision packet."""

    packet_id: str = Field(default_factory=lambda: f"planner_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_latent_id: str | None
    source_match_id: str | None
    source_cost_id: str | None
    selected_skill: str
    selected_action: str
    planner_status: str
    planner_decision: str
    next_action: str
    action_allowed: bool
    registry_status: str | None
    match_score: float = Field(ge=0.0, le=1.0)
    action_score: float = Field(ge=0.0, le=1.0)
    compression_score: float = Field(ge=0.0, le=1.0)
    overall_confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


class PlannerDecisionPacketSummary(BaseModel):
    """Summary of persisted planner decision packets."""

    inspect_type: str = "planner_decision_packet"
    path: str
    exists: bool
    total_packet_count: int = Field(ge=0)
    latest_packet_id: str | None
    latest_selected_skill: str | None
    latest_planner_status: str | None
    latest_planner_decision: str | None
    latest_next_action: str | None
    latest_action_allowed: bool | None
    latest_overall_confidence: float | None


class PlannerDecisionPacketJsonlStore:
    """Persist planner packets as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[PlannerDecisionPacketRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(PlannerDecisionPacketRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid planner decision packet at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[PlannerDecisionPacketRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: PlannerDecisionPacketRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_latest_planner_decision_packet(profile: Path) -> dict[str, object]:
    """Build and persist the latest planner decision packet."""

    latents = LatentStateJsonlStore(profile / LATENT_STATE_FILENAME).load()
    matches = SkillRegistryMatchJsonlStore(profile / SKILL_REGISTRY_MATCH_FILENAME).load()
    costs = ActionCostJsonlStore(profile / ACTION_COST_FILENAME).load()
    if not matches:
        record = _missing_match_packet(profile, latents[-1] if latents else None, costs[-1] if costs else None)
    else:
        record = _packet_from_sources(
            profile,
            latents[-1] if latents else None,
            matches[-1],
            costs[-1] if costs else None,
        )
    path = profile / PLANNER_PACKET_FILENAME
    count = PlannerDecisionPacketJsonlStore(path).append(record)
    return {
        "packet_type": "planner_decision_packet",
        "profile_path": str(profile),
        "packet_path": str(path),
        "packet_count": count,
        "packet_record": record.model_dump(mode="json"),
    }


def summarize_planner_decision_packets(path: Path) -> dict[str, object]:
    records = PlannerDecisionPacketJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = PlannerDecisionPacketSummary(
        path=str(path),
        exists=path.exists(),
        total_packet_count=len(records),
        latest_packet_id=latest.packet_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_planner_status=latest.planner_status if latest else None,
        latest_planner_decision=latest.planner_decision if latest else None,
        latest_next_action=latest.next_action if latest else None,
        latest_action_allowed=latest.action_allowed if latest else None,
        latest_overall_confidence=latest.overall_confidence if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_match_packet(profile: Path, latent, cost) -> PlannerDecisionPacketRecord:
    selected_skill = latent.suggested_skill if latent else "skill_registry_match_missing"
    selected_action = latent.candidate_action if latent else "match_skill_registry"
    action_score = cost.action_score if cost else 0.0
    compression_score = latent.compression_score if latent else 0.0
    return PlannerDecisionPacketRecord(
        profile_path=str(profile),
        source_latent_id=latent.latent_id if latent else None,
        source_match_id=None,
        source_cost_id=cost.cost_id if cost else None,
        selected_skill=selected_skill,
        selected_action=selected_action,
        planner_status="blocked",
        planner_decision="planner_blocked",
        next_action="build_skill_registry_match",
        action_allowed=False,
        registry_status=None,
        match_score=0.0,
        action_score=action_score,
        compression_score=compression_score,
        overall_confidence=0.0,
        reasons=["skill_registry_match_missing"],
    )


def _packet_from_sources(profile: Path, latent, match, cost) -> PlannerDecisionPacketRecord:
    selected_skill = match.matched_skill_name or match.latent_suggested_skill
    selected_action = latent.candidate_action if latent else "inspect_planner_state"
    action_score = cost.action_score if cost else match.action_score
    compression_score = latent.compression_score if latent else match.compression_score
    confidence = _overall_confidence(match.match_score, action_score, compression_score)
    status, decision, next_action, allowed, reasons = _planner_outcome(match, action_score, confidence)
    return PlannerDecisionPacketRecord(
        profile_path=str(profile),
        source_latent_id=latent.latent_id if latent else match.latent_id,
        source_match_id=match.match_id,
        source_cost_id=cost.cost_id if cost else None,
        selected_skill=selected_skill,
        selected_action=selected_action,
        planner_status=status,
        planner_decision=decision,
        next_action=next_action,
        action_allowed=allowed,
        registry_status=match.registry_status,
        match_score=match.match_score,
        action_score=action_score,
        compression_score=compression_score,
        overall_confidence=confidence,
        reasons=reasons,
    )


def _overall_confidence(match_score: float, action_score: float, compression_score: float) -> float:
    return round((match_score + action_score + compression_score) / 3, 4)


def _planner_outcome(match, action_score: float, confidence: float):
    if match.registry_status == "matched" and confidence >= 0.75 and action_score >= 0.75:
        return (
            "ready",
            "planner_ready",
            "stage_skill_execution_gate",
            True,
            ["planner_packet_quality_ok"],
        )
    if match.registry_status == "fallback":
        return (
            "watch",
            "planner_watch",
            "register_or_activate_skill",
            False,
            ["skill_registry_fallback"],
        )
    if action_score < 0.5:
        return (
            "blocked",
            "planner_blocked",
            "repair_action_cost",
            False,
            ["low_action_score"],
        )
    return (
        "watch",
        "planner_watch",
        "review_planner_packet",
        False,
        ["planner_confidence_watch"],
    )
