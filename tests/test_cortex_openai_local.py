import json

import pytest

import hex_cortex.memory.cortex_r as runner_module
from hex_cortex.memory.cortex_openai_local import (
    build_cortex_openai_local_adapter,
)
from hex_cortex.memory.cortex_r import build_cortex_r


def test_openai_compatible_extracts_chat_content() -> None:
    raw = json.dumps(
        {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": json.dumps(
                            {"status": "ok", "summary": "ready"}
                        ),
                    }
                }
            ]
        }
    )

    result = runner_module._extract(
        raw,
        protocol="openai_compatible",
    )

    assert result == {"status": "ok", "summary": "ready"}


def test_openai_compatible_runner_posts_messages(monkeypatch) -> None:
    observed = {}

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "local answer",
                            }
                        }
                    ]
                }
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["payload"] = json.loads(request.data.decode("utf-8"))
        return Response()

    monkeypatch.setattr(runner_module, "urlopen", fake_urlopen)
    runner = build_cortex_r(
        endpoint="http://127.0.0.1:8080/v1/chat/completions",
        protocol="openai_compatible",
    )

    result = runner(
        {
            "model": "local-model",
            "prompt": "Inspect this architecture.",
        }
    )

    assert result == {"status": "ok", "summary": "local answer"}
    assert observed["url"].endswith("/v1/chat/completions")
    assert observed["timeout"] == 8.0
    assert observed["payload"]["model"] == "local-model"
    assert observed["payload"]["messages"] == [
        {"role": "user", "content": "Inspect this architecture."}
    ]


def test_openai_local_adapter_contract() -> None:
    adapter = build_cortex_openai_local_adapter()

    assert adapter.name == "local.openai_compatible"
    assert adapter.lane == "tool"
    assert adapter.network_capable is True
    assert adapter.auto_safe_capable is True


def test_local_runner_rejects_unknown_protocol() -> None:
    with pytest.raises(ValueError, match="unsupported"):
        build_cortex_r(
            endpoint="http://127.0.0.1:8080/v1/chat/completions",
            protocol="unknown",
        )
