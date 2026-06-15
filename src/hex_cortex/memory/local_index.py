"""Local knowledge index for HEX-CORTEX.

The index is intentionally simple in v0.1:
- in-memory entries
- deterministic tokenization
- no model dependency
- no vector store dependency
"""

from __future__ import annotations

import re
from collections import Counter
from math import log

from hex_cortex.memory.schemas import IndexEntry

_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    """Tokenize text for lightweight lexical retrieval."""

    return [token.lower() for token in _TOKEN_RE.findall(text)]


class LocalKnowledgeIndex:
    """Small local index used before any expensive semantic retrieval."""

    def __init__(self, entries: list[IndexEntry] | None = None) -> None:
        self._entries: dict[str, IndexEntry] = {}
        self._term_frequencies: dict[str, Counter[str]] = {}
        self._document_frequency: Counter[str] = Counter()
        self._dirty = True

        for entry in entries or []:
            self.add_entry(entry)

    @property
    def entries(self) -> list[IndexEntry]:
        return list(self._entries.values())

    def add_entry(self, entry: IndexEntry) -> None:
        self._entries[entry.entry_id] = entry
        self._dirty = True

    def remove_entry(self, entry_id: str) -> None:
        self._entries.pop(entry_id, None)
        self._dirty = True

    def exact_search(
        self,
        query: str,
        required_tags: list[str] | None = None,
    ) -> list[IndexEntry]:
        """Return entries containing the raw query string."""

        normalized_query = query.strip().lower()
        if not normalized_query:
            return []

        required = {tag.lower() for tag in required_tags or []}
        hits = []
        for entry in self._entries.values():
            if required and not required.issubset({tag.lower() for tag in entry.tags}):
                continue
            haystack = f"{entry.title}\n{entry.text}".lower()
            if normalized_query in haystack:
                hits.append(entry)
        return hits

    def lexical_scores(
        self,
        query: str,
        required_tags: list[str] | None = None,
    ) -> list[tuple[IndexEntry, float]]:
        """Score entries with a lightweight BM25-inspired lexical formula."""

        self._rebuild_if_needed()
        query_terms = tokenize(query)
        if not query_terms:
            return []

        required = {tag.lower() for tag in required_tags or []}
        total_docs = max(len(self._entries), 1)
        raw_scores: list[tuple[IndexEntry, float]] = []

        for entry_id, entry in self._entries.items():
            if required and not required.issubset({tag.lower() for tag in entry.tags}):
                continue

            term_frequency = self._term_frequencies.get(entry_id, Counter())
            if not term_frequency:
                continue

            score = 0.0
            for term in query_terms:
                tf = term_frequency.get(term, 0)
                if tf == 0:
                    continue
                df = self._document_frequency.get(term, 0)
                idf = log(1 + (total_docs - df + 0.5) / (df + 0.5))
                score += (tf / (tf + 1.5)) * idf

            if score > 0:
                raw_scores.append((entry, score))

        if not raw_scores:
            return []

        max_score = max(score for _entry, score in raw_scores)
        return [(entry, min(score / max_score, 1.0)) for entry, score in raw_scores]

    def _rebuild_if_needed(self) -> None:
        if not self._dirty:
            return

        self._term_frequencies = {}
        self._document_frequency = Counter()

        for entry_id, entry in self._entries.items():
            tokens = tokenize(f"{entry.title}\n{entry.text}\n{' '.join(entry.tags)}")
            frequencies = Counter(tokens)
            self._term_frequencies[entry_id] = frequencies
            self._document_frequency.update(frequencies.keys())

        self._dirty = False
