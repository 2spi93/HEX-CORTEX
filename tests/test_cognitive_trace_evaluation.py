from hex_cortex.memory.cognitive_trace import (
    CognitiveTraceJsonlStore,
    CognitiveTraceRecord,
    CognitiveTraceStep,
)
from hex_cortex.memory.cognitive_trace_evaluation import (
    evaluate_latest_cognitive_trace,
    summarize_cognitive_trace_evaluations,
)


def test_cognitive_trace_evaluation_blocks_missing_trace(tmp_path) -> None:
    payload = evaluate_latest_cognitive_trace(tmp_path / "profile")
    record = payload["evaluation_record"]

    assert record["verdict"] == "trace_missing"
    assert record["overall_score"] == 0.0


def test_cognitive_trace_evaluation_scores_valid_trace(tmp_path) -> None:
    profile = tmp_path / "profile"
    trace_path = profile / "cognitive-trace.jsonl"
    CognitiveTraceJsonlStore(trace_path).append(
        CognitiveTraceRecord(
            profile_path=str(profile),
            source_type="test",
            status="watch",
            decision="watch",
            final_action="review_watch_reasons",
            final_reason="latest_snapshot_watch",
            steps=[
                CognitiveTraceStep(index=0, label="readiness", observation="o", decision="watch", confidence=0.6),
                CognitiveTraceStep(index=1, label="next_action", observation="o", decision="review", confidence=0.8),
                CognitiveTraceStep(index=2, label="safety", observation="o", decision="block", confidence=0.9),
                CognitiveTraceStep(index=3, label="dispatch", observation="o", decision="skipped", confidence=0.9),
                CognitiveTraceStep(index=4, label="cycle", observation="o", decision="review", confidence=0.85),
            ],
        )
    )

    payload = evaluate_latest_cognitive_trace(profile)
    summary = summarize_cognitive_trace_evaluations(profile / "cognitive-trace-evaluation.jsonl")

    assert payload["evaluation_record"]["verdict"] == "trace_valid"
    assert payload["evaluation_record"]["overall_score"] == 1.0
    assert summary["latest_verdict"] == "trace_valid"
