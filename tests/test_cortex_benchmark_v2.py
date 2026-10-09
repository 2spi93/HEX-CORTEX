"""Benchmark V2 quality, privacy and stale-prior regression tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_benchmark_v2 import (
    append_report,
    benchmark_local,
    load_experimental_priors,
    score,
    suite,
    wilson_lower_bound,
)


def _report(responses: dict[str, str]) -> dict[str, object]:
    return score(
        responses,
        model_id="qwen-local",
        model_digest="sha256:abcd",
        quantization="Q4_K_M",
        hardware_id="win11-ryzen",
    )


def test_suite_has_heldout_and_stable_identity() -> None:
    first = suite()
    assert first == suite()
    assert first["count"] >= 18
    assert first["holdout_count"] >= 5
    assert first["independent_repository_validation"] is False


def test_unanswered_tasks_are_failures_and_not_a_prior() -> None:
    report = _report({"instruction_gate": "VERIFY-ONLY"})
    assert report["answered_count"] == 1
    assert report["heldout_score"] < 0.65
    assert report["usable_as_experimental_routing_prior"] is False
    assert report["raw_prompts_or_responses_persisted"] is False
    assert "VERIFY-ONLY" not in json.dumps(report)


def test_all_correct_responses_eligible_only_for_experimental_prior() -> None:
    from hex_cortex.memory.cortex_benchmark_v2 import _TASKS

    values = {}
    for row in _TASKS:
        check = row["check"]
        kind = check["kind"]
        expected = check["expected"]
        if kind == "numeric":
            response = str(int(expected))
        elif kind in {"json_field_numeric", "json_field_equals"}:
            response = json.dumps({check["field"]: expected})
        else:
            response = str(expected)
        values[str(row["task_id"])] = response
    report = _report(values)
    assert report["usable_as_experimental_routing_prior"] is True
    assert report["quality_label"] == "synthetic_smoke_only"
    assert report["heldout_score"] == 1.0
    assert 0 < report["heldout_wilson_lower_95"] < 1.0


def test_reject_unknown_tasks_and_negative_latency() -> None:
    with pytest.raises(ValueError, match="unknown"):
        _report({"unknown": "OK"})
    with pytest.raises(ValueError, match="durations"):
        score(
            {}, model_id="a", model_digest="b", quantization="c",
            hardware_id="d", durations_ms={"code_trace_len": -4.0},
        )
    assert wilson_lower_bound(0, 0) == 0.0


def test_stale_hardware_digest_and_suite_fingerprints_do_not_route(tmp_path: Path) -> None:
    from hex_cortex.memory.cortex_benchmark_v2 import _TASKS

    responses = {}
    for task in _TASKS:
        check = task["check"]
        expected = check["expected"]
        if check["kind"] == "numeric":
            answer = str(expected)
        elif check["kind"].startswith("json_field"):
            answer = json.dumps({check["field"]: expected})
        else:
            answer = str(expected)
        responses[str(task["task_id"])] = answer
    report = _report(responses)
    path = tmp_path / "fingerprints_v2.jsonl"
    append_report(report, path)
    assert load_experimental_priors(
        path, domain="coding", hardware_id="win11-ryzen",
        model_digests={"qwen-local": "sha256:abcd"},
    ) == {"qwen-local": 1.0}
    assert load_experimental_priors(
        path, domain="coding", hardware_id="different",
        model_digests={"qwen-local": "sha256:abcd"},
    ) == {}
    assert load_experimental_priors(
        path, domain="coding", hardware_id="win11-ryzen",
        model_digests={"qwen-local": "another-model-version"},
    ) == {}


def test_live_benchmark_calls_only_local_transport_and_unloads() -> None:
    observed: list[tuple[str, dict[str, object]]] = []

    def transport(url: str, body: bytes | None, timeout: float) -> str:
        assert url == "http://127.0.0.1:11434/api/chat"
        assert timeout > 0
        payload = json.loads(body)
        observed.append((url, payload))
        return json.dumps({"message": {"content": "VERIFY-ONLY"}, "eval_count": 5})

    report = benchmark_local(
        model_id="tiny", model_digest="sha256:abcd", quantization="Q4",
        hardware_id="test", transport=transport,
    )
    assert report["model_call_performed"] is True
    assert report["answered_count"] == suite()["count"]
    assert report["usable_as_experimental_routing_prior"] is False
    assert observed[-1][1]["keep_alive"] == 0
    assert len(observed) == suite()["count"] + 1


def test_nonlocal_endpoint_denied_before_any_model_call() -> None:
    with pytest.raises(ValueError):
        benchmark_local(
            model_id="test", model_digest="sha256:abc", quantization="Q4",
            hardware_id="local", endpoint="https://example.org",
            transport=lambda *_: (_ for _ in ()).throw(AssertionError("called")),
        )
