from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_controlled_skill_use import (
    CORTEX_CONTROLLED_SKILL_USE_FILENAME,
    CortexControlledSkillUseJsonlStore,
    CortexControlledSkillUseRecord,
)
from hex_cortex.memory.cortex_guidance_outcome import (
    CORTEX_GUIDANCE_OUTCOME_FILENAME,
    CortexGuidanceOutcomeJsonlStore,
    CortexGuidanceOutcomeRecord,
)
from hex_cortex.memory.cortex_guidance_quality_score import (
    CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME,
    CortexGuidanceQualityScoreJsonlStore,
    CortexGuidanceQualityScoreRecord,
)
from hex_cortex.memory.cortex_loop_close_report import (
    CORTEX_LOOP_CLOSE_REPORT_FILENAME,
    CortexLoopCloseReportJsonlStore,
    CortexLoopCloseReportRecord,
)
from hex_cortex.memory.cortex_multi_skill_router import (
    CORTEX_MULTI_SKILL_ROUTER_FILENAME,
    CortexMultiSkillRouterJsonlStore,
    CortexMultiSkillRouterRecord,
)

CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME = "cortex-multi-skill-feedback-score.jsonl"


class CortexMultiSkillFeedbackScoreRecord(BaseModel):
    feedback_id: str = Field(default_factory=lambda: f"cortex_multi_skill_feedback_score_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_router_id: str | None
    source_router_hash: str | None
    source_use_id: str | None
    source_use_hash: str | None
    source_quality_score_hash: str | None
    source_outcome_id: str | None
    source_outcome_hash: str | None
    source_report_hash: str | None
    selected_skill_key: str | None
    selected_domain: str | None
    route_quality_score: float = Field(ge=0.0, le=1.0)
    skill_use_success_score: float = Field(ge=0.0, le=1.0)
    guidance_quality_score: float = Field(ge=0.0, le=1.0)
    outcome_score: float = Field(ge=0.0, le=1.0)
    stability_score: float = Field(ge=0.0, le=1.0)
    feedback_score: float = Field(ge=0.0, le=1.0)
    feedback_status: str
    feedback_decision: str
    feedback_allowed: bool
    next_action: str
    blockers: list[str]
    feedback_hash: str
    reasons: list[str]


class CortexMultiSkillFeedbackScoreJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMultiSkillFeedbackScoreRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMultiSkillFeedbackScoreRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex multi skill feedback score {line_number}") from exc
        return records

    def save(self, records: list[CortexMultiSkillFeedbackScoreRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_multi_skill_feedback_score(profile: Path) -> dict[str, object]:
    router = _latest_router(profile)
    use = _latest_use(profile)
    quality = _latest_quality(profile)
    outcome = _latest_outcome(profile)
    report = _latest_report(profile)
    record = _feedback_record(profile, router, use, quality, outcome, report)
    path = profile / CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME
    store = CortexMultiSkillFeedbackScoreJsonlStore(path)
    current = store.load()
    if record.source_router_hash and any(item.source_router_hash == record.source_router_hash for item in current):
        records: list[CortexMultiSkillFeedbackScoreRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "feedback_type": "cortex_multi_skill_feedback_score",
        "profile_path": str(profile),
        "feedback_path": str(path),
        "feedback_count": count,
        "feedback_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_multi_skill_feedback_scores(path: Path) -> dict[str, object]:
    records = CortexMultiSkillFeedbackScoreJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.feedback_allowed]
    return {
        "inspect_type": "cortex_multi_skill_feedback_score",
        "path": str(path),
        "exists": path.exists(),
        "total_feedback_count": len(records),
        "allowed_feedback_count": len(allowed),
        "latest_feedback_id": latest.feedback_id if latest else None,
        "latest_feedback_status": latest.feedback_status if latest else None,
        "latest_feedback_decision": latest.feedback_decision if latest else None,
        "latest_feedback_allowed": latest.feedback_allowed if latest else None,
        "latest_feedback_score": latest.feedback_score if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_selected_domain": latest.selected_domain if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_feedback_hash": latest.feedback_hash if latest else None,
    }


def _latest_router(profile: Path) -> CortexMultiSkillRouterRecord | None:
    records = CortexMultiSkillRouterJsonlStore(profile / CORTEX_MULTI_SKILL_ROUTER_FILENAME).load()
    return records[-1] if records else None


def _latest_use(profile: Path) -> CortexControlledSkillUseRecord | None:
    records = CortexControlledSkillUseJsonlStore(profile / CORTEX_CONTROLLED_SKILL_USE_FILENAME).load()
    return records[-1] if records else None


def _latest_quality(profile: Path) -> CortexGuidanceQualityScoreRecord | None:
    records = CortexGuidanceQualityScoreJsonlStore(profile / CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME).load()
    return records[-1] if records else None


def _latest_outcome(profile: Path) -> CortexGuidanceOutcomeRecord | None:
    records = CortexGuidanceOutcomeJsonlStore(profile / CORTEX_GUIDANCE_OUTCOME_FILENAME).load()
    return records[-1] if records else None


def _latest_report(profile: Path) -> CortexLoopCloseReportRecord | None:
    records = CortexLoopCloseReportJsonlStore(profile / CORTEX_LOOP_CLOSE_REPORT_FILENAME).load()
    return records[-1] if records else None


def _feedback_record(
    profile: Path,
    router: CortexMultiSkillRouterRecord | None,
    use: CortexControlledSkillUseRecord | None,
    quality: CortexGuidanceQualityScoreRecord | None,
    outcome: CortexGuidanceOutcomeRecord | None,
    report: CortexLoopCloseReportRecord | None,
) -> CortexMultiSkillFeedbackScoreRecord:
    blockers = _blockers(router, use, quality, outcome, report)
    selected_skill_key = router.selected_skill_key if router else None
    selected_domain = router.selected_domain if router else None
    route_quality_score = router.selected_route_score if router and router.router_allowed else 0.0
    skill_use_success_score = _skill_use_score(router, use)
    guidance_quality_score = quality.quality_score if quality and quality.score_allowed else 0.0
    outcome_score = _outcome_score(outcome)
    stability_score = _stability_score(router, use, quality, outcome, report)
    feedback_score = round(
        (
            route_quality_score
            + skill_use_success_score
            + guidance_quality_score
            + outcome_score
            + stability_score
        )
        / 5.0,
        4,
    )
    if feedback_score < 0.80 and "feedback_score_below_threshold" not in blockers:
        blockers.append("feedback_score_below_threshold")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "multi_skill_feedback_ready" if allowed else "multi_skill_feedback_blocked"
    next_action = "build_skill_usage_history" if allowed else "repair_multi_skill_feedback_score"
    reasons = ["route_ready", "skill_use_successful", "guidance_quality_ready", "outcome_accepted", "closeout_stable"] if allowed else blockers
    feedback_hash = _hash(
        str(profile),
        router.router_hash if router else "missing_router",
        use.use_hash if use else "missing_use",
        quality.score_hash if quality else "missing_quality",
        outcome.outcome_hash if outcome else "missing_outcome",
        report.report_hash if report else "missing_report",
        str(feedback_score),
        decision,
        next_action,
        *reasons,
    )
    return CortexMultiSkillFeedbackScoreRecord(
        profile_path=str(profile),
        source_router_id=router.router_id if router else None,
        source_router_hash=router.router_hash if router else None,
        source_use_id=use.use_id if use else None,
        source_use_hash=use.use_hash if use else None,
        source_quality_score_hash=quality.score_hash if quality else None,
        source_outcome_id=outcome.outcome_id if outcome else None,
        source_outcome_hash=outcome.outcome_hash if outcome else None,
        source_report_hash=report.report_hash if report else None,
        selected_skill_key=selected_skill_key,
        selected_domain=selected_domain,
        route_quality_score=route_quality_score,
        skill_use_success_score=skill_use_success_score,
        guidance_quality_score=guidance_quality_score,
        outcome_score=outcome_score,
        stability_score=stability_score,
        feedback_score=feedback_score,
        feedback_status=status,
        feedback_decision=decision,
        feedback_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        feedback_hash=feedback_hash,
        reasons=reasons,
    )


def _blockers(router, use, quality, outcome, report) -> list[str]:
    blockers = []
    if router is None:
        blockers.append("missing_multi_skill_router")
    elif router.router_allowed is not True:
        blockers.append("multi_skill_router_not_allowed")
    elif router.next_action != "prepare_local_compact_expert_adapter":
        blockers.append("router_not_waiting_feedback_context")
    if use is None:
        blockers.append("missing_controlled_skill_use")
    elif use.use_allowed is not True:
        blockers.append("controlled_skill_use_not_allowed")
    if quality is None:
        blockers.append("missing_guidance_quality_score")
    elif quality.score_allowed is not True:
        blockers.append("guidance_quality_score_not_allowed")
    if outcome is None:
        blockers.append("missing_guidance_outcome")
    elif outcome.outcome_allowed is not True:
        blockers.append("guidance_outcome_not_allowed")
    if report is None:
        blockers.append("missing_loop_close_report")
    elif report.report_allowed is not True:
        blockers.append("loop_close_report_not_allowed")
    return blockers


def _skill_use_score(router: CortexMultiSkillRouterRecord | None, use: CortexControlledSkillUseRecord | None) -> float:
    if router is None or use is None or use.use_allowed is not True:
        return 0.0
    if use.selected_skill_key == router.selected_skill_key:
        return 1.0
    if use.selected_domain == router.selected_domain:
        return 0.75
    return 0.25


def _outcome_score(outcome: CortexGuidanceOutcomeRecord | None) -> float:
    if outcome is None or outcome.outcome_allowed is not True:
        return 0.0
    return outcome.usefulness_score


def _stability_score(router, use, quality, outcome, report) -> float:
    if not all([router, use, quality, outcome, report]):
        return 0.0
    skill_keys = {
        value
        for value in [
            router.selected_skill_key,
            use.selected_skill_key,
            quality.selected_skill_key,
            outcome.selected_skill_key,
            report.selected_skill_key,
        ]
        if value
    }
    closeout_ok = report.report_allowed is True and report.report_status == "complete"
    if len(skill_keys) == 1 and closeout_ok:
        return 1.0
    if closeout_ok:
        return 0.65
    return 0.25


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
