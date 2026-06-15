"""Skill library for HEX-CORTEX.

A skill is a validated reusable workflow. v0.1 stores and scores skills only;
it does not execute arbitrary code.
"""

from __future__ import annotations

from collections.abc import Iterable

from hex_cortex.evolver.schemas import SkillRecord, SkillStatus


class SkillLibrary:
    """Deterministic registry of reusable validated skills."""

    def __init__(self, skills: Iterable[SkillRecord] | None = None) -> None:
        self._skills: dict[str, SkillRecord] = {}

        for skill in skills or []:
            self.add(skill)

    @property
    def skills(self) -> list[SkillRecord]:
        """Return all skills as defensive copies."""

        return [skill.model_copy(deep=True) for skill in self._skills.values()]

    def add(self, skill: SkillRecord) -> SkillRecord:
        """Add one skill to the library."""

        if skill.skill_id in self._skills:
            raise ValueError(f"skill already registered: {skill.skill_id}")
        self._skills[skill.skill_id] = skill
        return skill.model_copy(deep=True)

    def get(self, skill_id: str) -> SkillRecord | None:
        """Return one skill by id."""

        skill = self._skills.get(skill_id)
        if skill is None:
            return None
        return skill.model_copy(deep=True)

    def remove(self, skill_id: str) -> None:
        """Remove one skill from the library."""

        self._skills.pop(skill_id, None)

    def active(self) -> list[SkillRecord]:
        """Return skills available for reuse."""

        return [
            skill.model_copy(deep=True)
            for skill in self._skills.values()
            if skill.status == SkillStatus.ACTIVE
        ]

    def search(
        self,
        trigger_tags: list[str],
        *,
        include_candidates: bool = False,
    ) -> list[SkillRecord]:
        """Search skills by trigger tags, highest confidence first.

        Empty tag queries return active skills sorted by confidence.
        """

        allowed_statuses = {SkillStatus.ACTIVE}
        if include_candidates:
            allowed_statuses.add(SkillStatus.CANDIDATE)

        requested = {tag.lower() for tag in trigger_tags}
        matches = []
        for skill in self._skills.values():
            if skill.status not in allowed_statuses:
                continue
            skill_tags = {tag.lower() for tag in skill.trigger_tags}
            if not requested or requested.intersection(skill_tags):
                matches.append(skill)

        ordered = sorted(matches, key=lambda skill: skill.confidence, reverse=True)
        return [skill.model_copy(deep=True) for skill in ordered]

    def activate(self, skill_id: str) -> SkillRecord:
        """Promote a skill to active if it exists."""

        skill = self._required(skill_id)
        updated = skill.model_copy(update={"status": SkillStatus.ACTIVE})
        self._skills[skill_id] = updated
        return updated.model_copy(deep=True)

    def degrade(self, skill_id: str) -> SkillRecord:
        """Mark a skill as degraded."""

        skill = self._required(skill_id)
        updated = skill.model_copy(update={"status": SkillStatus.DEGRADED})
        self._skills[skill_id] = updated
        return updated.model_copy(deep=True)

    def archive(self, skill_id: str) -> SkillRecord:
        """Archive a skill so it is no longer reused."""

        skill = self._required(skill_id)
        updated = skill.model_copy(update={"status": SkillStatus.ARCHIVED})
        self._skills[skill_id] = updated
        return updated.model_copy(deep=True)

    def record_success(self, skill_id: str) -> SkillRecord:
        """Record successful reuse and update confidence."""

        skill = self._required(skill_id)
        success_count = skill.success_count + 1
        failure_count = skill.failure_count
        confidence = self._confidence_from_counts(success_count, failure_count)
        updated = skill.model_copy(
            update={
                "success_count": success_count,
                "confidence": confidence,
                "status": SkillStatus.ACTIVE,
            }
        )
        self._skills[skill_id] = updated
        return updated.model_copy(deep=True)

    def record_failure(self, skill_id: str) -> SkillRecord:
        """Record failed reuse and degrade/archive weak skills."""

        skill = self._required(skill_id)
        success_count = skill.success_count
        failure_count = skill.failure_count + 1
        confidence = self._confidence_from_counts(success_count, failure_count)
        status = SkillStatus.DEGRADED if confidence >= 0.35 else SkillStatus.ARCHIVED
        updated = skill.model_copy(
            update={
                "failure_count": failure_count,
                "confidence": confidence,
                "status": status,
            }
        )
        self._skills[skill_id] = updated
        return updated.model_copy(deep=True)

    def _required(self, skill_id: str) -> SkillRecord:
        skill = self._skills.get(skill_id)
        if skill is None:
            raise KeyError(f"unknown skill: {skill_id}")
        return skill

    @staticmethod
    def _confidence_from_counts(success_count: int, failure_count: int) -> float:
        total = success_count + failure_count
        if total == 0:
            return 0.5
        # Conservative smoothing: one virtual success and one virtual failure.
        return round((success_count + 1) / (total + 2), 10)
