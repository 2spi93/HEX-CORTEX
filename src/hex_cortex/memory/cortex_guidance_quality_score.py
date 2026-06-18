from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_controlled_skill_guidance_renderer import (
    CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME,
    CortexControlledSkillGuidanceRendererJsonlStore,
    CortexControlledSkillGuidanceRendererRecord,
)
from hex_cortex.memory.cortex_guidance_outcome import (
    CORTEX_GUIDANCE_OUTCOME_FILENAME,
    CortexGuidanceOutcomeJsonlStore,
    CortexGuidanceOutcomeRecord,
)
from hex_cortex.memory.cortex_loop_close_report import (
    CORTEX_LOOP_CLOSE_REPORT_FILENAME,
    CortexLoopCloseReportJsonlStore,
    CortexLoopCloseReportRecord,
)

CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME = "cortex-guidance-quality-score.jsonl"


class CortexGuidanceQualityScoreRecord(BaseModel):
    score_id: str = Field(default_factory=lambda: f"cortex_guidance_quality_score_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_guidance_id: str | None
    source_guidance_hash: str | None
    source_outcome_id: str | None
    source_outcome_hash: str | None
    source_report_hash: str | None
    selected_skill_key: str | None
    safety_score: float = Field(ge=0.0, le=1.0)
    structure_score: float = Field(ge=0.0, le=1.0)
    usefulness_score: float = Field(ge=0.0, le=1.0)
    reuse_score: float = Field(ge=0.0, le=1.0)
    closeout_score: float = Field(ge=0.0, le=1.0)
    quality_score: float = Field(ge=0.0, le=1.0)
    score_status: str
    score_decision: str
    score_allowed: bool
    next_action: str
    blockers: list[str]
    score_hash: str
    reasons: list[str]


class CortexGuidanceQualityScoreJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexGuidanceQualityScoreRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexGuidanceQualityScoreRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex guidance quality score {line_number}") from exc
        return records

    def save(self, records: list[CortexGuidanceQualityScoreRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_guidance_quality_score(profile: Path) -> dict[str, object]:
    guidance = _latest_guidance(profile)
    outcome = _latest_outcome(profile)
    report = _latest_report(profile)
    record = _score_record(profile, guidance, outcome, report)
    path = profile / CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME
    store = CortexGuidanceQualityScoreJsonlStore(path)
    current = store.load()
    if record.source_guidance_hash and any(item.source_guidance_hash == record.source_guidance_hash for item in current):
        records: list[CortexGuidanceQualityScoreRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "score_type": "cortex_guidance_quality_score",
        "profile_path": str(profile),
        "score_path": str(path),
        "score_count": count,
        "score_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_guidance_quality_scores(path: Path) -> dict[str, object]:
    records = CortexGuidanceQualityScoreJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.score_allowed]
    return {
        "inspect_type": "cortex_guidance_quality_score",
        "path": str(path),
        "exists": path.exists(),
        "total_score_count": len(records),
        "allowed_score_count": len(allowed),
        "latest_score_id": latest.score_id if latest else None,
        "latest_score_status": latest.score_status if latest else None,
        "latest_score_decision": latest.score_decision if latest else None,
        "latest_score_allowed": latest.score_allowed if latest else None,
        "latest_quality_score": latest.quality_score if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_score_hash": latest.score_hash if latest else None,
    }


def _latest_guidance(profile: Path) -> CortexControlledSkillGuidanceRendererRecord | None:
    records = CortexControlledSkillGuidanceRendererJsonlStore(profile / CORTEX_CONTROLLED_SKILL_GUIDANCE_RENDERER_FILENAME).load()
    return records[-1] if records else None


def _latest_outcome(profile: Path) -> CortexGuidanceOutcomeRecord | None:
    records = CortexGuidanceOutcomeJsonlStore(profile / CORTEX_GUIDANCE_OUTCOME_FILENAME).load()
    return records[-1] if records else None


def _latest_report(profile: Path) -> CortexLoopCloseReportRecord | None:
    records = CortexLoopCloseReportJsonlStore(profile / CORTEX_LOOP_CLOSE_REPORT_FILENAME).load()
    return records[-1] if records else None


def _score_record(
    profile: Path,
    guidance: CortexControlledSkillGuidanceRendererRecord | None,
    outcome: CortexGuidanceOutcomeRecord | None,
    report: CortexLoopCloseReportRecord | None,
) -> CortexGuidanceQualityScoreRecord:
    blockers = _blockers(guidance, outcome, report)
    safety_score = _safety_score(guidance)
    structure_score = _structure_score(guidance)
    usefulness_score = outcome.usefulness_score if outcome else 0.0
    reuse_score = _reuse_score(guidance)
    closeout_score = 1.0 if report and report.report_allowed and report.report_status == "complete" else 0.0
    quality_score = round((safety_score + structure_score + usefulness_score + reuse_score + closeout_score) / 5.0, 4)
    if quality_score < 0.80:
        blockers.append("guidance_quality_below_threshold")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "guidance_quality_ready" if allowed else "guidance_quality_blocked"
    next_action = "route_multi_skill_candidate" if allowed else "repair_guidance_quality"
    reasons = ["guidance_safe", "guidance_useful", "loop_closed"] if allowed else blockers
    score_hash = _hash(
        str(profile),
        guidance.guidance_hash if guidance else "missing_guidance",
        outcome.outcome_hash if outcome else "missing_outcome",
        report.report_hash if report else "missing_report",
        str(quality_score),
        decision,
        next_action,
        *reasons,
    )
    return CortexGuidanceQualityScoreRecord(
        profile_path=str(profile),
        source_guidance_id=guidance.guidance_id if guidance else None,
        source_guidance_hash=guidance.guidance_hash if guidance else None,
        source_outcome_id=outcome.outcome_id if outcome else None,
        source_outcome_hash=outcome.outcome_hash if outcome else None,
        source_report_hash=report.report_hash if report else None,
        selected_skill_key=guidance.selected_skill_key if guidance else (outcome.selected_skill_key if outcome else None),
        safety_score=safety_score,
        structure_score=structure_score,
        usefulness_score=usefulness_score,
        reuse_score=reuse_score,
        closeout_score=closeout_score,
        quality_score=quality_score,
        score_status=status,
        score_decision=decision,
        score_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        score_hash=score_hash,
        reasons=reasons,
    )


def _blockers(guidance, outcome, report) -> list[str]:
    blockers = []
    if guidance is None:
        blockers.append("missing_guidance")
    elif guidance.guidance_allowed is not True:
        blockers.append("guidance_not_allowed")
    if outcome is None:
        blockers.append("missing_guidance_outcome")
    elif outcome.outcome_allowed is not True:
        blockers.append("guidance_outcome_not_allowed")
    if report is None:
        blockers.append("missing_loop_close_report")
    elif report.report_allowed is not True:
        blockers.append("loop_close_report_not_allowed")
    return blockers


def _safety_score(guidance: CortexControlledSkillGuidanceRendererRecord | None) -> float:
    if guidance is None:
        return 0.0
    text = " ".join([guidance.task_text or "", guidance.selected_reusable_rule or "", *guidance.guidance_steps]).lower()
    forbidden = set(guidance.forbidden_terms)
    leaked = [term for term in forbidden if f" {term} " in f" {text} "]
    allowed_mentions = {"deploy", "live", "trade", "order"}
    unsafe = [term for term in leaked if term not in allowed_mentions]
    return 1.0 if not unsafe else 0.25


def _structure_score(guidance: CortexControlledSkillGuidanceRendererRecord | None) -> float:
    if guidance is None:
        return 0.0
    steps = guidance.guidance_steps
    if len(steps) >= 5 and guidance.guidance_title and guidance.next_action == "record_guidance_receipt":
        return 1.0
    if len(steps) >= 3:
        return 0.75
    return 0.25


def _reuse_score(guidance: CortexControlledSkillGuidanceRendererRecord | None) -> float:
    if guidance is None:
        return 0.0
    if guidance.selected_skill_key and guidance.selected_reusable_rule and "reusable" in guidance.selected_reusable_rule.lower():
        return 1.0
    if guidance.selected_skill_key:
        return 0.75
    return 0.0


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
