"""Local durable MCP Tasks storage for completed read-only operations.

The first integration records already-completed deterministic tool calls; it
does not claim true background execution. SQLite provides retrieval across
separate CLI invocations. The path must be explicitly configured.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

_TASK_TTL_MS = 86_400_000


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LocalTaskStore:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as con:
            con.execute(
                "CREATE TABLE IF NOT EXISTS tasks ("
                "task_id TEXT PRIMARY KEY, created_at TEXT NOT NULL, "
                "updated_at TEXT NOT NULL, status TEXT NOT NULL, "
                "payload TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=3.0)

    def create_completed(self, result: dict[str, object]) -> dict[str, object]:
        """Persist before returning handle to meet immediate tasks/get visibility."""
        task_id = str(uuid4())
        timestamp = _now()
        row = {
            "taskId": task_id, "status": "completed", "createdAt": timestamp,
            "lastUpdatedAt": timestamp, "ttlMs": _TASK_TTL_MS,
            "pollIntervalMs": 1000, "result": result,
        }
        with self._connect() as con:
            con.execute(
                "INSERT INTO tasks VALUES (?, ?, ?, ?, ?)",
                (task_id, timestamp, timestamp, "completed", json.dumps(row)),
            )
        return {k: v for k, v in row.items() if k != "result"}

    def get(self, task_id: str) -> dict[str, object]:
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("taskId required")
        with self._connect() as con:
            result = con.execute(
                "SELECT payload FROM tasks WHERE task_id = ?", (task_id,)
            ).fetchone()
        if result is None:
            raise ValueError("unknown task")
        task: dict[str, object] = json.loads(result[0])
        created = datetime.fromisoformat(str(task["createdAt"]))
        if datetime.now(UTC) >= created + timedelta(milliseconds=_TASK_TTL_MS):
            raise ValueError("task expired")
        return task

    def cancel(self, task_id: str) -> None:
        """Acknowledgement: completed tasks remain terminal."""
        self.get(task_id)

    def update(self, task_id: str, input_responses: dict[str, object]) -> None:
        """No pending input is supported; unknown input keys are ignored."""
        if not isinstance(input_responses, dict):
            raise ValueError("inputResponses must be an object")
        self.get(task_id)
