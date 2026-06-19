from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from hex_cortex.memory.cortex_server_federation_audit import verify_signed_task_envelope

FEDERATION_QUEUE_FILENAME = "cortex-federation-queue.jsonl"


def enqueue_federation_task(
    profile: Path,
    *,
    envelope: dict[str, object],
    signing_key: bytes,
) -> dict[str, object]:
    verification = verify_signed_task_envelope(envelope, signing_key=signing_key)
    if verification["signature_valid"] is not True:
        return {
            "queue_type": "federation_queue",
            "queue_allowed": False,
            "blockers": list(verification["blockers"]),
            "event_record": None,
        }
    state = project_federation_queue(profile / FEDERATION_QUEUE_FILENAME)
    envelope_id = str(envelope.get("envelope_id"))
    if envelope_id in state["tasks"]:
        return {
            "queue_type": "federation_queue",
            "queue_allowed": True,
            "idempotent_reuse": True,
            "event_record": None,
            "task_state": state["tasks"][envelope_id],
        }
    event = {
        "event_type": "task.enqueued",
        "created_at": datetime.now(UTC).isoformat(),
        "envelope_id": envelope_id,
        "issuer": envelope.get("issuer"),
        "target": envelope.get("target"),
        "capability": envelope.get("capability"),
        "payload_ref": envelope.get("payload_ref"),
        "payload_hash": envelope.get("payload_hash"),
        "signature": envelope.get("signature"),
        "signature_algorithm": envelope.get("signature_algorithm"),
        "memory_policy": "separate_no_merge",
        "raw_memory_persisted": False,
    }
    path = profile / FEDERATION_QUEUE_FILENAME
    _append(path, event)
    return {
        "queue_type": "federation_queue",
        "queue_allowed": True,
        "idempotent_reuse": False,
        "queue_path": str(path),
        "event_record": event,
    }


def claim_next_federation_task(
    profile: Path,
    *,
    worker_id: str,
    capabilities: list[str],
) -> dict[str, object]:
    if not worker_id.strip():
        raise ValueError("worker_id must be non-empty")
    path = profile / FEDERATION_QUEUE_FILENAME
    state = project_federation_queue(path)
    candidate = next(
        (
            task
            for task in state["tasks"].values()
            if task["status"] == "pending" and task["capability"] in capabilities
        ),
        None,
    )
    if candidate is None:
        return {
            "queue_type": "federation_queue_claim",
            "claim_allowed": False,
            "task": None,
            "blockers": ["no_compatible_pending_task"],
        }
    event = {
        "event_type": "task.claimed",
        "created_at": datetime.now(UTC).isoformat(),
        "envelope_id": candidate["envelope_id"],
        "worker_id": worker_id,
    }
    _append(path, event)
    return {
        "queue_type": "federation_queue_claim",
        "claim_allowed": True,
        "task": candidate,
        "event_record": event,
        "blockers": [],
    }


def complete_federation_task(
    profile: Path,
    *,
    envelope_id: str,
    worker_id: str,
    result_status: str,
    result_hash: str,
) -> dict[str, object]:
    if result_status not in {"completed", "blocked", "failed"}:
        raise ValueError("invalid result_status")
    path = profile / FEDERATION_QUEUE_FILENAME
    state = project_federation_queue(path)
    task = state["tasks"].get(envelope_id)
    blockers = []
    if task is None:
        blockers.append("task_unknown")
    elif task.get("status") != "claimed":
        blockers.append("task_not_claimed")
    elif task.get("worker_id") != worker_id:
        blockers.append("worker_mismatch")
    if blockers:
        return {
            "queue_type": "federation_queue_complete",
            "completion_allowed": False,
            "blockers": blockers,
        }
    event = {
        "event_type": "task.completed",
        "created_at": datetime.now(UTC).isoformat(),
        "envelope_id": envelope_id,
        "worker_id": worker_id,
        "result_status": result_status,
        "result_hash": result_hash,
        "raw_result_persisted": False,
    }
    _append(path, event)
    return {
        "queue_type": "federation_queue_complete",
        "completion_allowed": True,
        "event_record": event,
        "blockers": [],
    }


def project_federation_queue(path: Path) -> dict[str, object]:
    tasks: dict[str, dict[str, object]] = {}
    events = _load(path)
    for event in events:
        envelope_id = str(event.get("envelope_id", ""))
        if event.get("event_type") == "task.enqueued":
            tasks[envelope_id] = {
                "envelope_id": envelope_id,
                "issuer": event.get("issuer"),
                "target": event.get("target"),
                "capability": event.get("capability"),
                "payload_ref": event.get("payload_ref"),
                "payload_hash": event.get("payload_hash"),
                "signature": event.get("signature"),
                "signature_algorithm": event.get("signature_algorithm"),
                "memory_policy": event.get("memory_policy"),
                "status": "pending",
                "worker_id": None,
                "result_status": None,
                "result_hash": None,
            }
        elif event.get("event_type") == "task.claimed" and envelope_id in tasks:
            tasks[envelope_id]["status"] = "claimed"
            tasks[envelope_id]["worker_id"] = event.get("worker_id")
        elif event.get("event_type") == "task.completed" and envelope_id in tasks:
            tasks[envelope_id]["status"] = "closed"
            tasks[envelope_id]["result_status"] = event.get("result_status")
            tasks[envelope_id]["result_hash"] = event.get("result_hash")
    return {
        "projection_type": "federation_queue_projection",
        "path": str(path),
        "event_count": len(events),
        "task_count": len(tasks),
        "pending_count": sum(task["status"] == "pending" for task in tasks.values()),
        "claimed_count": sum(task["status"] == "claimed" for task in tasks.values()),
        "closed_count": sum(task["status"] == "closed" for task in tasks.values()),
        "tasks": tasks,
    }


def _append(path: Path, event: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, sort_keys=True) + "\n")


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
