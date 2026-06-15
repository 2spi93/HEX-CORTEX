"""Hydrate the local knowledge index from persisted memory records."""

from __future__ import annotations

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import IndexEntry, MemoryRecord


class MemoryIndexHydrator:
    """Convert visible memory records into local index entries."""

    def __init__(self, index: LocalKnowledgeIndex) -> None:
        self.index = index

    def hydrate(self, memories: list[MemoryRecord]) -> int:
        """Add visible memories to the index and return the number added."""

        count = 0
        for memory in memories:
            if not memory.visible:
                continue
            self.index.add_entry(self.to_index_entry(memory))
            count += 1
        return count

    @staticmethod
    def to_index_entry(memory: MemoryRecord) -> IndexEntry:
        """Convert one memory record into an index entry."""

        return IndexEntry(
            entry_id=memory.memory_id,
            path=f"memory://{memory.memory_id}",
            title=memory.title,
            text=memory.body,
            tags=["memory", *memory.tags],
            metadata={
                "source": "LocalMemoryJsonlStore",
                "memory_id": memory.memory_id,
                "source_event_ids": memory.source_event_ids,
                "confidence": memory.confidence,
                "sensitivity": memory.sensitivity.value,
            },
        )
