from hex_cortex.memory.local_index import LocalKnowledgeIndex, tokenize
from hex_cortex.memory.retrieval_router import RetrievalRouter
from hex_cortex.memory.schemas import IndexEntry, RetrievalMethod, RetrievalQuery, RetrievalResult


def test_tokenize_handles_basic_french_terms() -> None:
    assert tokenize("Mémoire compressée, index-first!") == ["mémoire", "compressée", "index", "first"]


def test_retrieval_prefers_exact_match() -> None:
    index = LocalKnowledgeIndex(
        [
            IndexEntry(
                path="memory/main_index.md",
                title="Main index",
                text="HEX-CORTEX uses index-first retrieval before semantic fallback.",
                tags=["architecture"],
            ),
            IndexEntry(
                path="memory/noise.md",
                title="Noise",
                text="This note discusses unrelated runtime details.",
                tags=["noise"],
            ),
        ]
    )
    router = RetrievalRouter(index)

    packet = router.retrieve(RetrievalQuery(query="index-first retrieval"))

    assert packet.method == RetrievalMethod.EXACT
    assert packet.results[0].title == "Main index"
    assert "semantic fallback" in packet.context_text


def test_retrieval_uses_lexical_ranking_when_no_exact_match() -> None:
    index = LocalKnowledgeIndex(
        [
            IndexEntry(
                path="memory/compression.md",
                title="Memory compression",
                text="Compression turns raw events into reusable tacit knowledge.",
                tags=["memory"],
            ),
            IndexEntry(
                path="memory/action.md",
                title="Action control",
                text="Actions require a critic gate and a confidence threshold.",
                tags=["action"],
            ),
        ]
    )
    router = RetrievalRouter(index)

    packet = router.retrieve(
        RetrievalQuery(
            query="compress raw memory into knowledge",
            semantic_fallback_threshold=0.99,
        )
    )

    assert packet.method == RetrievalMethod.LEXICAL
    assert packet.results[0].title == "Memory compression"
    assert packet.results[0].score > 0


def test_retrieval_calls_semantic_fallback_when_lexical_score_is_weak() -> None:
    index = LocalKnowledgeIndex(
        [
            IndexEntry(
                path="memory/lexical.md",
                title="Lexical note",
                text="A small note about keyword routing.",
            )
        ]
    )

    def fallback(query: RetrievalQuery) -> list[RetrievalResult]:
        return [
            RetrievalResult(
                entry_id="semantic_1",
                path="semantic://world-model",
                title="World model semantic hit",
                snippet=f"Semantic fallback answered: {query.query}",
                score=0.91,
                method=RetrievalMethod.SEMANTIC_FALLBACK,
            )
        ]

    router = RetrievalRouter(index, semantic_fallback=fallback)
    packet = router.retrieve(
        RetrievalQuery(
            query="latent prediction surprise",
            semantic_fallback_threshold=0.9,
        )
    )

    assert packet.method == RetrievalMethod.SEMANTIC_FALLBACK
    assert packet.results[0].path == "semantic://world-model"


def test_context_packet_respects_character_budget() -> None:
    index = LocalKnowledgeIndex(
        [
            IndexEntry(
                path="memory/long.md",
                title="Long memory",
                text="memory " * 500,
            )
        ]
    )
    router = RetrievalRouter(index)

    packet = router.retrieve(RetrievalQuery(query="memory", max_context_chars=256))

    assert packet.total_chars == 256
    assert packet.truncated is True
    assert len(packet.context_text) == 256
