from hex_cortex.memory.schemas import MemoryRecord, MemoryType


def test_memory_record_defaults_to_episode_type_and_access_metadata() -> None:
    memory = MemoryRecord(title="Episode", body="Compressed episode.")

    assert memory.memory_type == MemoryType.EPISODE
    assert memory.access_count == 0
    assert memory.last_accessed_at is None
    assert memory.supersedes_memory_ids == []
    assert memory.conflicts_with_memory_ids == []


def test_memory_record_accepts_specialized_type() -> None:
    memory = MemoryRecord(
        title="Preference",
        body="Operator prefers local-first workflows.",
        memory_type=MemoryType.OPERATOR_PREFERENCE,
    )

    assert memory.memory_type == MemoryType.OPERATOR_PREFERENCE
