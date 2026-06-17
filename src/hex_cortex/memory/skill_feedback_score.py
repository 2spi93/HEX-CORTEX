"""Feedback-weighted skill score reports."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.registry_learning_candidate import (
    REGISTRY_LEARNING_FILENAME,
    RegistryLearningCandidateJsonlStore,
)
from hex_cortex.memory.skill_outcome_feedback import (
    SKILL_OUTCOME_FEEDBACK_FILENAME,
    SkillOutcomeFeedbackJsonlStore,
)

SKILL_FEEDBACK_SCORE_FILENAME = "skill-feedback-score.jsonl"


class SkillFeedbackScoreRecord(BaseModel):
    """One persisted feedback-weighted skill score."""

    score_id: str = Field(default_factory=lambda: f"skill_feedback_score_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    selected_skill: str
    source_learning_id: str | None
    feedback_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)
    not_observed_count: int = Field(ge=0)
    base_score: float = Field(ge=0.0, le=1.0)
    feedback_score: float = Field(ge=0.0, le=1.0)
    final_score: float = Field(ge=0.0, le=1.0)
    score_status: str
    score_decision: str
    next_action: str
    reasons: list[str]


class SkillFeedbackScoreSummary(BaseModel):
    """Summary of persisted feedback-weighted skill scores."""

    inspect_type: str = "skill_feedback_score"
    path: str
    exists: bool
    total_score_count: int = Field(ge=0)
    latest_score_id: str | None
    latest_selected_skill: str | None
    latest_score_status: str | None
    latest_score_decision: str | None
    latest_final_score: float | None
    latest_next_action: str | None


class SkillFeedbackScoreJsonlStore:
    """Persist feedback-weighted skill scores as JSON Lines."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[SkillFeedbackScoreRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(SkillFeedbackScoreRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(
                        f"invalid skill feedback score at line {line_number}"
                    ) from exc
        return records

    def save(self, records: list[SkillFeedbackScoreRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: SkillFeedbackScoreRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def build_skill_feedback_score(profile: Path) -> dict[str, object]:
    """Build a feedback-weighted skill score report."""

    feedback = SkillOutcomeFeedbackJsonlStore(
        profile / SKILL_OUTCOME_FEEDBACK_FILENAME
    ).load()
    learning = RegistryLearningCandidateJsonlStore(
        profile / REGISTRY_LEARNING_FILENAME
    ).load()
    if not feedback:
        record = _missing_feedback_score(profile, learning[-1] if learning else None)
    else:
        record = _score_from_sources(profile, feedback, learning[-1] if learning else None)
    path = profile / SKILL_FEEDBACK_SCORE_FILENAME
    count = SkillFeedbackScoreJsonlStore(path).append(record)
    return {
        "score_type": "skill_feedback_score",
        "profile_path": str(profile),
        "score_path": str(path),
        "score_count": count,
        "score_record": record.model_dump(mode="json"),
    }


def summarize_skill_feedback_scores(path: Path) -> dict[str, object]:
    records = SkillFeedbackScoreJsonlStore(path).load()
    latest = records[-1] if records else None
    summary = SkillFeedbackScoreSummary(
        path=str(path),
        exists=path.exists(),
        total_score_count=len(records),
        latest_score_id=latest.score_id if latest else None,
        latest_selected_skill=latest.selected_skill if latest else None,
        latest_score_status=latest.score_status if latest else None,
        latest_score_decision=latest.score_decision if latest else None,
        latest_final_score=latest.final_score if latest else None,
        latest_next_action=latest.next_action if latest else None,
    )
    return summary.model_dump(mode="json")


def _missing_feedback_score(profile: Path, learning) -> SkillFeedbackScoreRecord:
    selected_skill = learning.selected_skill if learning else "skill_feedback_missing"
    return SkillFeedbackScoreRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_learning_id=learning.learning_id if learning else None,
        feedback_count=0,
        success_count=0,
        failure_count=0,
        blocked_count=0,
        not_observed_count=0,
        base_score=0.0,
        feedback_score=0.0,
        final_score=0.0,
        score_status="blocked",
        score_decision="score_blocked",
        next_action="record_skill_outcome_feedback",
        reasons=["skill_outcome_feedback_missing"],
    )


def _score_from_sources(profile: Path, feedback, learning) -> SkillFeedbackScoreRecord:
    latest = feedback[-1]
    selected_skill = latest.selected_skill
    relevant = [record for record in feedback if record.selected_skill == selected_skill]
    counts = Counter(record.observed_outcome for record in relevant)
    success_count = counts.get("success", 0)
    failure_count = counts.get("failure", 0) + counts.get("regression", 0)
    blocked_count = counts.get("blocked", 0)
    not_observed_count = counts.get("not_observed", 0)
    base_score = learning.learning_score if learning else 0.0
    feedback_score = _feedback_score(success_count, failure_count, not_observed_count)
    final_score = round((0.6 * base_score) + (0.4 * feedback_score), 4)
    status, decision, next_action, reasons = _score_decision(final_score, latest)
    return SkillFeedbackScoreRecord(
        profile_path=str(profile),
        selected_skill=selected_skill,
        source_learning_id=learning.learning_id if learning else None,
        feedback_count=len(relevant),
        success_count=success_count,
        failure_count=failure_count,
        blocked_count=blocked_count,
        not_observed_count=not_observed_count,
        base_score=base_score,
        feedback_score=feedback_score,
        final_score=final_score,
        score_status=status,
        score_decision=decision,
        next_action=next_action,
        reasons=reasons,
    )


def _feedback_score(success_count: int, failure_count: int, not_observed_count: int) -> float:
    total = max(success_count + failure_count + not_observed_count, 1)
    raw = (success_count - failure_count) / total
    return round(max(raw, 0.0), 4)


def _score_decision(score: float, latest):
    if latest.observed_outcome != "success":
        return (
            "watch",
            "score_hold",
            latest.next_action,
            ["latest_outcome_not_success"],
        )
    if score >= 0.8:
        return (
            "ready",
            "score_ready",
            "prepare_operator_review",
            ["skill_feedback_score_ready"],
        )
    if score >= 0.5:
        return (
            "watch",
            "score_watch",
            "collect_more_skill_feedback",
            ["skill_feedback_score_needs_more_feedback"],
        )
    return (
        "blocked",
        "score_blocked",
        "repair_skill_feedback_inputs",
        ["skill_feedback_score_too_low"],
    )
