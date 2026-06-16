import pytest

from hex_cortex.memory.confidence import (
    MemoryConfidencePlanner,
    MemoryConfidenceSaturationState,
)
from hex_cortex.memory.schemas import MemoryRecord


def test_memory_confidence_plan_prioritizes_low_confidence_and_never_confirmed() -> None:
    low = MemoryRecord(title="low", body="body", confidence=0.4, access_count=0)
    medium = MemoryRecord(title="medium", body="body", confidence=0.6, access_count=1)
    strong = MemoryRecord(title="strong", body="body", confidence=0.9, access_count=3)

    plan = MemoryConfidencePlanner(confidence_floor=0.7).plan(
        [strong, medium, low],
        limit=5,
    )

    assert plan.total_memory_count == 3
    assert plan.visible_memory_count == 3
    assert plan.saturation_threshold == 0.7
    assert plan.saturated_memory_count == 1
    assert plan.unsaturated_memory_count == 2
    assert plan.candidate_count == 2
    assert [candidate.memory_id for candidate in plan.candidates] == [
        low.memory_id,
        medium.memory_id,
    ]
    assert plan.candidates[0].saturation_state == (
        MemoryConfidenceSaturationState.NEEDS_CONFIRMATION
    )
    assert plan.candidates[0].reasons == [
        "confidence_below_floor",
        "never_confirmed",
    ]


def test_memory_confidence_plan_respects_limit_and_ignores_hidden_memory() -> None:
    hidden = MemoryRecord(title="hidden", body="body", confidence=0.1, visible=False)
    first = MemoryRecord(title="first", body="body", confidence=0.5)
    second = MemoryRecord(title="second", body="body", confidence=0.5)

    plan = MemoryConfidencePlanner().plan([hidden, first, second], limit=1)

    assert plan.total_memory_count == 3
    assert plan.visible_memory_count == 2
    assert plan.candidate_count == 1
    assert plan.candidates[0].memory_id in {first.memory_id, second.memory_id}
    assert plan.candidates[0].memory_id != hidden.memory_id
    assert MemoryConfidencePlanner().saturation_state(hidden) == (
        MemoryConfidenceSaturationState.HIDDEN
    )


def test_memory_confidence_plan_excludes_saturated_memory() -> None:
    saturated = MemoryRecord(
        title="saturated",
        body="body",
        confidence=0.7,
        access_count=1,
    )
    never_confirmed = MemoryRecord(
        title="never",
        body="body",
        confidence=0.9,
        access_count=0,
    )

    planner = MemoryConfidencePlanner(confidence_floor=0.7)
    plan = planner.plan([saturated, never_confirmed], limit=5)

    assert planner.saturation_state(saturated) == (
        MemoryConfidenceSaturationState.CONFIDENCE_SATURATED
    )
    assert planner.saturation_state(never_confirmed) == (
        MemoryConfidenceSaturationState.NEEDS_CONFIRMATION
    )
    assert plan.saturated_memory_count == 1
    assert plan.unsaturated_memory_count == 1
    assert plan.candidate_count == 1
    assert plan.candidates[0].memory_id == never_confirmed.memory_id
    assert plan.candidates[0].reasons == ["never_confirmed"]


def test_memory_confidence_plan_rejects_non_positive_limit() -> None:
    with pytest.raises(ValueError, match="plan limit must be positive"):
        MemoryConfidencePlanner().plan([], limit=0)
