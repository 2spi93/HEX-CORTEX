"""Profile confidence planning helpers."""

from __future__ import annotations

from pathlib import Path

from hex_cortex.memory.confidence import MemoryConfidencePlanner
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore


def profile_memory_confidence_plan(
    profile: Path,
    *,
    limit: int = 3,
    saturation_threshold: float = 0.7,
) -> dict[str, object]:
    """Return next memory confidence candidates for a profile."""

    memory_path = profile / "memory.jsonl"
    memories = LocalMemoryJsonlStore(memory_path).load()
    plan = MemoryConfidencePlanner(
        confidence_floor=saturation_threshold,
    ).plan(memories, limit=limit)
    return {
        "plan_type": "memory_confidence_profile",
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "limit": limit,
        "total_memory_count": plan.total_memory_count,
        "visible_memory_count": plan.visible_memory_count,
        "saturation_threshold": plan.saturation_threshold,
        "saturated_memory_count": plan.saturated_memory_count,
        "unsaturated_memory_count": plan.unsaturated_memory_count,
        "candidate_count": plan.candidate_count,
        "candidates": [candidate.model_dump(mode="json") for candidate in plan.candidates],
    }
