from hex_cortex.memory.index_hydrator import MemoryIndexHydrator
from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import MemoryRecord


def make_memory(title: str, body: str, visible: bool = True) -> MemoryRecord:
    return MemoryRecord(
        title=title,
        body=body,
        tags=["retrieval"],
        source_event_ids=["evt_1"],
        confidence=0.85,
        visible=visible,
    )


def test_memory_index_hydrator_converts_memory_to_index_entry() -> None:
    memory = make_memory("Index-first rule", "Use compact lexical search first.")

    entry = MemoryIndexHydrator.to_index_entry(memory)

    assert entry.entry_id == memory.memory_id
    assert entry.path == f"memory://{memory.memory_id}"
    assert entry.title == memory.title
    assert entry.text == memory.body
    assert "memory" in entry.tags
    assert entry.metadata["memory_id"] == memory.memory_id


def test_memory_index_hydrator_adds_visible_memories_to_index() -> None:
    index = LocalKnowledgeIndex()
    visible = make_memory("Visible", "Find me later.")
    hidden = make_memory("Hidden", "Do not index.", visible=False)

    count = MemoryIndexHydrator(index).hydrate([visible, hidden])

    assert count == 1
    assert [entry.entry_id for entry in index.entries] == [visible.memory_id]


def test_memory_index_hydrator_supports_exact_retrieval() -> None:
    index = LocalKnowledgeIndex()
    memory = make_memory("Retrieval memory", "HEX-CORTEX should hydrate memories.")
    MemoryIndexHydrator(index).hydrate([memory])

    hits = index.exact_search("hydrate memories")

    assert [hit.entry_id for hit in hits] == [memory.memory_id]


def test_memory_index_hydrator_supports_lexical_retrieval() -> None:
    index = LocalKnowledgeIndex()
    memory = make_memory("Replay memory", "Compressed replay memories are searchable.")
    MemoryIndexHydrator(index).hydrate([memory])

    hits = index.lexical_scores("searchable replay")

    assert hits
    assert hits[0][0].entry_id == memory.memory_id
