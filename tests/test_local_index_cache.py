"""Regression tests for LocalKnowledgeIndex precomputed caches."""

from __future__ import annotations

import math

import pytest

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import IndexEntry


def _entry(entry_id: str, title: str, text: str, tags: list[str]) -> IndexEntry:
    return IndexEntry(
        entry_id=entry_id,
        title=title,
        text=text,
        tags=tags,
        path=f"docs/{entry_id}.md",
    )


def test_exact_search_reflects_add_and_remove() -> None:
    index = LocalKnowledgeIndex()
    index.add_entry(_entry("a", "Routing Guide", "thalamic router budget", ["Core"]))

    assert len(index.exact_search("router")) == 1

    index.add_entry(_entry("b", "Router Notes", "router escalation", ["core"]))
    assert len(index.exact_search("router")) == 2
    assert len(index.exact_search("router", required_tags=["CORE"])) == 2

    index.remove_entry("a")
    hits = index.exact_search("router")
    assert [hit.entry_id for hit in hits] == ["b"]


def test_lexical_scores_stable_across_mutations() -> None:
    index = LocalKnowledgeIndex(
        [
            _entry("a", "Spine", "canonical spine hash chain", ["spine"]),
            _entry("b", "Replay", "replay consolidation engine", ["replay"]),
        ]
    )

    first = index.lexical_scores("spine hash")
    assert [entry.entry_id for entry, _score in first] == ["a"]
    assert first[0][1] == pytest.approx(1.0)

    # Repeated identical query must hit the IDF cache and stay identical.
    assert index.lexical_scores("spine hash") == first

    index.add_entry(_entry("c", "Spine Store", "spine jsonl store", ["spine"]))
    rescored = index.lexical_scores("spine hash")
    assert {entry.entry_id for entry, _score in rescored} == {"a", "c"}
    for _entry_obj, score in rescored:
        assert 0.0 < score <= 1.0
        assert math.isfinite(score)


def test_lexical_scores_filters_by_precomputed_tags() -> None:
    index = LocalKnowledgeIndex(
        [
            _entry("a", "Spine", "spine events", ["Spine", "Audit"]),
            _entry("b", "Spine Two", "spine events", ["replay"]),
        ]
    )

    scored = index.lexical_scores("spine", required_tags=["audit"])
    assert [entry.entry_id for entry, _score in scored] == ["a"]
