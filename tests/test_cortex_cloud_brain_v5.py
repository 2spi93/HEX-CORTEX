"""Cloud-first Brain V5 contracts; all tests are network- and key-free."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_cloud_brain_v5 import (
    CloudBrain,
    CloudRequestFailed,
    default_cloud_transport,
)
from hex_cortex.memory.cortex_local_harness_cli import main
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task


def _task() -> Task:
    return Task("t1", "coding", "Explain a pure function, no file edits")


def test_no_cloud_api_key_fails_closed_before_network(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    called: list[object] = []

    def fake(url, data, headers, timeout):
        called.append(url)
        return "{}"

    brain = CloudBrain("openai", transport=fake)
    with pytest.raises(CloudRequestFailed, match="cloud_credential_missing"):
        brain("gpt-6.1-sol", _task())
    assert called == []


def test_openai_api_payload_fixed_url_and_no_persisted_response(monkeypatch, tmp_path: Path) -> None:
    secret = "test-key-shall-never-enter-receipts"
    monkeypatch.setenv("OPENAI_API_KEY", secret)
    sent = []

    def fake(url, data, headers, timeout):
        sent.append((url, json.loads(data), headers, timeout))
        return json.dumps({
            "status": "completed",
            "output": [
                {"type": "reasoning", "summary": []},
                {"type": "message", "content": [{"type": "output_text", "text": "OK"}]},
            ],
        })

    brain = CloudBrain("openai", transport=fake, max_output_tokens=200)
    harness = LocalHarness(
        Session("cloud-session", tmp_path),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0),
    )
    output = run_clocked_local_task(
        harness, _task(), models=["gpt-6.1-sol"], brain=brain, approved=True,
    )
    assert output["status"] == "complete"
    assert output["output"] == "OK"
    assert output["canonical_spine_verified"] is True
    assert harness.verify_replay()
    assert len(sent) == 1
    url, body, headers, timeout = sent[0]
    assert url == "https://api.openai.com/v1/responses"
    assert body["model"] == "gpt-6.1-sol"
    assert body["input"] == _task().instruction
    assert body["store"] is False
    assert body["max_output_tokens"] == 200
    assert headers["Authorization"] == f"Bearer {secret}"
    assert timeout == 90.0
    assert secret not in json.dumps(harness.receipts)
    assert secret not in json.dumps(output["receipt"])
    assert "OK" not in json.dumps(harness.receipts)
    assert list(tmp_path.iterdir()) == []


def test_anthropic_messages_payload_and_format(monkeypatch) -> None:
    secret = "test-anthropic-secret"
    monkeypatch.setenv("ANTHROPIC_API_KEY", secret)
    captured = []

    def fake(url, data, headers, timeout):
        captured.append((url, json.loads(data), headers, timeout))
        return json.dumps({
            "stop_reason": "end_turn",
            "content": [
                {"type": "thinking", "thinking": "not persisted"},
                {"type": "text", "text": "Bonjour"},
            ],
        })

    brain = CloudBrain("anthropic", transport=fake, max_output_tokens=300)
    assert brain("claude-sonnet-5", _task()) == "Bonjour"
    url, body, headers, _ = captured[0]
    assert url == "https://api.anthropic.com/v1/messages"
    assert body["model"] == "claude-sonnet-5"
    assert body["max_tokens"] == 300
    assert body["messages"] == [{"role": "user", "content": _task().instruction}]
    assert "temperature" not in body
    assert headers["x-api-key"] == secret
    assert headers["anthropic-version"] == "2023-06-01"


@pytest.mark.parametrize("provider,response", [
    ("openai", {"status": "incomplete", "output": []}),
    ("openai", {"status": "completed", "output": [{"type": "tool_call"}]}),
    ("anthropic", {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "partial"}]}),
    ("anthropic", {"stop_reason": "tool_use", "content": []}),
])
def test_partial_or_tool_only_response_is_rejected(monkeypatch, provider, response) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake")
    brain = CloudBrain(provider, transport=lambda *args: json.dumps(response))
    with pytest.raises(CloudRequestFailed):
        brain("valid-model", _task())


def test_cloud_provider_cannot_be_redirected_to_private_url() -> None:
    with pytest.raises(CloudRequestFailed, match="unapproved_cloud_endpoint"):
        default_cloud_transport(
            "http://127.0.0.1:9999", b"{}", {"Authorization": "secret"}, 1,
        )


def test_cloud_adapter_rejects_excess_budgets_and_unsafe_model_name(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    with pytest.raises(ValueError):
        CloudBrain("openai", max_output_tokens=999999)
    with pytest.raises(ValueError):
        CloudBrain("openai", timeout_seconds=0)
    with pytest.raises(ValueError):
        CloudBrain("openai", max_instruction_chars=0)
    with pytest.raises(CloudRequestFailed, match="invalid_cloud_model_id"):
        CloudBrain("openai")("bad\r\nheader", _task())
    with pytest.raises(CloudRequestFailed, match="cloud_input_budget_exceeded"):
        CloudBrain("openai", max_instruction_chars=4)("valid-model", _task())


def test_cloud_adapter_scrubs_third_party_exceptions(monkeypatch) -> None:
    secret = "never-echo-this-key"
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    def bad(*args):
        raise RuntimeError("provider error with " + secret)

    brain = CloudBrain("openai", transport=bad)
    with pytest.raises(CloudRequestFailed) as exc:
        brain("gpt-6.1-sol", _task())
    assert str(exc.value) == "cloud_transport_failed"
    assert exc.value.__cause__ is None


def test_cloud_harness_denied_without_double_approval(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    rc = main([
        "--project-root", str(tmp_path), "--provider", "openai",
        "--model", "gpt-6.1-sol", "--approve-model",
        "--instruction", "Explain architecture",
    ])
    response = json.loads(capsys.readouterr().out)
    assert rc == 2
    assert response["reason"] == "model_call_not_authorized"
    assert list(tmp_path.iterdir()) == []


def test_cloud_dry_run_requires_no_keys_local_llm_or_network(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rc = main([
        "--project-root", str(tmp_path), "--provider", "anthropic",
        "--model", "claude-sonnet-5", "--dry-run",
    ])
    record = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert record["status"] == "configuration_only"
    assert record["network_call_performed"] is False
    assert record["benchmark_required"] is False
    assert record["checkout_modified"] is False
    assert list(tmp_path.iterdir()) == []


def test_cloud_single_explicit_model_and_no_old_fingerprint(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    rc = main([
        "--project-root", str(tmp_path), "--provider", "openai",
        "--model", "gpt-6.1-sol", "--model", "other", "--approve-model",
        "--approve-cloud-send",
    ])
    assert rc == 2
    assert "requires_one_explicit_model" in capsys.readouterr().out
    rc = main([
        "--project-root", str(tmp_path), "--provider", "openai",
        "--model", "gpt-6.1-sol", "--fingerprint-registry", "x.jsonl",
        "--approve-model", "--approve-cloud-send",
    ])
    assert rc == 2
    assert "cloud_provider_rejects_local_fingerprint_registry" in capsys.readouterr().out


def test_cloud_harness_injected_mock_no_real_http(monkeypatch, tmp_path, capsys) -> None:
    import hex_cortex.memory.cortex_local_harness_cli as cli
    observed = []

    def fake_brain_factory(*, provider, timeout_seconds, max_output_tokens):
        assert provider == "openai"

        def brain(model_id, task):
            observed.append((model_id, task.task_id))
            return "remote model simulated"
        return brain

    monkeypatch.setattr(cli, "CloudBrain", fake_brain_factory)
    rc = main([
        "--project-root", str(tmp_path), "--provider", "openai",
        "--model", "gpt-6.1-sol", "--approve-model", "--approve-cloud-send",
        "--instruction", "Read only",
    ])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["status"] == "complete"
    assert result["output"] == "remote model simulated"
    assert result["canonical_spine_verified"] is True
    assert len(observed) == 1


def test_offline_manifest_remains_operational_without_local_or_cloud_models(tmp_path, capsys) -> None:
    (tmp_path / "pyproject.toml").write_text("project = 'X'\n", encoding="utf-8")
    rc = main(["--project-root", str(tmp_path), "--approve-read"])
    result = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert result["tool_result"]["manifest"] == ["pyproject.toml"]
