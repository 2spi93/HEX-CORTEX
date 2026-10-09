"""A2A in-process protocol subset with explicit local grant."""

from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_a2a_local import LocalA2A, run_local_a2a_jsonl


def _send(message_id: str = "m-1", content: str = "inspect repo") -> dict:
    return {
        "jsonrpc": "2.0", "id": 1, "method": "SendMessage",
        "params": {
            "message": {
                "messageId": message_id, "role": "user",
                "parts": [{"text": content}],
            }
        },
    }


def test_a2a_default_is_denied(tmp_path: Path) -> None:
    dispatcher = LocalA2A(root=tmp_path)
    result = dispatcher.handle(_send())["result"]["task"]
    assert result["status"]["state"] == "failed"
    assert "operation_denied_by_local_policy" in str(result["artifacts"])
    assert result["metadata"]["side_effects"] is False


def test_a2a_approved_manifest_and_idempotent_replay(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("ok", encoding="utf-8")
    dispatcher = LocalA2A(root=tmp_path, allow_read_repo=True)
    first = dispatcher.handle(_send())["result"]["task"]
    assert first["status"]["state"] == "completed"
    assert "pyproject.toml" in str(first["artifacts"])
    repeat = dispatcher.handle(_send())["result"]["task"]
    assert repeat["id"] == first["id"]
    fetched = dispatcher.handle({
        "jsonrpc": "2.0", "id": 2, "method": "GetTask",
        "params": {"id": first["id"]},
    })["result"]
    assert fetched["id"] == first["id"]
    terminated = dispatcher.handle({
        "jsonrpc": "2.0", "id": 3, "method": "CancelTask",
        "params": {"id": first["id"]},
    })["result"]
    assert terminated["status"]["state"] == "completed"


def test_a2a_rejects_collision_privilege_and_nontext_parts(tmp_path: Path) -> None:
    dispatcher = LocalA2A(root=tmp_path, allow_read_repo=True)
    dispatcher.handle(_send("one", "inventory"))
    conflict = dispatcher.handle(_send("one", "execute anything"))
    assert conflict["error"]["code"] == -32602
    payload = _send("two")
    payload["params"]["message"]["parts"] = [{"file": {"uri": "file:///private"}}]
    assert dispatcher.handle(payload)["error"]["code"] == -32602
    payload = _send("three")
    payload["params"]["message"]["role"] = "agent"
    assert dispatcher.handle(payload)["error"]["code"] == -32602


def test_a2a_unsupported_method_and_bad_jsonl(tmp_path: Path) -> None:
    dispatcher = LocalA2A(root=tmp_path)
    bad = dispatcher.handle({"jsonrpc": "2.0", "id": 4, "method": "DeleteAll"})
    assert bad["error"]["code"] == -32601
    raw = run_local_a2a_jsonl(
        "{this is not json}\n" + json.dumps(_send()) + "\n",
        root=tmp_path, allow_read_repo=False,
    )
    results = [json.loads(line) for line in raw.splitlines()]
    assert results[0]["error"]["code"] == -32700
    assert results[1]["result"]["task"]["status"]["state"] == "failed"
