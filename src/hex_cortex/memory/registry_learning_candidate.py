"""Learning candidates derived from skill outcome feedback and registry matches."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.skill_outcome_feedback import (
    SKILL_OUTCOME_FEEDBACK_FILENAME,
    SkillOutcomeFeedbackJsonlStore,
)
from hex_cortex.memory.skill_registry_integration import (
    SKILL_REGISTRY_MATCH_FILENAME,
    SkillRegistryMatchJsonlStore,
)

REGISTRY_LEARNING_FILENAME = "registry-learning-candidate.jsonl"


class RegistryLearningCandidateRecord(BaseModel):
    """One persisted registry learning candidate."""

    learning_id: str = Field(default_factory=lambda: f"registry_learning_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_feedback_id: str | None
    source_match_id: str | None
    registry_status: str | None
    observed_outcome: str | None
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    not_observed_count: int = Field(ge=0)
    learning_score: float = Field(ge=0.0, le=1.0)
    learning_status: str
    learning_decision: str
    next_action: str
    reasons: list[str]


class RegistryLearningCandidateSummary(BaseModel):
    """Summary of persisted registry learning candidates."""

    inspect_type: str = "registry_learning_candidate"
    path: str
    exists: bool
    total_learning_count: int = Field(ge=0)
    latest_learning_id: str | None
    latest_selected_skill: str | None
    latest_learning_status: str | None
    latest_learning_decision: str | None
    latest_learning_score: float | None
    latest_next_action: str | None


class RegistryLearningCandidateJsonlStore:
    """Persist registry learning candidates as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[RegistryLearningCandidateRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(RegistryLearningCandidateRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid registry learning candidate at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[RegistryLearningCandidateRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: RegistryLearningCandidateRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_registry_learning_candidate(profile: Path) -> dict[str, object]:
    """Build a registry learning candidate without changing the registry."""

    feedback_records = SkillOutcomeFeedbackJsonlStore(
        profile / SKILL_OUTCOME_FEEDBACK_FILENAME
    ).load()
    matches = SkillRegistryMatchJsonlStore(profile / SKILL_REGISTRY_MATCH_FILENAME).load()
    if not feedback_records:
        record = _missing_feedback_candidate(profile, matches[-1] if matches else None)
    else:
        record = _candidate_from_feedback(
            profile,
            feedback_records,
            matches[-1] if matches else None,
        )
    path = profile / REGISTRY_LEARNING_FILENAME
    count = RegistryLearningCandidateJsonlStore(path).append(record)
    return {
        "learning_type": "registry_learning_candidate",
        "profile_path": str(profile),
        "learning_path": str(path),
        "learning_count": count,
        "learning_record": record.model_dump(mode="json"),
    }


def summarize_registry_learning_candidates(path: Path) -> dict[str, object]:
    records = RegistryLearningCandidateJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = RegistryLearningCandidateSummary(
        path=str(path),
        exists=path.exists(),
        total_learning_count=len(records),
        latest_learning_id=latest.learning_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_learning_status=latest.learning_status if latest else None,
        latest_learning_decision=latest.learning_decision if latest else None,
        latest_learning_score=latest.learning_score if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_feedback_candidate(profile: Path, match) -> RegistryLearningCandidateRecord:
    selected_skill = match.latent_suggested_skill if match else "skill_feedback_missing"
    return RegistryLearningCandidateRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_feedback_id=None,
        source_match_id=match.match_id if match else None,
        registry_status=match.registry_status if match else None,
        observed_outcome=None,
        success_count=0,
        failure_count=0,
        blocked_count=0,
        not_observed_count=0,
        learning_score=0.0,
        learning_status="blocked",
        learning_decision="learning_blocked",
        next_action="record_skill_outcome_feedback",
        reasons=["skill_outcome_feedback_missing"],
    )


def _candidate_from_feedback(profile: Path, feedback_records, match) -> RegistryLearningCandidateRecord:
    latest = feedback_records[-1]
    selected_skill = latest.selected_skill
    relevant = [record for record in feedback_records if record.selected_skill == selected_skill]
    success_count = _count(relevant, "success")
    failure_count = _count(relevant, "failure") + _count(relevant, "regression")
    blocked_count = _count(relevant, "blocked")
    not_observed_count = _count(relevant, "not_observed")
    learning_score = _learning_score(success_count, failure_count, not_observed_count)
    status, decision, next_action, reasons = _learning_decision(
        learning_score,
        latest,
        match,
    )
    return RegistryLearningCandidateRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_feedback_id=latest.feedback_id,
        source_match_id=match.match_id if match else None,
        registry_status=match.registry_status if match else None,
        observed_outcome=latest.observed_outcome,
        success_count=success_count,
        failure_count=failure_count,
        blocked_count=blocked_count,
        not_observed_count=not_observed_count,
        learning_score=learning_score,
        learning_status=status,
        learning_decision=decision,
        next_action=next_action,
        reasons=reasons,
    )


def _count(records, outcome: str) -> int:
    return sum(1 for record in records if record.observed_outcome == outcome)


def _learning_score(success_count: int, failure_count: int, not_observed_count: int) -> float:
    denominator = max(success_count + failure_count + not_observed_count, 1)
    raw = (success_count - failure_count) / denominator
    return round(max(raw, 0.0), 4)


def _learning_decision(score: float, latest, match):
    if latest.observed_outcome != "success":
        return (
            "watch",
            "learning_hold",
            latest.next_action,
            ["latest_outcome_not_success"],
        )
    if match and match.registry_status == "fallback" and score >= 0.8:
        return (
            "ready",
            "learning_ready",
            "prepare_skill_registry_update_proposal",
            ["successful_fallback_skill_candidate"],
        )
    if score >= 0.8:
        return (
            "ready",
            "learning_ready",
            "prepare_skill_confidence_update_proposal",
            ["successful_registered_skill_candidate"],
        )
    return (
        "watch",
        "learning_watch",
        "collect_more_skill_outcomes",
        ["insufficient_success_evidence"],
    )
