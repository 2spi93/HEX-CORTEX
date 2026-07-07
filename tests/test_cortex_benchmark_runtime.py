"""Tests for the benchmark runtime with a fake local transport."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_benchmark_runtime import (
    append_fingerprint,
    collect_benchmark_responses,
    list_local_models,
    load_routing_priors,
    main,
    run_model_benchmark,
    unload_model,
)

ANSWERS = {
    "code_trace_len": "9",
    "code_trace_slice": "xetroc",
    "code_trace_sort": "8",
    "code_bug_line": "3",
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

PROMPT_KEYS = {
    "len('hexcortex')": "code_trace_len",
    "'cortex'[::-1]": "code_trace_slice",
    "sorted([3, 1, 2])": "code_trace_sort",
    "mean() wrong": "code_bug_line",
    "17 * 23": "math_product",
    "greatest common divisor": "math_gcd",
    "15% of 240": "math_percent",
    "cheval": "french_plural",
    "participe": "french_grammar",
    '{"answer": <integer>}': "json_answer_int",
    '{"primes"': "json_answer_list",
    "single word OUI": "instruction_exact_word",
    "DONE-42": "instruction_no_extra",
}


def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
    if url.endswith("/api/tags"):
        return json.dumps({"models": [{"name": "small-model"}, {"name": "big-model"}]})
    prompt = json.loads(body.decode("utf-8"))["messages"][0]["content"]
    for fragment, task_id in PROMPT_KEYS.items():
        if fragment in prompt:
            return json.dumps({"message": {"role": "assistant", "content": ANSWERS[task_id]}})
    return json.dumps({"message": {"role": "assistant", "content": "no idea"}})


def test_list_local_models_sorted() -> None:
    models = list_local_models(transport=fake_transport)
    assert models == ["big-model", "small-model"]


def test_collect_and_score_full_loop(tmp_path: Path) -> None:
    report = run_model_benchmark("small-model", transport=fake_transport)

    assert report["overall_score"] == 1.0
    assert report["model_call_performed"] is True
    assert report["measured_at"].endswith("+00:00")
    # No raw model text is persisted in the record.
    assert all(
        set(row) == {"task_id", "domain", "passed", "answered"}
        for row in report["task_results"]
    )

    registry = tmp_path / "fingerprints.jsonl"
    append_fingerprint(report, registry)
    priors = load_routing_priors(registry, domain="coding")
    assert priors == {"small-model": 1.0}


def test_failed_calls_count_as_unanswered() -> None:
    def flaky_transport(url: str, body: bytes | None, timeout: float) -> str:
        prompt = json.loads(body.decode("utf-8"))["messages"][0]["content"]
        if "17 * 23" in prompt:
            raise OSError("connection dropped")
        return fake_transport(url, body, timeout)

    responses = collect_benchmark_responses("small-model", transport=flaky_transport)
    assert "math_product" not in responses
    assert "math_gcd" in responses


def test_runtime_refuses_remote_endpoints() -> None:
    with pytest.raises(ValueError):
        list_local_models(endpoint="http://example.com:11434", transport=fake_transport)
    with pytest.raises(ValueError):
        collect_benchmark_responses(
            "m", endpoint="http://10.0.0.5:11434", transport=fake_transport
        )


def test_unload_model_requests_zero_keep_alive() -> None:
    captured: list[dict[str, object]] = []

    def capture_transport(url: str, body: bytes | None, timeout: float) -> str:
        captured.append(json.loads(body.decode("utf-8")))
        return "{}"

    assert unload_model("small-model", transport=capture_transport) is True
    assert captured == [{"model": "small-model", "messages": [], "keep_alive": 0}]

    def broken_transport(url: str, body: bytes | None, timeout: float) -> str:
        raise OSError("runtime gone")

    assert unload_model("small-model", transport=broken_transport) is False


def test_cli_unloads_each_model_to_avoid_vram_stacking(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    unloads: list[str] = []

    def tracking_transport(url: str, body: bytes | None, timeout: float) -> str:
        if body is not None:
            payload = json.loads(body.decode("utf-8"))
            if payload.get("keep_alive") == 0:
                unloads.append(str(payload["model"]))
                return "{}"
        return fake_transport(url, body, timeout)

    monkeypatch.setattr(
        "hex_cortex.memory.cortex_benchmark_runtime.default_local_transport",
        tracking_transport,
    )

    exit_code = main(["--registry", str(tmp_path / "f.jsonl")])

    assert exit_code == 0
    assert unloads == ["big-model", "small-model"]


def test_cli_main_writes_registry_and_ranks(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        "hex_cortex.memory.cortex_benchmark_runtime.default_local_transport",
        fake_transport,
    )
    registry = tmp_path / "fingerprints.jsonl"

    exit_code = main(["--registry", str(registry), "--domain", "coding"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert {row["model_id"] for row in payload["fingerprints"]} == {"big-model", "small-model"}
    assert payload["routing_demo"]["selected_model"] in {"big-model", "small-model"}
    assert registry.exists()
    assert len(registry.read_text(encoding="utf-8").splitlines()) == 2
