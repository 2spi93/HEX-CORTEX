from hex_cortex.evolver.pruning import (
    PruningAction,
    PruningBatchReport,
    PruningDecision,
)
from hex_cortex.memory.pruning_application import MemoryPruningApplication
from hex_cortex.memory.schemas import MemoryRecord


def make_memory(confidence: float = 0.8, deletable: bool = True) -> MemoryRecord:
    return MemoryRecord(
        title="Memory",
        body="Compressed memory body.",
        confidence=confidence,
        deletable=deletable,
    )


def make_decision(memory: MemoryRecord, action: PruningAction) -> PruningDecision:
    return PruningDecision(
        target_type="memory",
        target_id=memory.memory_id,
        action=action,
        reason=f"test_{action.value}",
        score=memory.confidence,
    )


def test_memory_pruning_application_dry_run_does_not_mutate_visibility() -> None:
    memory = make_memory(confidence=0.1)
    report = PruningBatchReport(decisions=[make_decision(memory, PruningAction.ARCHIVE)])

    result = MemoryPruningApplication([memory]).apply(report, dry_run=True)

    assert result.dry_run is True
    assert result.changed_count == 1
    assert result.visible_before == 1
    assert result.visible_after == 1
    assert result.memories[0].visible is True
    assert memory.visible is True
    assert result.changes[0].after_visible is False


def test_memory_pruning_application_apply_archives_visible_memory() -> None:
    memory = make_memory(confidence=0.1)
    report = PruningBatchReport(decisions=[make_decision(memory, PruningAction.ARCHIVE)])

    result = MemoryPruningApplication([memory]).apply(report, dry_run=False)

    assert result.dry_run is False
    assert result.changed_count == 1
    assert result.visible_before == 1
    assert result.visible_after == 0
    assert result.memories[0].visible is False
    assert memory.visible is True


def test_memory_pruning_application_keeps_non_deletable_memory_visible() -> None:
    memory = make_memory(confidence=0.1, deletable=False)
    report = PruningBatchReport(decisions=[make_decision(memory, PruningAction.ARCHIVE)])

    result = MemoryPruningApplication([memory]).apply(report, dry_run=False)

    assert result.changed_count == 0
    assert result.visible_after == 1
    assert result.memories[0].visible is True


def test_memory_pruning_application_degrade_is_non_destructive() -> None:
    memory = make_memory(confidence=0.4)
    report = PruningBatchReport(decisions=[make_decision(memory, PruningAction.DEGRADE)])

    result = MemoryPruningApplication([memory]).apply(report, dry_run=False)

    assert result.changed_count == 0
    assert result.visible_after == 1
    assert result.memories[0].visible is True


def test_memory_pruning_application_ignores_non_memory_decisions() -> None:
    memory = make_memory(confidence=0.1)
    report = PruningBatchReport(
        decisions=[
            PruningDecision(
                target_type="skill",
                target_id="skill_1",
                action=PruningAction.ARCHIVE,
                reason="skill_low_confidence",
                score=0.1,
            )
        ]
    )

    result = MemoryPruningApplication([memory]).apply(report, dry_run=False)

    assert result.changed_count == 0
    assert result.changes == []
    assert result.visible_after == 1
