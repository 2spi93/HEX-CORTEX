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
    transport: Transport = default_local_transport

    def __post_init__(self) -> None:
        _require_localhost(self.endpoint.rstrip("/") + "/api/chat")
        if not 0 < self.timeout_seconds <= 600:
            raise ValueError("model request timeout must be within (0, 600]")
        if not 0 < self.max_predict_tokens <= 4096:
            raise ValueError("model token budget must be within (0, 4096]")

    def __call__(self, model_id: str, task: Task) -> str:
        if not model_id.strip():
            raise ValueError("model identifier required")
        body = json.dumps(
            {
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
                    {"role": "user", "content": task.instruction},
                ],
                "options": {
                    "temperature": 0.0,
                    "num_predict": self.max_predict_tokens,
                },
                "stream": False,
                "keep_alive": 0,
            }
        ).encode("utf-8")
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
