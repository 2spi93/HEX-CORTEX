"""Pruning decisions for HEX-CORTEX."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.evolver.schemas import CellHealth, SkillRecord, SkillStatus
from hex_cortex.memory.schemas import MemoryRecord, TacitRule

TargetType = Literal["memory", "rule", "skill", "cell"]


class PruningAction(StrEnum):
    """Conservative pruning action."""

    KEEP = "keep"
    DEGRADE = "degrade"
    ARCHIVE = "archive"
    QUARANTINE = "quarantine"


class PruningDecision(BaseModel):
    """One pruning decision for one target."""

    decision_id: str = Field(default_factory=lambda: f"prune_{uuid4().hex}")
    target_type: TargetType
    target_id: str
    action: PruningAction
    reason: str
    score: float = Field(ge=0.0, le=1.0)


class PruningBatchReport(BaseModel):
    """Batch of pruning decisions."""

    decisions: list[PruningDecision] = Field(default_factory=list)

    @property
    def archive_count(self) -> int:
        return self._count(PruningAction.ARCHIVE)

    @property
    def degrade_count(self) -> int:
        return self._count(PruningAction.DEGRADE)

    @property
    def quarantine_count(self) -> int:
        return self._count(PruningAction.QUARANTINE)

    @property
    def keep_count(self) -> int:
        return self._count(PruningAction.KEEP)

    def _count(self, action: PruningAction) -> int:
        return sum(1 for decision in self.decisions if decision.action == action)


class PruningEngine:
    """Deterministic pruning policy for memory, rules, skills, and cells.

    v0.1 emits decisions only. It does not delete source material.
    """

    def __init__(
        self,
        *,
        archive_threshold: float = 0.25,
        degrade_threshold: float = 0.45,
        quarantine_threshold: float = 0.35,
    ) -> None:
        self.archive_threshold = archive_threshold
        self.degrade_threshold = degrade_threshold
        self.quarantine_threshold = quarantine_threshold

    def decide_memory(self, memory: MemoryRecord) -> PruningDecision:
        if not memory.deletable:
            return self._decision(
                "memory",
                memory.memory_id,
                PruningAction.KEEP,
                "memory_not_deletable",
                memory.confidence,
            )
        if not memory.visible:
            return self._decision(
                "memory",
                memory.memory_id,
                PruningAction.ARCHIVE,
                "memory_already_hidden",
                memory.confidence,
            )
        if memory.confidence < self.archive_threshold:
            return self._decision(
                "memory",
                memory.memory_id,
                PruningAction.ARCHIVE,
                "memory_confidence_below_archive_threshold",
                memory.confidence,
            )
        if memory.confidence < self.degrade_threshold:
            return self._decision(
                "memory",
                memory.memory_id,
                PruningAction.DEGRADE,
                "memory_confidence_below_degrade_threshold",
                memory.confidence,
            )
        return self._decision(
            "memory",
            memory.memory_id,
            PruningAction.KEEP,
            "memory_healthy",
            memory.confidence,
        )

    def decide_rule(self, rule: TacitRule) -> PruningDecision:
        total = rule.success_count + rule.failure_count
        failure_ratio = rule.failure_count / total if total else 0.0
        more_failures = rule.failure_count > rule.success_count
        if rule.confidence < self.archive_threshold and more_failures:
            return self._decision(
                "rule",
                rule.rule_id,
                PruningAction.ARCHIVE,
                "rule_low_confidence_and_more_failures_than_successes",
                rule.confidence,
            )
        if failure_ratio >= 0.5 and total >= 2:
            return self._decision(
                "rule",
                rule.rule_id,
                PruningAction.DEGRADE,
                "rule_failure_ratio_too_high",
                rule.confidence,
            )
        return self._decision(
            "rule",
            rule.rule_id,
            PruningAction.KEEP,
            "rule_healthy",
            rule.confidence,
        )

    def decide_skill(self, skill: SkillRecord) -> PruningDecision:
        if skill.status == SkillStatus.ARCHIVED:
            return self._decision(
                "skill",
                skill.skill_id,
                PruningAction.KEEP,
                "skill_already_archived",
                skill.confidence,
            )
        if skill.confidence < self.archive_threshold:
            return self._decision(
                "skill",
                skill.skill_id,
                PruningAction.ARCHIVE,
                "skill_confidence_below_archive_threshold",
                skill.confidence,
            )
        if skill.confidence < self.degrade_threshold:
            return self._decision(
                "skill",
                skill.skill_id,
                PruningAction.DEGRADE,
                "skill_confidence_below_degrade_threshold",
                skill.confidence,
            )
        return self._decision(
            "skill",
            skill.skill_id,
            PruningAction.KEEP,
            "skill_healthy",
            skill.confidence,
        )

    def decide_cell(self, health: CellHealth) -> PruningDecision:
        if health.quarantine:
            return self._decision(
                "cell",
                health.cell_id,
                PruningAction.QUARANTINE,
                "cell_already_quarantined",
                health.trust_score,
            )
        repeated_failure = health.failure_count >= 3
        if health.trust_score < self.quarantine_threshold and repeated_failure:
            return self._decision(
                "cell",
                health.cell_id,
                PruningAction.QUARANTINE,
                "cell_trust_below_quarantine_threshold",
                health.trust_score,
            )
        if health.requires_double_check:
            return self._decision(
                "cell",
                health.cell_id,
                PruningAction.DEGRADE,
                "cell_requires_double_check",
                health.trust_score,
            )
        return self._decision(
            "cell",
            health.cell_id,
            PruningAction.KEEP,
            "cell_healthy",
            health.trust_score,
        )

    def decide_batch(
        self,
        *,
        memories: list[MemoryRecord] | None = None,
        rules: list[TacitRule] | None = None,
        skills: list[SkillRecord] | None = None,
        cells: list[CellHealth] | None = None,
    ) -> PruningBatchReport:
        decisions = []
        decisions.extend(self.decide_memory(memory) for memory in memories or [])
        decisions.extend(self.decide_rule(rule) for rule in rules or [])
        decisions.extend(self.decide_skill(skill) for skill in skills or [])
        decisions.extend(self.decide_cell(cell) for cell in cells or [])
        return PruningBatchReport(decisions=decisions)

    @staticmethod
    def _decision(
        target_type: TargetType,
        target_id: str,
        action: PruningAction,
        reason: str,
        score: float,
    ) -> PruningDecision:
        return PruningDecision(
            target_type=target_type,
            target_id=target_id,
            action=action,
            reason=reason,
            score=max(0.0, min(score, 1.0)),
        )
