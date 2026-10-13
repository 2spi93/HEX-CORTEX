"""Explicitly approved local Ollama Brain adapter for the Harness V2 kernel."""

from __future__ import annotations

import json
from dataclasses import dataclass

from hex_cortex.memory.cortex_benchmark_runtime import (
    Transport,
    _require_localhost,
    default_local_transport,
)
from hex_cortex.memory.cortex_local_harness_v2 import Task


@dataclass(frozen=True)
class LocalOllamaBrain:
    endpoint: str = "http://127.0.0.1:11434"
    timeout_seconds: float = 60.0
    max_predict_tokens: int = 768
    num_gpu: int | None = None
    transport: Transport = default_local_transport
    response_format: dict[str, object] | str | None = None
    history: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        _require_localhost(self.endpoint.rstrip("/") + "/api/chat")
        if not 0 < self.timeout_seconds <= 600:
            raise ValueError("model request timeout must be within (0, 600]")
        if not 0 < self.max_predict_tokens <= 4096:
            raise ValueError("model token budget must be within (0, 4096]")
        if self.num_gpu is not None and self.num_gpu < 0:
            raise ValueError("num_gpu must be non-negative or None for default behavior")
        if len(self.history) > 6 or len(self.history) % 2 != 0:
            raise ValueError("chat history exceeds three complete exchanges")
        for index, turn in enumerate(self.history):
            if (
                not isinstance(turn, tuple) or len(turn) != 2
                or turn[0] != ("user" if index % 2 == 0 else "assistant")
                or not isinstance(turn[1], str)
                or not 0 < len(turn[1].strip()) <= 600
            ):
                raise ValueError("chat history role, text or length invalid")
        if self.response_format is not None:
            if self.response_format != "json" and not isinstance(self.response_format, dict):
                raise ValueError("response_format must be a JSON schema or 'json'")
            if isinstance(self.response_format, dict):
                encoded = json.dumps(self.response_format, ensure_ascii=True)
                if len(encoded) > 32768 or self.response_format.get("type") != "object":
                    raise ValueError("response_format JSON schema invalid or too large")

    def __call__(self, model_id: str, task: Task) -> str:
        if not model_id.strip():
            raise ValueError("model identifier required")
        options: dict[str, object] = {
            "temperature": 0.0,
            "num_predict": self.max_predict_tokens,
        }
        if self.num_gpu is not None:
            options["num_gpu"] = self.num_gpu
        request: dict[str, object] = {
                "model": model_id,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are HEX-CORTEX's local read-only reasoning brain. "
                            "Return an answer; do not claim a tool, patch, test, "
                            "repository modification or external call was performed."
                        ),
                    },
                    *[{"role": role, "content": text} for role, text in self.history],
                    {"role": "user", "content": task.instruction},
                ],
                "options": options,
                "stream": False,
                "keep_alive": 0,
            }
        if self.response_format is not None:
            request["format"] = self.response_format
        body = json.dumps(request).encode("utf-8")
        result = json.loads(
            self.transport(
                self.endpoint.rstrip("/") + "/api/chat",
                body, self.timeout_seconds,
            )
        )
        answer = result["message"]["content"]
        if not isinstance(answer, str):
            raise ValueError("local model returned non-text response")
        return answer
