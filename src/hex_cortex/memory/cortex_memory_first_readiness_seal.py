from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

CORTEX_MEMORY_FIRST_READINESS_SEAL_FILENAME = "cortex-memory-first-readiness-seal.jsonl"


class CortexMemoryFirstReadinessSealRecord(BaseModel):
    seal_id: str = Field(default_factory=lambda: f"cortex_memory_first_readiness_seal_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    learning_event_count: int = Field(ge=0)
    skill_candidate_count: int = Field(ge=0)
    registered_skill_count: int = Field(ge=0)
    activation_gate_count: int = Field(ge=0)
    active_skill_count: int = Field(ge=0)
    latest_skill_key: str | None
    seal_status: str
    seal_decision: str
    seal_allowed: bool
    next_action: str
    blockers: list[str]
    seal_hash: str
    reasons: list[str]


class CortexMemoryFirstReadinessSealJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMemoryFirstReadinessSealRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMemoryFirstReadinessSealRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex memory first readiness seal {line_number}") from exc
        return records

    def save(self, records: list[CortexMemoryFirstReadinessSealRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_memory_first_readiness_seal(profile: Path) -> dict[str, object]:
    learning = _load_jsonl(profile / "cortex-learning-event.jsonl")
    candidates = _load_jsonl(profile / "cortex-skill-candidate.jsonl")
    library = _load_jsonl(profile / "cortex-skill-library.jsonl")
    gates = _load_jsonl(profile / "cortex-skill-activation-gate.jsonl")
    active_index = _load_jsonl(profile / "cortex-active-skill-index.jsonl")
    accepted_learning = [row for row in learning if row.get("event_allowed") is True]
    promotable_candidates = [row for row in candidates if row.get("candidate_allowed") is True and row.get("promote_to_library") is True]
    registered_skills = [row for row in library if row.get("library_allowed") is True and row.get("library_status") == "registered"]
    authorized_gates = [row for row in gates if row.get("gate_allowed") is True and row.get("activation_authorized") is True]
    active_count = _active_skill_count(active_index)
    blockers = []
    if not accepted_learning:
        blockers.append("missing_accepted_learning_event")
    if not promotable_candidates:
        blockers.append("missing_promotable_skill_candidate")
    if not registered_skills:
        blockers.append("missing_registered_skill")
    if not authorized_gates:
        blockers.append("missing_authorized_activation_gate")
    if active_count < 1:
        blockers.append("missing_active_skill_index_entry")
    allowed = not blockers
    status = "sealed" if allowed else "blocked"
    decision = "memory_first_loop_ready" if allowed else "memory_first_loop_not_ready"
    next_action = "use_active_skill_in_controlled_skill_use" if allowed else "repair_memory_first_loop"
    reasons = ["learning_loop_closed", "skill_active_index_ready"] if allowed else blockers
    latest_skill_key = _latest_skill_key(active_index, registered_skills, authorized_gates)
    seal_hash = _hash(
        str(profile),
        str(len(accepted_learning)),
        str(len(promotable_candidates)),
        str(len(registered_skills)),
        str(len(authorized_gates)),
        str(active_count),
        latest_skill_key or "missing_skill_key",
        decision,
        next_action,
        *reasons,
    )
    record = CortexMemoryFirstReadinessSealRecord(
        profile_path=str(profile),
        learning_event_count=len(accepted_learning),
        skill_candidate_count=len(promotable_candidates),
        registered_skill_count=len(registered_skills),
        activation_gate_count=len(authorized_gates),
        active_skill_count=active_count,
        latest_skill_key=latest_skill_key,
        seal_status=status,
        seal_decision=decision,
        seal_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        seal_hash=seal_hash,
        reasons=reasons,
    )
    path = profile / CORTEX_MEMORY_FIRST_READINESS_SEAL_FILENAME
    store = CortexMemoryFirstReadinessSealJsonlStore(path)
    current = store.load()
    count = store.save([*current, record])
    return {
        "seal_type": "cortex_memory_first_readiness_seal",
        "profile_path": str(profile),
        "seal_path": str(path),
        "seal_count": count,
        "seal_records": [record.model_dump(mode="json")],
    }


def summarize_cortex_memory_first_readiness_seals(path: Path) -> dict[str, object]:
    records = CortexMemoryFirstReadinessSealJsonlStore(path).load()
    latest = records[-1] if records else None
    sealed = [record for record in records if record.seal_allowed]
    return {
        "inspect_type": "cortex_memory_first_readiness_seal",
        "path": str(path),
        "exists": path.exists(),
        "total_seal_count": len(records),
        "sealed_count": len(sealed),
        "latest_seal_id": latest.seal_id if latest else None,
        "latest_seal_status": latest.seal_status if latest else None,
        "latest_seal_decision": latest.seal_decision if latest else None,
        "latest_seal_allowed": latest.seal_allowed if latest else None,
        "latest_active_skill_count": latest.active_skill_count if latest else None,
        "latest_skill_key": latest.latest_skill_key if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_seal_hash": latest.seal_hash if latest else None,
    }


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _active_skill_count(active_index: list[dict[str, object]]) -> int:
    if not active_index:
        return 0
    latest = active_index[-1]
    for key in ("active_skill_count", "active_count", "indexed_active_skill_count"):
        value = latest.get(key)
        if isinstance(value, int):
            return value
    active_keys = latest.get("active_skill_keys")
    if isinstance(active_keys, list):
        return len(active_keys)
    return len([row for row in active_index if row.get("active") is True or row.get("index_allowed") is True])


def _latest_skill_key(
    active_index: list[dict[str, object]],
    library: list[dict[str, object]],
    gates: list[dict[str, object]],
) -> str | None:
    for rows in (active_index, library, gates):
        for row in reversed(rows):
            value = row.get("latest_skill_key") or row.get("skill_key")
            if isinstance(value, str) and value:
                return value
    return None


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
