"""Operator-controlled CPU-only Ollama chat using the EXISTING LocalHarness.

No commands/tools, no conversation persistence, no CUDA/GPU; every send is a
one-shot explicitly-approved CALL_MODEL with a bounded budget.
"""
from __future__ import annotations

from uuid import uuid4

from hex_cortex.memory.cortex_benchmark_runtime import (
    default_local_transport,
    list_local_models,
)
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain

_ENDPOINT = "http://127.0.0.1:11434"


def available_models(*, transport=default_local_transport) -> list[str]:
    """Read fixed Ollama loopback endpoint; never choose a user URL."""
    models = list_local_models(
        endpoint=_ENDPOINT, transport=transport, timeout_seconds=2.5,
    )
    return sorted(set(name for name in models if isinstance(name, str)
                      and 0 < len(name) <= 120 and not any(c.isspace() for c in name)))[:64]


def safe_cpu_chat(
    *, root, model: str, prompt: str, transport=default_local_transport,
    history: tuple[tuple[str, str], ...] = (),
    trusted_project_facts: str = "",
) -> dict:
    """One prompt, one model call, no tool dispatch or stored messages."""
    if not isinstance(prompt, str) or not 0 < len(prompt.strip()) <= 1600:
        raise ValueError("command_center_chat_prompt_invalid")
    if not isinstance(model, str) or not 0 < len(model) <= 120:
        raise ValueError("command_center_chat_model_invalid")
    if model not in available_models(transport=transport):
        raise ValueError("command_center_chat_model_not_installed")
    harness = LocalHarness(
        session=Session(session_id="ui-model-" + uuid4().hex, project_root=root),
        grants=frozenset({Capability.CALL_MODEL}),
        budget=Budget(max_model_calls=1, max_tool_calls=0, max_response_chars=3800),
    )
    brain = LocalOllamaBrain(
        endpoint=_ENDPOINT, timeout_seconds=45.0,
        max_predict_tokens=256, num_gpu=0, transport=transport,
        history=history, trusted_project_facts=trusted_project_facts,
    )
    result = harness.execute(
        Task(task_id="ui-chat-" + uuid4().hex, domain="local_chat",
             instruction=prompt.strip()),
        models=[model], brain=brain, approved=True,
    )
    if not harness.verify_replay():
        raise ValueError("command_center_chat_replay_failed")
    if result["status"] != "complete":
        return {
            "status": "blocked", "reason": result["reason"],
            "model_used": None, "files_written": False, "gpu_used": False,
        }
    return {
        "status": "completed", "reply": result["output"],
        "model_used": result["receipt"]["model_used"],
        "receipt_sha256": result["receipt"]["sha256"],
        "calls_used": 1,
        "context_turns_used": len(history),
        "server_capability_facts_used": bool(trusted_project_facts),
        "cpu_only_requested": True,
        "gpu_used": False,
        "tools_executed": False,
        "conversation_saved": False,
        "spine_saved": False,
        "files_written": False,
    }
