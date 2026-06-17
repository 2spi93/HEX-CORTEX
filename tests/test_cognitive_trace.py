from hex_cortex.memory.cognitive_trace import (
    CognitiveTraceJsonlStore,
    CognitiveTraceRecord,
    CognitiveTraceStep,
    summarize_cognitive_traces,
)


def test_cognitive_trace_store_summarizes_latest_trace(tmp_path) -> None:
    path = tmp_path / "trace.jsonl"
    record = CognitiveTraceRecord(
        profile_path="profile",
        source_type="test",
        status="watch",
        decision="watch",
        final_action="review_watch_reasons",
        final_reason="latest_snapshot_watch",
        steps=[
            CognitiveTraceStep(
                index=0,
                label="readiness",
                observation="status=watch",
                decision="watch",
                confidence=0.6,
            )
        ],
    )

    count = CognitiveTraceJsonlStore(path).append(record)
    summary = summarize_cognitive_traces(path)

    assert count == 1
    assert summary["total_trace_count"] == 1
    assert summary["latest_final_action"] == "review_watch_reasons"
    assert summary["latest_step_count"] == 1
