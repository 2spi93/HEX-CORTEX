"""Profile-level health scoring for local HEX-CORTEX state."""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from hex_cortex.evolver.skill_jsonl_store import SkillJsonlStore
from hex_cortex.evolver.schemas import SkillStatus
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.pruning_audit import PruningAuditJsonlStore
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


class ProfileHealthStatus(StrEnum):
    """Overall local profile health status."""

    HEALTHY = "healthy"
    WATCH = "watch"
    DEGRADED = "degraded"


class ProfileHealthComponent(BaseModel):
    """One scored health component."""

    name: str
    score: float = Field(ge=0.0, le=1.0)
    status: ProfileHealthStatus
    reason: str


class ProfileHealthReport(BaseModel):
    """Full profile health report."""

    profile_path: str
    overall_score: float = Field(ge=0.0, le=1.0)
    status: ProfileHealthStatus
    components: list[ProfileHealthComponent]
    spine_integrity_ok: bool
    total_events: int = Field(ge=0)
    total_memory_count: int = Field(ge=0)
    visible_memory_count: int = Field(ge=0)
    hidden_memory_count: int = Field(ge=0)
    average_memory_confidence: float = Field(ge=0.0, le=1.0)
    total_skill_count: int = Field(ge=0)
    active_skill_count: int = Field(ge=0)
    pruning_changed_count: int = Field(ge=0)
    pruning_archive_count: int = Field(ge=0)
    pruning_audit_count: int = Field(ge=0)
    latest_pruning_operation: str | None = None


class ProfileHealthScorer:
    """Score one local profile from persisted state."""

    def __init__(self, profile: str | Path) -> None:
        self.profile = Path(profile)

    def score(self) -> ProfileHealthReport:
        """Build a profile health report."""

        spine_component, spine_total_events, spine_ok = self._score_spine()
        memory_component, memory_stats = self._score_memory()
        skill_component, skill_stats = self._score_skills()
        pruning_component, pruning_stats = self._score_pruning(memory_stats)
        audit_component, audit_stats = self._score_audit()
        components = [
            spine_component,
            memory_component,
            skill_component,
            pruning_component,
            audit_component,
        ]
        weights = {
            "spine": 0.35,
            "memory": 0.25,
            "skills": 0.15,
            "pruning": 0.15,
            "audit": 0.10,
        }
        overall = round(
            sum(component.score * weights[component.name] for component in components),
            4,
        )
        return ProfileHealthReport(
            profile_path=str(self.profile),
            overall_score=overall,
            status=_status_for_score(overall),
            components=components,
            spine_integrity_ok=spine_ok,
            total_events=spine_total_events,
            total_memory_count=memory_stats["total"],
            visible_memory_count=memory_stats["visible"],
            hidden_memory_count=memory_stats["hidden"],
            average_memory_confidence=memory_stats["average_confidence"],
            total_skill_count=skill_stats["total"],
            active_skill_count=skill_stats["active"],
            pruning_changed_count=pruning_stats["changed"],
            pruning_archive_count=pruning_stats["archive"],
            pruning_audit_count=audit_stats["total"],
            latest_pruning_operation=audit_stats["latest_operation"],
        )

    def _score_spine(self) -> tuple[ProfileHealthComponent, int, bool]:
        spine = CanonicalSpineJsonlStore(self.profile / "spine.jsonl").load()
        integrity = spine.verify_integrity()
        total_events = spine.project().total_events
        if not integrity.ok:
            return _component("spine", 0.0, "spine_integrity_failed"), total_events, False
        if total_events == 0:
            return _component("spine", 0.7, "spine_empty_but_valid"), total_events, True
        return _component("spine", 1.0, "spine_integrity_ok"), total_events, True

    def _score_memory(self) -> tuple[ProfileHealthComponent, dict[str, int | float]]:
        memories = LocalMemoryJsonlStore(self.profile / "memory.jsonl").load()
        total = len(memories)
        visible = sum(1 for memory in memories if memory.visible)
        hidden = total - visible
        average_confidence = (
            sum(memory.confidence for memory in memories) / total if total else 0.0
        )
        if total == 0:
            component = _component("memory", 0.5, "memory_empty")
        else:
            visible_ratio = visible / total
            score = round((visible_ratio * 0.7) + (average_confidence * 0.3), 4)
            component = _component("memory", score, "memory_visible_and_confident")
        return component, {
            "total": total,
            "visible": visible,
            "hidden": hidden,
            "average_confidence": round(average_confidence, 4),
        }

    def _score_skills(self) -> tuple[ProfileHealthComponent, dict[str, int]]:
        skills = SkillJsonlStore(self.profile / "skills.jsonl").load()
        total = len(skills)
        active = sum(1 for skill in skills if skill.status == SkillStatus.ACTIVE)
        if total == 0:
            return _component("skills", 0.5, "skills_empty"), {"total": total, "active": active}
        score = round(active / total, 4)
        reason = "active_skills_available" if active else "no_active_skills"
        return _component("skills", score, reason), {"total": total, "active": active}

    def _score_pruning(
        self,
        memory_stats: dict[str, int | float],
    ) -> tuple[ProfileHealthComponent, dict[str, int]]:
        hidden = int(memory_stats["hidden"])
        total = int(memory_stats["total"])
        changed = hidden
        archive = hidden
        if total == 0:
            return _component("pruning", 0.7, "no_memory_to_prune"), {
                "changed": changed,
                "archive": archive,
            }
        if hidden == 0:
            return _component("pruning", 1.0, "no_hidden_memory"), {
                "changed": changed,
                "archive": archive,
            }
        score = round(max(0.0, 1.0 - (hidden / total)), 4)
        return _component("pruning", score, "hidden_memory_present"), {
            "changed": changed,
            "archive": archive,
        }

    def _score_audit(self) -> tuple[ProfileHealthComponent, dict[str, int | str | None]]:
        records = PruningAuditJsonlStore(self.profile / "pruning-audit.jsonl").load()
        total = len(records)
        latest_operation = records[-1].operation if records else None
        if total == 0:
            return _component("audit", 0.0, "pruning_audit_empty"), {
                "total": total,
                "latest_operation": latest_operation,
            }
        return _component("audit", 1.0, "pruning_audit_present"), {
            "total": total,
            "latest_operation": latest_operation,
        }


def _component(name: str, score: float, reason: str) -> ProfileHealthComponent:
    return ProfileHealthComponent(
        name=name,
        score=score,
        status=_status_for_score(score),
        reason=reason,
    )


def _status_for_score(score: float) -> ProfileHealthStatus:
    if score >= 0.9:
        return ProfileHealthStatus.HEALTHY
    if score >= 0.7:
        return ProfileHealthStatus.WATCH
    return ProfileHealthStatus.DEGRADED
