from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_LEARNING_EVENT_FILENAME = "cortex-learning-event.jsonl"
_VALID_OUTCOMES = {"success", "failure", "correction", "external_lesson", "reuse"}
_VALID_DOMAINS = {"coding", "general", "research", "ops", "architecture", "product"}
_VALID_SCOPES = {"self", "team", "external", "benchmark", "repo"}


class CortexLearningEventRecord(BaseModel):
    learning_id: str = Field(default_factory=lambda: f"cortex_learning_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    outcome: str
    domain: str
    scope: str
    source_ref: str | None = None
    problem: str
    action_taken: str
    result: str
    lesson: str
    reusable_rule: str
    confidence: float = Field(ge=0.0, le=1.0)
    promote_to_skill: bool
    event_status: str
    event_decision: str
    event_allowed: bool
    blockers: list[str]
    learning_hash: str
    reasons: list[str]


class CortexLearningEventJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexLearningEventRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexLearningEventRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex learning event {line_number}") from exc
        return records

    def save(self, records: list[CortexLearningEventRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: CortexLearningEventRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def record_cortex_learning_event(
    profile: Path,
    *,
    outcome: str,
    domain: str,
    scope: str,
    problem: str,
    action_taken: str,
    result: str,
    lesson: str,
    reusable_rule: str,
    confidence: float,
    source_ref: str | None = None,
) -> dict[str, object]:
    record = _event_record(
        profile=profile,
        outcome=outcome,
        domain=domain,
        scope=scope,
        problem=problem,
        action_taken=action_taken,
        result=result,
        lesson=lesson,
        reusable_rule=reusable_rule,
        confidence=confidence,
        source_ref=source_ref,
    )
    path = profile / CORTEX_LEARNING_EVENT_FILENAME
    count = CortexLearningEventJsonlStore(path).append(record)
    return {
        "learning_type": "cortex_learning_event",
        "profile_path": str(profile),
        "learning_path": str(path),
        "learning_count": count,
        "learning_record": record.model_dump(mode="json"),
    }


def summarize_cortex_learning_events(path: Path) -> dict[str, object]:
    records = CortexLearningEventJsonlStore(path).load()
    latest = records[-1] if records else None
    accepted = [record for record in records if record.event_allowed]
    promoted = [record for record in accepted if record.promote_to_skill]
    return {
        "inspect_type": "cortex_learning_event",
        "path": str(path),
        "exists": path.exists(),
        "total_learning_count": len(records),
        "accepted_learning_count": len(accepted),
        "promoted_skill_candidate_count": len(promoted),
        "latest_learning_id": latest.learning_id if latest else None,
        "latest_outcome": latest.outcome if latest else None,
        "latest_domain": latest.domain if latest else None,
        "latest_scope": latest.scope if latest else None,
        "latest_event_status": latest.event_status if latest else None,
        "latest_event_decision": latest.event_decision if latest else None,
        "latest_event_allowed": latest.event_allowed if latest else None,
        "latest_promote_to_skill": latest.promote_to_skill if latest else None,
        "latest_learning_hash": latest.learning_hash if latest else None,
    }


def _event_record(
    *,
    profile: Path,
    outcome: str,
    domain: str,
    scope: str,
    problem: str,
    action_taken: str,
    result: str,
    lesson: str,
    reusable_rule: str,
    confidence: float,
    source_ref: str | None,
) -> CortexLearningEventRecord:
    clean = {
        "outcome": outcome.strip().lower(),
        "domain": domain.strip().lower(),
        "scope": scope.strip().lower(),
        "problem": _clean(problem),
        "action_taken": _clean(action_taken),
        "result": _clean(result),
        "lesson": _clean(lesson),
        "reusable_rule": _clean(reusable_rule),
    }
    blockers = _blockers(clean, confidence)
    allowed = not blockers
    promote = allowed and confidence >= 0.75 and clean["outcome"] in {"success", "correction", "reuse", "external_lesson"}
    decision = "learning_event_accepted" if allowed else "learning_event_blocked"
    status = "accepted" if allowed else "blocked"
    reasons = ["learning_event_validated"] if allowed else blockers
    learning_hash = _hash(
        str(profile),
        clean["outcome"],
        clean["domain"],
        clean["scope"],
        source_ref or "none",
        clean["problem"],
        clean["action_taken"],
        clean["result"],
        clean["lesson"],
        clean["reusable_rule"],
        str(confidence),
        decision,
        *reasons,
    )
    return CortexLearningEventRecord(
        profile_path=str(profile),
        outcome=clean["outcome"],
        domain=clean["domain"],
        scope=clean["scope"],
        source_ref=source_ref,
        problem=clean["problem"],
        action_taken=clean["action_taken"],
        result=clean["result"],
        lesson=clean["lesson"],
        reusable_rule=clean["reusable_rule"],
        confidence=confidence,
        promote_to_skill=promote,
        event_status=status,
        event_decision=decision,
        event_allowed=allowed,
        blockers=blockers,
        learning_hash=learning_hash,
        reasons=reasons,
    )


def _blockers(clean: dict[str, str], confidence: float) -> list[str]:
    blockers = []
    if clean["outcome"] not in _VALID_OUTCOMES:
        blockers.append("invalid_outcome")
    if clean["domain"] not in _VALID_DOMAINS:
        blockers.append("invalid_domain")
    if clean["scope"] not in _VALID_SCOPES:
        blockers.append("invalid_scope")
    for field in ["problem", "action_taken", "result", "lesson", "reusable_rule"]:
        if len(clean[field]) < 8:
            blockers.append(f"{field}_too_short")
    if confidence < 0.0 or confidence > 1.0:
        blockers.append("confidence_out_of_range")
    return blockers


def _clean(value: str) -> str:
    return " ".join(value.strip().split())


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
