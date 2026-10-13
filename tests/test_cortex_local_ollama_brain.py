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


def test_local_ollama_num_gpu_none_omitted_from_payload() -> None:
    """When num_gpu is None, it should not appear in the options payload."""
    collected = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        content = json.loads(body)
        collected.append((url, content, timeout))
        return json.dumps({"message": {"content": "OK"}})

    brain = LocalOllamaBrain(transport=fake_transport, num_gpu=None)
    brain("tiny-local", Task("1", "coding", "Test"))
    _, body, _ = collected[0]
    assert "num_gpu" not in body["options"]


def test_local_ollama_num_gpu_zero_forces_cpu() -> None:
    """When num_gpu=0, Ollama should force CPU-only inference."""
    collected = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        content = json.loads(body)
        collected.append((url, content, timeout))
        return json.dumps({"message": {"content": "OK"}})

    brain = LocalOllamaBrain(transport=fake_transport, num_gpu=0)
    brain("tiny-local", Task("1", "coding", "Test"))
    _, body, _ = collected[0]
    assert body["options"]["num_gpu"] == 0


def test_local_ollama_num_gpu_positive_included() -> None:
    """When num_gpu is a positive integer, it should appear in options."""
    collected = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        content = json.loads(body)
        collected.append((url, content, timeout))
        return json.dumps({"message": {"content": "OK"}})

    brain = LocalOllamaBrain(transport=fake_transport, num_gpu=2)
    brain("tiny-local", Task("1", "coding", "Test"))
    _, body, _ = collected[0]
    assert body["options"]["num_gpu"] == 2


def test_local_ollama_negative_num_gpu_rejected() -> None:
    """Negative num_gpu values should be rejected."""
    with pytest.raises(ValueError, match="num_gpu must be non-negative"):
        LocalOllamaBrain(num_gpu=-1)


def test_cli_num_gpu_zero_passed_to_brain(tmp_path: Path, capsys) -> None:
    """CLI --num-gpu 0 should be transmitted to the brain."""
    collected = []

    def fake_transport(url: str, body: bytes | None, timeout: float) -> str:
        content = json.loads(body)
        collected.append((url, content, timeout))
        return json.dumps({"message": {"content": "OK"}})

    # Patch LocalOllamaBrain to capture the transport call
    import hex_cortex.memory.cortex_local_harness_cli as cli_module
    original_brain = cli_module.LocalOllamaBrain

    def patched_brain(*args, **kwargs):
        kwargs["transport"] = fake_transport
        return original_brain(*args, **kwargs)

    cli_module.LocalOllamaBrain = patched_brain  # type: ignore
    try:
        code = main([
            "--project-root", str(tmp_path),
            "--model", "local",
            "--instruction", "Test",
            "--approve-model",
            "--num-gpu", "0",
        ])
        result = json.loads(capsys.readouterr().out)
        assert code == 0
        assert result["status"] == "complete"
        assert len(collected) == 1
        _, body, _ = collected[0]
        assert body["options"]["num_gpu"] == 0
    finally:
        cli_module.LocalOllamaBrain = original_brain


def test_cli_num_gpu_negative_rejected(tmp_path: Path, capsys) -> None:
    """CLI --num-gpu with negative value should be rejected."""
    code = main([
        "--project-root", str(tmp_path),
        "--num-gpu", "-1",
    ])
    result = json.loads(capsys.readouterr().out)
    assert code == 2
    assert "num_gpu must be non-negative" in result["reason"]


def test_local_ollama_structured_schema_opt_in_only() -> None:
    from hex_cortex.memory.cortex_structured_code_plan import code_plan_json_schema

    seen = []

    def transport(_url: str, body: bytes | None, _timeout: float) -> str:
        seen.append(json.loads(body))
        return json.dumps({"message": {"content": '{"summary":"ok"}'}})

    schema = code_plan_json_schema()
    brain = LocalOllamaBrain(
        transport=transport, response_format=schema, num_gpu=0,
        max_predict_tokens=1536,
    )
    brain("qwen2.5-coder:7b", Task("test", "coding", "Return JSON"))
    assert seen[0]["format"] == schema
    assert seen[0]["options"]["num_gpu"] == 0
    assert seen[0]["options"]["num_predict"] == 1536
    assert seen[0]["stream"] is False
    assert seen[0]["keep_alive"] == 0


def test_local_ollama_refuses_arbitrary_format_values() -> None:
    with pytest.raises(ValueError, match="response_format"):
        LocalOllamaBrain(response_format="xml")
    with pytest.raises(ValueError, match="response_format"):
        LocalOllamaBrain(response_format={"type": "array"})
    with pytest.raises(ValueError, match="response_format"):
        LocalOllamaBrain(response_format={"type": "object", "description": "a" * 40000})
