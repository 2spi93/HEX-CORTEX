import pytest

from hex_cortex.core.cell_registry import CellRegistry
from hex_cortex.core.cortex_pipeline import CortexPipeline
from hex_cortex.core.schemas import CellRole, CellSpec, Task
from hex_cortex.evolver.schemas import SkillRecord, SkillStatus
from hex_cortex.evolver.skill_library import SkillLibrary
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import IndexEntry, RetrievalMethod
from hex_cortex.replay.schemas import ReplayStatus


def test_cortex_pipeline_runs_complete_local_pass() -> None:
    pipeline = CortexPipeline()
    task = Task(
        content="Classify this local task",
        domain_hints=["intent"],
        novelty=0.2,
        risk=0.2,
        uncertainty=0.2,
    )

    result = pipeline.run(task)

    assert result.task_id == task.task_id
    assert result.clock_completed is True
    assert result.routing_decision.selected_cells
    assert result.replay_report.status == ReplayStatus.CONSOLIDATED
    assert result.pruning_report.decisions
    assert pipeline.spine.verify_integrity().ok is True


def test_cortex_pipeline_retrieves_memory_and_matches_skill() -> None:
    index = LocalKnowledgeIndex(
        [
            IndexEntry(
                path="memory/retrieval.md",
                title="Retrieval memory",
                text="HEX-CORTEX should use index-first retrieval.",
                tags=["memory"],
            )
        ]
    )
    skill = SkillRecord(
        name="memory retrieval workflow",
        description="Use local index before broader retrieval.",
        trigger_tags=["memory"],
        workflow_steps=["search index", "bound context", "verify lineage"],
        confidence=0.9,
        status=SkillStatus.ACTIVE,
    )
    pipeline = CortexPipeline(
        index=index,
        skill_library=SkillLibrary([skill]),
    )
    task = Task(
        content="index-first retrieval",
        domain_hints=["memory"],
        novelty=0.5,
        risk=0.4,
        uncertainty=0.4,
    )

    result = pipeline.run(task)

    assert result.context_packet.method == RetrievalMethod.EXACT
    assert [matched.skill_id for matched in result.matched_skills] == [skill.skill_id]
    assert "memory_cell" in result.routing_decision.selected_cells


def test_cortex_pipeline_writes_expected_spine_events() -> None:
    pipeline = CortexPipeline()
    task = Task(content="Trace the local cortex pipeline", domain_hints=["logic"])

    pipeline.run(task)
    event_types = [event.event_type for event in pipeline.spine.events_for_task(task.task_id)]

    assert "task.received" in event_types
    assert "retrieval.packet" in event_types
    assert "skill.lookup" in event_types
    assert "routing.decision" in event_types
    assert "clock.completed" in event_types
    assert "replay.report" in event_types
    assert "pruning.report" in event_types


def test_cortex_pipeline_fails_when_no_healthy_cell_exists() -> None:
    registry = CellRegistry(
        [
            CellSpec(
                cell_id="unstable_cell",
                role=CellRole.ACTION,
                domains=["action"],
            )
        ]
    )
    registry.record_failure("unstable_cell", "failure 1")
    registry.record_failure("unstable_cell", "failure 2")
    registry.record_failure("unstable_cell", "failure 3")
    pipeline = CortexPipeline(cell_registry=registry)
    task = Task(content="Route action safely", domain_hints=["action"])

    with pytest.raises(ValueError, match="registered cells"):
        pipeline.run(task)
