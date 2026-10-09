from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_local_harness_cli import main
from hex_cortex.memory.cortex_local_harness_v2 import Budget, Capability, LocalHarness, Session, Task
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain


def test_local_ollama_adapter_bounded_and_unloads() -> None:
    collected = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        content = json.loads(body)
        collected.append((url, content, timeout))
        return json.dumps({"message": {"content": "42"}})

    brain = LocalOllamaBrain(transport=fake_transport, max_predict_tokens=256)
    answer = brain("tiny-local", Task("1", "math", "What is six times seven?"))
    assert answer == "42"
    url, body, timeout = collected[0]
    assert url == "http://127.0.0.1:11434/api/chat"
    assert timeout == 60.0
    assert body["stream"] is False
    assert body["keep_alive"] == 0
    assert body["options"]["num_predict"] == 256


def test_remote_endpoint_and_unbounded_tokens_rejected() -> None:
    with pytest.raises(ValueError):
        LocalOllamaBrain(endpoint="https://example.org")
    with pytest.raises(ValueError):
        LocalOllamaBrain(max_predict_tokens=500_000)
    with pytest.raises(ValueError):
        LocalOllamaBrain(timeout_seconds=1000.0)


def test_harness_budget_stops_second_model_call(tmp_path: Path) -> None:
    calls = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        calls.append(json.loads(body))
        return json.dumps({"message": {"content": "OK"}})

    harness = LocalHarness(
        session=Session("local-llm", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1),
    )
    brain = LocalOllamaBrain(transport=fake_transport)
    assert harness.execute(
        Task("t1", "coding", "Summarize this function"),
        models=["local"], brain=brain, approved=True,
    )["status"] == "complete"
    assert harness.execute(
        Task("t2", "coding", "Summarize more"),
        models=["local"], brain=brain, approved=True,
    )["status"] == "blocked"
    assert len(calls) == 1


def test_cli_read_denied_without_explicit_approval(tmp_path: Path, capsys) -> None:
    code = main(["--project-root", str(tmp_path)])
    result = json.loads(capsys.readouterr().out)
    assert code == 2
    assert result["reason"] == "tool_not_authorized"


def test_cli_read_approved(tmp_path: Path, capsys) -> None:
    (tmp_path / "README.md").write_text("local checkout", encoding="utf-8")
    code = main(["--project-root", str(tmp_path), "--approve-read"])
    result = json.loads(capsys.readouterr().out)
    assert code == 0
    assert result["tool_result"]["manifest"] == ["README.md"]


def test_cli_model_denied_by_default_without_call(tmp_path: Path, capsys) -> None:
    code = main([
        "--project-root", str(tmp_path), "--model", "local",
        "--instruction", "Test",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 2
    assert result["reason"] == "model_call_not_authorized"
