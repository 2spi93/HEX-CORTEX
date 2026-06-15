"""Retrieval router for HEX-CORTEX memory.

The router follows the v0.1 law:
exact search → lexical ranking → semantic fallback stub → bounded context packet.
"""

from __future__ import annotations

from collections.abc import Callable

from hex_cortex.memory.local_index import LocalKnowledgeIndex
from hex_cortex.memory.schemas import (
    ContextPacket,
    IndexEntry,
    RetrievalMethod,
    RetrievalQuery,
    RetrievalResult,
)

SemanticFallback = Callable[[RetrievalQuery], list[RetrievalResult]]


class RetrievalRouter:
    """Build bounded context packets from a local knowledge index."""

    def __init__(
        self,
        index: LocalKnowledgeIndex,
        semantic_fallback: SemanticFallback | None = None,
    ) -> None:
        self.index = index
        self.semantic_fallback = semantic_fallback

    def retrieve(self, query: RetrievalQuery) -> ContextPacket:
        exact_hits = self.index.exact_search(query.query, query.required_tags)
        if exact_hits:
            results = [
                self._result_from_entry(entry, score=1.0, method=RetrievalMethod.EXACT)
                for entry in exact_hits[: query.top_k]
            ]
            return self._packet(query, RetrievalMethod.EXACT, results)

        lexical_hits = sorted(
            self.index.lexical_scores(query.query, query.required_tags),
            key=lambda item: item[1],
            reverse=True,
        )
        lexical_results = [
            self._result_from_entry(entry, score=score, method=RetrievalMethod.LEXICAL)
            for entry, score in lexical_hits[: query.top_k]
        ]

        if lexical_results and lexical_results[0].score >= query.semantic_fallback_threshold:
            return self._packet(query, RetrievalMethod.LEXICAL, lexical_results)

        if self.semantic_fallback is not None:
            semantic_results = self.semantic_fallback(query)[: query.top_k]
            if semantic_results:
                return self._packet(query, RetrievalMethod.SEMANTIC_FALLBACK, semantic_results)

        if lexical_results:
            return self._packet(query, RetrievalMethod.LEXICAL, lexical_results)

        return ContextPacket(
            query=query.query,
            method=RetrievalMethod.EMPTY,
            results=[],
            context_text="",
            total_chars=0,
            truncated=False,
        )

    @staticmethod
    def _result_from_entry(entry: IndexEntry, score: float, method: RetrievalMethod) -> RetrievalResult:
        snippet = entry.text.strip().replace("\n", " ")
        if len(snippet) > 500:
            snippet = f"{snippet[:497]}..."

        return RetrievalResult(
            entry_id=entry.entry_id,
            path=entry.path,
            title=entry.title,
            snippet=snippet,
            score=score,
            method=method,
            metadata=entry.metadata,
        )

    @staticmethod
    def _packet(
        query: RetrievalQuery,
        method: RetrievalMethod,
        results: list[RetrievalResult],
    ) -> ContextPacket:
        chunks: list[str] = []
        total_chars = 0
        truncated = False

        for result in results:
            block = (
                f"[{result.title}]\n"
                f"path: {result.path}\n"
                f"score: {result.score:.3f}\n"
                f"method: {result.method.value}\n"
                f"{result.snippet}\n"
            )
            next_total = total_chars + len(block)
            if next_total > query.max_context_chars:
                remaining = max(query.max_context_chars - total_chars, 0)
                if remaining > 0:
                    chunks.append(block[:remaining])
                    total_chars += remaining
                truncated = True
                break

            chunks.append(block)
            total_chars = next_total

        return ContextPacket(
            query=query.query,
            method=method,
            results=results,
            context_text="\n---\n".join(chunks),
            total_chars=total_chars,
            truncated=truncated,
        )
