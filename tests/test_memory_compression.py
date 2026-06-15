import pytest

from hex_cortex.memory.compression import MemoryCompressionSpine
from hex_cortex.memory.schemas import ReplayOutcome, TacitRule


def test_compress_successful_episode_into_memory_record() -> None:
    spine = MemoryCompressionSpine()
    episode = spine.summarize_episode(
        task_id="task_1",
        goal="design memory retrieval architecture",
        active_cells=["RetrievalRouter", "CriticCell", "ActionCell"],
        observations=["lexical retrieval reduced context size"],
        used_memory_ids=["mem_1"],
        outcome=ReplayOutcome.SUCCESS,
        confidence=0.82,
    )

    compression = spine.compress_episode(episode, source_event_ids=["evt_1", "evt_2"])
    memory = spine.to_memory_record(compression)

    assert compression.source_episode_id == episode.episode_id
    assert compression.extracted_rules
    assert "RetrievalRouter" in compression.summary
    assert memory.source_event_ids == ["evt_1", "evt_2"]
    assert "tacit-rule" in memory.tags
    assert memory.confidence == 0.82


def test_compression_requires_source_lineage() -> None:
    spine = MemoryCompressionSpine()
    episode = spine.summarize_episode(
        task_id="task_2",
        goal="test lineage",
        active_cells=["CriticCell"],
    )

    with pytest.raises(ValueError, match="source_event_ids"):
        spine.compress_episode(episode, source_event_ids=[])


def test_error_episode_creates_critic_rule() -> None:
    spine = MemoryCompressionSpine()
    episode = spine.summarize_episode(
        task_id="task_3",
        goal="execute risky action",
        active_cells=["ActionCell"],
        errors=["action executed without review"],
        outcome=ReplayOutcome.FAILURE,
        confidence=0.4,
    )

    compression = spine.compress_episode(episode, source_event_ids=["evt_failure"])

    assert len(compression.extracted_rules) == 1
    rule = compression.extracted_rules[0]
    assert "CriticCell" in rule.claim
    assert rule.failure_count == 1
    assert rule.confidence == 0.55


def test_rule_confidence_updates_after_replay() -> None:
    spine = MemoryCompressionSpine()
    rule = TacitRule(
        claim="Use retrieval before deep reasoning.",
        source_event_ids=["evt_1"],
        success_count=1,
        failure_count=1,
        confidence=0.5,
    )

    updated = spine.update_rule_from_replay(rule, ReplayOutcome.SUCCESS)

    assert updated.success_count == 2
    assert updated.failure_count == 1
    assert updated.confidence == pytest.approx(0.6)
