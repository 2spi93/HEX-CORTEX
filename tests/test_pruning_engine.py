from hex_cortex.evolver.pruning import PruningAction, PruningEngine
from hex_cortex.evolver.schemas import CellHealth, SkillRecord, SkillStatus
from hex_cortex.memory.schemas import MemoryRecord, TacitRule


def test_pruning_engine_archives_low_confidence_deletable_memory() -> None:
    engine = PruningEngine()
    memory = MemoryRecord(
        title="Weak memory",
        body="Low confidence compressed memory.",
        confidence=0.1,
    )

    decision = engine.decide_memory(memory)

    assert decision.action == PruningAction.ARCHIVE
    assert decision.reason == "memory_confidence_below_archive_threshold"


def test_pruning_engine_keeps_non_deletable_memory() -> None:
    engine = PruningEngine()
    memory = MemoryRecord(
        title="Protected memory",
        body="Do not archive this memory.",
        confidence=0.1,
        deletable=False,
    )

    decision = engine.decide_memory(memory)

    assert decision.action == PruningAction.KEEP
    assert decision.reason == "memory_not_deletable"


def test_pruning_engine_degrades_rule_with_high_failure_ratio() -> None:
    engine = PruningEngine()
    rule = TacitRule(
        claim="Use this fragile rule.",
        source_event_ids=["evt_1"],
        success_count=1,
        failure_count=2,
        confidence=0.4,
    )

    decision = engine.decide_rule(rule)

    assert decision.action == PruningAction.DEGRADE
    assert decision.reason == "rule_failure_ratio_too_high"


def test_pruning_engine_archives_weak_skill() -> None:
    engine = PruningEngine()
    skill = SkillRecord(
        name="weak skill",
        description="A workflow that stopped working.",
        confidence=0.1,
        status=SkillStatus.ACTIVE,
    )

    decision = engine.decide_skill(skill)

    assert decision.action == PruningAction.ARCHIVE
    assert decision.reason == "skill_confidence_below_archive_threshold"


def test_pruning_engine_quarantines_unstable_cell() -> None:
    engine = PruningEngine()
    health = CellHealth(
        cell_id="unstable_cell",
        trust_score=0.2,
        failure_count=3,
    )

    decision = engine.decide_cell(health)

    assert decision.action == PruningAction.QUARANTINE
    assert decision.reason == "cell_trust_below_quarantine_threshold"


def test_pruning_engine_degrades_cell_requiring_double_check() -> None:
    engine = PruningEngine()
    health = CellHealth(
        cell_id="critic_cell",
        trust_score=0.6,
        requires_double_check=True,
    )

    decision = engine.decide_cell(health)

    assert decision.action == PruningAction.DEGRADE
    assert decision.reason == "cell_requires_double_check"


def test_pruning_engine_batch_counts_decisions() -> None:
    engine = PruningEngine()
    memory = MemoryRecord(title="m", body="b", confidence=0.1)
    skill = SkillRecord(name="s", description="d", confidence=0.9, status=SkillStatus.ACTIVE)
    cell = CellHealth(cell_id="c", trust_score=0.2, failure_count=3)

    report = engine.decide_batch(memories=[memory], skills=[skill], cells=[cell])

    assert report.archive_count == 1
    assert report.keep_count == 1
    assert report.quarantine_count == 1
    assert report.degrade_count == 0
