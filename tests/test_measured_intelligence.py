"""Tests for the measured-intelligence kit: benchmark, bandit, calibration, reflex."""

from __future__ import annotations

import json

import pytest

from hex_cortex.memory.cortex_bandit_router import (
    empty_routing_stats,
    rank_models,
    update_routing_outcome,
)
from hex_cortex.memory.cortex_confidence_calibration import (
    build_calibration_map,
    calibrate_confidence,
)
from hex_cortex.memory.cortex_model_benchmark import (
    BENCHMARK_TASKS,
    build_benchmark_suite,
    score_benchmark_responses,
)
from hex_cortex.memory.cortex_reflex_brain import build_reflex_request, classify_task

# --- benchmark ---------------------------------------------------------------

PERFECT_RESPONSES = {
    "code_trace_len": "9",
    "code_trace_slice": "xetroc",
    "code_trace_sort": "The answer is 8",
    "code_bug_line": "Line 3",
    "math_product": "391",
    "math_gcd": "12",
    "math_percent": "36",
    "french_plural": "chevaux",
    "french_grammar": "écrits",
    "json_answer_int": '{"answer": 4}',
    "json_answer_list": '{"primes": [2, 3, 5, 7]}',
    "instruction_exact_word": "OUI",
    "instruction_no_extra": "DONE-42",
}


def test_suite_exposes_prompts_without_answers() -> None:
    suite = build_benchmark_suite()

    assert suite["task_count"] == len(BENCHMARK_TASKS)
    assert "coding" in suite["domains"] and "french" in suite["domains"]
    serialized = json.dumps(suite)
    assert "expected" not in serialized  # answers never leak to the model under test
    assert all(set(task) == {"task_id", "domain", "prompt"} for task in suite["tasks"])


def test_perfect_responses_score_one_everywhere() -> None:
    report = score_benchmark_responses(model_id="test-model", responses=PERFECT_RESPONSES)

    assert report["overall_score"] == 1.0
    assert all(score == 1.0 for score in report["domain_scores"].values())


def test_wrong_verbose_and_missing_answers_are_failures() -> None:
    responses = dict(PERFECT_RESPONSES)
    responses["math_product"] = "The answer is 392"  # wrong number
    responses["instruction_exact_word"] = "OUI, bien sûr!"  # extra words break exact
    responses.pop("french_plural")  # unanswered counts as failure

    report = score_benchmark_responses(model_id="weak-model", responses=responses)

    failed = {row["task_id"] for row in report["task_results"] if not row["passed"]}
    assert failed == {"math_product", "instruction_exact_word", "french_plural"}
    assert report["domain_scores"]["coding"] == 1.0
    assert report["domain_scores"]["french"] == 0.5


def test_json_answers_are_extracted_from_chatty_output() -> None:
    responses = dict(PERFECT_RESPONSES)
    responses["json_answer_int"] = 'Sure! Here is the JSON:\n{"answer": 4}\nHope this helps.'

    report = score_benchmark_responses(model_id="chatty", responses=responses)
    results = {row["task_id"]: row["passed"] for row in report["task_results"]}
    assert results["json_answer_int"] is True


def test_unknown_task_ids_are_rejected() -> None:
    with pytest.raises(ValueError):
        score_benchmark_responses(model_id="m", responses={"nope": "x"})


# --- bandit router -----------------------------------------------------------


def test_bandit_learns_from_outcomes() -> None:
    stats = empty_routing_stats()
    for _ in range(10):
        stats = update_routing_outcome(stats, model_id="strong", domain="coding", success=True)
        stats = update_routing_outcome(stats, model_id="weak", domain="coding", success=False)

    decision = rank_models(stats, domain="coding", candidates=["weak", "strong"])

    assert decision["selected_model"] == "strong"
    assert decision["reasons"] == ["observed_rate_dominant"]
    assert decision["total_domain_trials"] == 20


def test_unexplored_model_gets_optimism_bonus() -> None:
    stats = empty_routing_stats()
    for _ in range(30):
        stats = update_routing_outcome(stats, model_id="known", domain="coding", success=True)

    decision = rank_models(stats, domain="coding", candidates=["known", "newcomer"])
    rows = {row["model_id"]: row for row in decision["ranking"]}

    assert rows["newcomer"]["exploration_bonus"] > rows["known"]["exploration_bonus"]


def test_benchmark_prior_breaks_cold_start_ties() -> None:
    stats = empty_routing_stats()
    decision = rank_models(
        stats,
        domain="coding",
        candidates=["model-a", "model-b"],
        benchmark_priors={"model-a": 0.9, "model-b": 0.3},
    )

    assert decision["selected_model"] == "model-a"


def test_update_is_pure_and_inputs_validated() -> None:
    stats = empty_routing_stats()
    updated = update_routing_outcome(stats, model_id="m", domain="coding", success=True)

    assert stats["models"] == {}  # original untouched
    assert updated["models"]["m"]["coding"]["successes"] == 1
    with pytest.raises(ValueError):
        rank_models(stats, domain="coding", candidates=[])
    with pytest.raises(ValueError):
        rank_models(stats, domain="coding", candidates=["a", "a"])


# --- confidence calibration --------------------------------------------------


def test_calibration_detects_bluffing_model() -> None:
    # Model claims 0.9 but succeeds only 50% of the time.
    observations = [
        {"claimed_confidence": 0.9, "success": index % 2 == 0} for index in range(20)
    ]
    calibration_map = build_calibration_map(observations)

    result = calibrate_confidence(0.9, calibration_map)
    assert result["corrected_confidence"] == pytest.approx(0.5)
    assert result["bluff_detected"] is True
    assert calibration_map["expected_calibration_error"] == pytest.approx(0.4)


def test_thin_buckets_shrink_toward_claim() -> None:
    observations = [{"claimed_confidence": 0.3, "success": True}]  # one sample only
    calibration_map = build_calibration_map(observations)

    result = calibrate_confidence(0.3, calibration_map)
    assert result["correction_basis"] == "partial_evidence_blend"
    assert 0.3 < result["corrected_confidence"] < 1.0
    assert result["bluff_detected"] is False

    empty = calibrate_confidence(0.8, calibration_map)
    assert empty["corrected_confidence"] == pytest.approx(0.8)
    assert empty["correction_basis"] == "no_evidence_claim_kept"


def test_calibration_rejects_bad_observations() -> None:
    with pytest.raises(ValueError):
        build_calibration_map([{"claimed_confidence": float("nan"), "success": True}])
    with pytest.raises(ValueError):
        build_calibration_map([{"claimed_confidence": 0.5, "success": "yes"}])
    with pytest.raises(ValueError):
        calibrate_confidence(1.5, build_calibration_map([]))


# --- reflex brain ------------------------------------------------------------


def _ollama_reply(content: dict[str, object]) -> str:
    return json.dumps({"message": {"role": "assistant", "content": json.dumps(content)}})


def test_reflex_dry_run_without_transport_is_cold() -> None:
    result = classify_task("Fix the failing pytest in the spine module")

    assert result["dry_run"] is True
    assert result["model_call_performed"] is False
    assert result["request"]["payload"]["options"]["temperature"] == 0.0
    assert result["request"]["mutation_allowed"] is False


def test_reflex_valid_call_returns_bounded_verdict_without_raw_text() -> None:
    captured: dict[str, object] = {}

    def fake_transport(url: str, body: bytes, timeout: float) -> str:
        captured["url"] = url
        return _ollama_reply(
            {"task_domain": "debugging", "novelty": 0.2, "uncertainty": 0.4, "risk": "low"}
        )

    verdict = classify_task("Fix the failing pytest", transport=fake_transport)

    assert verdict["valid"] is True
    assert verdict["task_domain"] == "debugging"
    assert verdict["raw_response_persisted"] is False
    assert "message" not in json.dumps(verdict)  # raw body never leaks
    assert str(captured["url"]).startswith("http://127.0.0.1:11434")


def test_reflex_rejects_out_of_contract_replies() -> None:
    bad_enum = classify_task(
        "task",
        transport=lambda *_: _ollama_reply(
            {"task_domain": "hacking", "novelty": 0.1, "uncertainty": 0.1, "risk": "low"}
        ),
    )
    assert bad_enum["valid"] is False and bad_enum["invalid_reason"] == "enum_out_of_contract"

    bad_score = classify_task(
        "task",
        transport=lambda *_: _ollama_reply(
            {"task_domain": "coding", "novelty": 3.0, "uncertainty": 0.1, "risk": "low"}
        ),
    )
    assert bad_score["valid"] is False and bad_score["invalid_reason"] == "score_out_of_bounds"

    garbage = classify_task("task", transport=lambda *_: "not json at all")
    assert garbage["valid"] is False and garbage["invalid_reason"] == "response_not_parseable"


def test_reflex_refuses_remote_endpoints() -> None:
    with pytest.raises(ValueError):
        build_reflex_request("task", endpoint="http://example.com:11434")
    with pytest.raises(ValueError):
        build_reflex_request("", endpoint="http://127.0.0.1:11434")
