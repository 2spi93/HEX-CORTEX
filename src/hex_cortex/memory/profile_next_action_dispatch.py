"""Dispatch the next cognitive action when profile readiness allows it."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from hex_cortex.cli import (
    _load_memory_index,
    _load_skill_library,
    _load_spine,
    _save_memory,
    _save_spine,
    resolve_profile_paths,
    summarize_result,
)
from hex_cortex.core.cortex_pipeline import CortexPipeline
from hex_cortex.core.schemas import Task
from hex_cortex.memory.profile_dispatch_history import record_profile_dispatch_history
from hex_cortex.memory.profile_next_action import inspect_profile_next_action


class ProfileNextActionDispatchReport(BaseModel):
    """Dispatch report for the next cognitive action."""

    dispatch_type: str = "profile_next_action_dispatch"
    profile_path: str
    status: str
    decision: str
    reason: str
    next_action: str
    next_reason: str
    dispatch_status: str
    dispatch_reason: str
    dispatch_id: str
    dispatch_history_count: int
    dispatch_history_path: str
    pipeline_result: dict[str, object] | None


def dispatch_profile_next_action(
    profile: Path,
    *,
    task_content: str = "Run local cortex pipeline after operator readiness allow.",
    domain_hints: list[str] | None = None,
    policy_limit: int = 6,
    policy_stability_window: int = 3,
    minimum_ready_score: float = 1.0,
) -> dict[str, object]:
    """Inspect the next action and execute it when it is dispatchable."""

    next_payload = inspect_profile_next_action(
        profile,
        policy_limit=policy_limit,
        policy_stability_window=policy_stability_window,
        minimum_ready_score=minimum_ready_score,
    )
    pipeline_result = None
    dispatch_status = "skipped"
    dispatch_reason = str(next_payload["next_reason"])
    if next_payload["next_action"] == "run_cortex_pipeline":
        pipeline_result = _run_cortex_pipeline(
            profile,
            task_content=task_content,
            domain_hints=domain_hints or ["operator", "next-action"],
        )
        dispatch_status = "executed"
        dispatch_reason = "cortex_pipeline_executed"
    base_report = {
        "profile_path": str(profile),
        "status": str(next_payload["status"]),
        "decision": str(next_payload["decision"]),
        "reason": str(next_payload["reason"]),
        "next_action": str(next_payload["next_action"]),
        "next_reason": str(next_payload["next_reason"]),
        "dispatch_status": dispatch_status,
        "dispatch_reason": dispatch_reason,
        "pipeline_result": pipeline_result,
    }
    history_payload = record_profile_dispatch_history(profile, base_report)
    dispatch_record = history_payload["dispatch_record"]
    report = ProfileNextActionDispatchReport(
        **base_report,
        dispatch_id=str(dispatch_record["dispatch_id"]),
        dispatch_history_count=int(history_payload["history_count"]),
        dispatch_history_path=str(history_payload["history_path"]),
    )
    return report.model_dump(mode="json")


def _run_cortex_pipeline(
    profile: Path,
    *,
    task_content: str,
    domain_hints: list[str],
) -> dict[str, object]:
    args = _ProfileArgs(profile=profile)
    paths = resolve_profile_paths(args)
    task = Task(
        content=task_content,
        domain_hints=domain_hints,
        novelty=0.4,
        risk=0.2,
        uncertainty=0.3,
    )
    spine = _load_spine(paths.spine_jsonl)
    index, hydrated_memory_count = _load_memory_index(paths.memory_jsonl)
    skill_library, hydrated_skill_count = _load_skill_library(paths.skills_jsonl)
    result = CortexPipeline(
        spine=spine,
        index=index,
        skill_library=skill_library,
    ).run(task)
    persisted_event_count = _save_spine(paths.spine_jsonl, spine)
    persisted_memory_count = _save_memory(paths.memory_jsonl, result.replay_report.memory)
    return summarize_result(
        result,
        persisted_event_count=persisted_event_count,
        persisted_memory_count=persisted_memory_count,
        hydrated_memory_count=hydrated_memory_count,
        hydrated_skill_count=hydrated_skill_count,
        profile_path=str(profile),
    )


class _ProfileArgs:
    def __init__(self, *, profile: Path) -> None:
        self.profile = profile
        self.spine_jsonl = None
        self.memory_jsonl = None
        self.skills_jsonl = None
