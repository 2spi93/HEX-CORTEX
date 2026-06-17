from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.operator_cockpit_snapshot import (
    OPERATOR_COCKPIT_SNAPSHOT_FILENAME,
    summarize_operator_cockpit_snapshots,
)

OPERATOR_COMMAND_INTAKE_FILENAME = "operator-command-intake.jsonl"
_EXECUTE_WORDS = {"execute", "run", "go", "deploy", "live", "trade", "order", "buy", "sell"}
_ABORT_WORDS = {"abort", "stop", "halt", "cancel", "kill"}
_REPAIR_WORDS = {"repair", "fix", "recover", "rebuild", "rerun"}
_SIMULATE_WORDS = {"simulate", "dry-run", "dryrun", "test", "preview"}
_INSPECT_WORDS = {"inspect", "status", "summary", "show", "view", "explain"}


class OperatorCommandIntakeRecord(BaseModel):
    command_id: str = Field(default_factory=lambda: f"operator_command_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    command_text: str
    command_kind: str
    command_status: str
    command_decision: str
    command_allowed: bool
    command_route: str
    source_cockpit_id: str | None
    source_cockpit_hash: str | None
    cockpit_decision: str | None
    cockpit_mode: str | None
    next_action: str
    blockers: list[str]
    command_hash: str
    reasons: list[str]


class OperatorCommandIntakeJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[OperatorCommandIntakeRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(OperatorCommandIntakeRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid operator command intake {line_number}") from exc
        return records

    def save(self, records: list[OperatorCommandIntakeRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)

    def append(self, record: OperatorCommandIntakeRecord) -> int:
        records = self.load()
        records.append(record)
        return self.save(records)


def ingest_operator_command(profile: Path, command_text: str) -> dict[str, object]:
    record = _record_from_command(profile, command_text)
    path = profile / OPERATOR_COMMAND_INTAKE_FILENAME
    count = OperatorCommandIntakeJsonlStore(path).append(record)
    return {
        "intake_type": "operator_command_intake",
        "profile_path": str(profile),
        "intake_path": str(path),
        "intake_count": count,
        "intake_record": record.model_dump(mode="json"),
    }


def summarize_operator_command_intakes(path: Path) -> dict[str, object]:
    records = OperatorCommandIntakeJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "operator_command_intake",
        "path": str(path),
        "exists": path.exists(),
        "total_intake_count": len(records),
        "latest_command_id": latest.command_id if latest else None,
        "latest_command_kind": latest.command_kind if latest else None,
        "latest_command_status": latest.command_status if latest else None,
        "latest_command_decision": latest.command_decision if latest else None,
        "latest_command_allowed": latest.command_allowed if latest else None,
        "latest_command_route": latest.command_route if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_command_hash": latest.command_hash if latest else None,
    }


def _record_from_command(profile: Path, command_text: str) -> OperatorCommandIntakeRecord:
    command = " ".join(command_text.strip().split())
    cockpit = summarize_operator_cockpit_snapshots(profile / OPERATOR_COCKPIT_SNAPSHOT_FILENAME)
    kind = _classify(command)
    cockpit_ready = cockpit.get("latest_cockpit_allowed") is True and cockpit.get("latest_next_action") == "await_operator_command"
    blockers = _blockers(command, kind, cockpit_ready)
    allowed = not blockers
    route = _route(kind, allowed)
    decision = "operator_command_accepted" if allowed else "operator_command_blocked"
    status = "accepted" if allowed else "blocked"
    next_action = route if allowed else _repair_action(blockers)
    reasons = ["cockpit_ready", f"command_kind_{kind}"] if allowed else blockers
    command_hash = _hash(
        str(profile),
        str(cockpit.get("latest_cockpit_hash")),
        command,
        kind,
        decision,
        next_action,
        *reasons,
    )
    return OperatorCommandIntakeRecord(
        profile_path=str(profile),
        command_text=command,
        command_kind=kind,
        command_status=status,
        command_decision=decision,
        command_allowed=allowed,
        command_route=route,
        source_cockpit_id=_as_string(cockpit.get("latest_cockpit_id")),
        source_cockpit_hash=_as_string(cockpit.get("latest_cockpit_hash")),
        cockpit_decision=_as_string(cockpit.get("latest_cockpit_decision")),
        cockpit_mode=_as_string(cockpit.get("latest_cockpit_mode")),
        next_action=next_action,
        blockers=blockers,
        command_hash=command_hash,
        reasons=reasons,
    )


def _classify(command: str) -> str:
    words = {part.strip(".,:;!?()[]{}\"'").lower() for part in command.split()}
    if words & _EXECUTE_WORDS:
        return "execute"
    if words & _ABORT_WORDS:
        return "abort"
    if words & _REPAIR_WORDS:
        return "repair"
    if words & _SIMULATE_WORDS:
        return "simulate"
    if words & _INSPECT_WORDS:
        return "inspect"
    return "unknown"


def _blockers(command: str, kind: str, cockpit_ready: bool) -> list[str]:
    blockers = []
    if not command:
        blockers.append("command_empty")
    if not cockpit_ready:
        blockers.append("cockpit_not_ready")
    if kind == "unknown":
        blockers.append("command_kind_unknown")
    if kind == "execute":
        blockers.append("execute_requires_separate_gate")
    return blockers


def _route(kind: str, allowed: bool) -> str:
    if not allowed:
        return "no_execution"
    routes = {
        "inspect": "route_inspect",
        "simulate": "route_simulate",
        "repair": "route_repair_plan",
        "abort": "route_abort_and_hold",
    }
    return routes.get(kind, "no_execution")


def _repair_action(blockers: list[str]) -> str:
    if "cockpit_not_ready" in blockers:
        return "build_operator_cockpit_snapshot"
    if "execute_requires_separate_gate" in blockers:
        return "build_execution_authorization_gate"
    return "revise_operator_command"


def _as_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
