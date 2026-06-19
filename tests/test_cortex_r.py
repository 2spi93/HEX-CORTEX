import json

import pytest

import hex_cortex.memory.cortex_r as module
from hex_cortex.memory.cortex_r import build_cortex_r


def test_cortex_r_rejects_remote_endpoint() -> None:
    with pytest.raises(ValueError, match="localhost"):
        build_cortex_r(endpoint="http://example.invalid:11434/api/generate")


def test_cortex_r_rejects_missing_port() -> None:
    with pytest.raises(ValueError, match="port"):
        build_cortex_r(endpoint="http://localhost/api/generate")


def test_cortex_r_extracts_nested_response_json() -> None:
    raw = json.dumps({"response": json.dumps({"status": "ok", "summary": "ready"})})

    result = module._extract(raw)

    assert result == {"status": "ok", "summary": "ready"}


def test_cortex_r_runner_posts_local_json(monkeypatch) -> None:
    calls = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return json.dumps({"response": json.dumps({"status": "ok", "summary": "ready"})}).encode("utf-8")

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse()

    monkeypatch.setattr(module, "urlopen", fake_urlopen)
    runner = build_cortex_r(endpoint="http://127.0.0.1:11434/api/generate", timeout_seconds=3)

    result = runner({"model": "qwen2.5-coder:7b-instruct"})

    assert result == {
        "status": "ok",
        "summary": "ready",
        "network_call_performed": True,
        "external_effect_performed": False,
    }
    assert len(calls) == 1
    request, timeout = calls[0]
    assert timeout == 3
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    assert request.get_method() == "POST"
