"""A2A JSON-RPC local adapter. In-process only; no HTTP transport or credentials.

Supported A2A subset: SendMessage, GetTask, CancelTask. All actions use the
read-only LocalHarness; the operator must explicitly enable repository reads.
This module does NOT advertise a network AgentCard or push notifications.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_local_harness_v2 import Task, build_readonly_harness
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task


def _error(request_id: object, code: int, message: str) -> dict[str, object]:
    return {"jsonrpc": "2.0", "id": request_id,
            "error": {"code": code, "message": message}}


@dataclass
class LocalA2A:
    """Single-machine A2A message/Task evaluator and idempotency boundary."""

    root: Path
    allow_read_repo: bool = False
    tasks: dict[str, dict[str, object]] = field(default_factory=dict)
    message_index: dict[str, tuple[str, str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.harness = build_readonly_harness(self.root, session_id="a2a-local")

    @staticmethod
    def _text_from_message(message: object) -> str:
        if not isinstance(message, dict):
            raise ValueError("message must be an object")
        if message.get("role") != "user":
            raise ValueError("only user messages accepted")
        parts = message.get("parts")
        if not isinstance(parts, list) or not parts or len(parts) > 8:
            raise ValueError("message must have 1-8 parts")
        texts = []
        for part in parts:
            if not isinstance(part, dict) or not isinstance(part.get("text"), str):
                raise ValueError("only text parts supported")
            texts.append(part["text"])
        result = "\n".join(texts)
        if not result.strip() or len(result) > 4_096:
            raise ValueError("message text invalid or too long")
        return result

    def handle(self, message: dict[str, object]) -> dict[str, object]:
        request_id = message.get("id")
        if message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            return _error(request_id, -32600, "Invalid A2A request")
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            return _error(request_id, -32602, "Invalid params")
        if method == "SendMessage":
            try:
                incoming = params.get("message")
                text = self._text_from_message(incoming)
                assert isinstance(incoming, dict)
                message_id = incoming.get("messageId")
                if not isinstance(message_id, str) or not message_id.strip():
                    raise ValueError("messageId is required")
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                if message_id in self.message_index:
                    previous_digest, existing_task = self.message_index[message_id]
                    if previous_digest != digest:
                        raise ValueError("messageId collision with different content")
                    return {"jsonrpc": "2.0", "id": request_id,
                            "result": {"task": self.tasks[existing_task]}}
                task_id = str(uuid4())
                # The only supported task is a diagnostic inventory; no
                # interpretation of the input text as executable commands.
                execution = run_clocked_local_task(
                    Task(task_id, "repo_read", "A2A read-only checkout inventory", "repo_manifest"),
                    approved=self.allow_read_repo,
                )
                if execution["status"] == "complete":
                    state = "completed"
                    content = json.dumps(execution["tool_result"], sort_keys=True)
                else:
                    state = "failed"
                    content = "operation_denied_by_local_policy"
                task = {
                    "id": task_id,
                    "contextId": "hex-cortex-local",
                    "status": {"state": state},
                    "artifacts": [{
                        "artifactId": "receipt",
                        "parts": [{"text": content}],
                    }],
                    "metadata": {
                        "project": "HEX-CORTEX",
                        "receipt_sha256": execution["receipt"]["sha256"],
                        "side_effects": False,
                    },
                }
                self.tasks[task_id] = task
                self.message_index[message_id] = (digest, task_id)
                return {"jsonrpc": "2.0", "id": request_id, "result": {"task": task}}
            except ValueError as exc:
                return _error(request_id, -32602, str(exc))
        if method in {"GetTask", "CancelTask"}:
            task_id = params.get("id")
            if not isinstance(task_id, str) or task_id not in self.tasks:
                return _error(request_id, -32602, "Unknown task")
            task = self.tasks[task_id]
            if method == "CancelTask" and task["status"]["state"] not in {
                "completed", "failed", "canceled",
            }:
                task["status"] = {"state": "canceled"}
            return {"jsonrpc": "2.0", "id": request_id, "result": task}
        return _error(request_id, -32601, "Unsupported A2A method")


def run_local_a2a_jsonl(input_text: str, *, root: Path, allow_read_repo: bool = False) -> str:
    """Test/CLI adapter for several JSON-RPC messages without opening a socket."""
    dispatcher = LocalA2A(root=root, allow_read_repo=allow_read_repo)
    outputs = []
    for raw in input_text.splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                raise ValueError("RPC message must be a JSON object")
            response = dispatcher.handle(payload)
        except (json.JSONDecodeError, ValueError):
            response = _error(None, -32700, "Invalid JSONL A2A request")
        outputs.append(json.dumps(response, sort_keys=True))
    return "\n".join(outputs) + ("\n" if outputs else "")
