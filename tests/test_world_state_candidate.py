from hex_cortex.memory.cognitive_trace import (
    CognitiveTraceJsonlStore,
    CognitiveTraceRecord,
    CognitiveTraceStep,
)
from hex_cortex.memory.cognitive_trace_evaluation import evaluate_latest_cognitive_trace
from hex_cortex.memory.world_state_candidate import (
    build_world_state_candidate,
    summarize_world_state_candidates,
)


def test_world_state_candidate_handles_missing_trace(tmp_path) -> None:
    payload = build_world_state_candidate(tmp_path / "profile")
    record = payload["candidate_record"]

    assert record["current_state"] == "trace_missing"
    assert record["candidate_action"] == "build_trace"
    assert record["predicted_risk"] == "high"


def test_world_state_candidate_uses_latest_trace_and_evaluation(tmp_path) -> None:
    profile = tmp_path / "profile"
    CognitiveTraceJsonlStore(profile / "cognitive-trace.jsonl").append(
        CognitiveTraceRecord(
            profile_path=str(profile),
            source_type="test",
            status="watch",
            decision="watch",
            final_action="review_watch_reasons",
            final_reason="latest_snapshot_watch",
            steps=[
                CognitiveTraceStep(
                    index=0,
                    label="readiness",
                    observation="o",
                    decision="watch",
                    confidence=0.6,
                ),
                CognitiveTraceStep(
                    index=1,
                    label="next_action",
                    observation="o",
                    decision="review",
                    confidence=0.8,
                ),
                CognitiveTraceStep(
                    index=2,
                    label="safety",
                    observation="o",
                    decision="block",
                    confidence=0.9,
                ),
                CognitiveTraceStep(
                    index=3,
                    label="dispatch",
                    observation="o",
                    decision="skipped",
                    confidence=0.9,
                ),
                CognitiveTraceStep(
                    index=4,
                    label="cycle",
                    observation="o",
                    decision="review",
                    confidence=0.85,
                ),
            ],
        )
    )
    evaluate_latest_cognitive_trace(profile)

    payload = build_world_state_candidate(profile)
    summary = summarize_world_state_candidates(profile / "world-state-candidate.jsonl")
    record = payload["candidate_record"]

    assert record["current_state"] == "status=watch; decision=watch"
    assert record["expected_state"] == "operator_reviews_watch_reasons"
    assert record["candidate_action"] == "review_watch_reasons"
    assert record["predicted_risk"] == "low"
    assert summary["latest_candidate_action"] == "review_watch_reasons"
