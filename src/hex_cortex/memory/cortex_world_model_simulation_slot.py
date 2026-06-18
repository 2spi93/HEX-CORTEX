from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_local_compact_expert_adapter import (
    CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME,
    CortexLocalCompactExpertAdapterJsonlStore,
    CortexLocalCompactExpertAdapterRecord,
)

CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME = "cortex-world-model-simulation-slot.jsonl"


class CortexWorldModelSimulationSlotRecord(BaseModel):
    simulation_id: str = Field(default_factory=lambda: f"cortex_world_model_simulation_slot_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_adapter_id: str | None
    source_adapter_hash: str | None
    selected_skill_key: str | None
    selected_domain: str | None
    expert_kind: str | None
    candidate_action: str
    current_state_summary: str
    predicted_next_state_summary: str
    benefit_score: float = Field(ge=0.0, le=1.0)
    cost_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    surprise_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    simulation_status: str
    simulation_decision: str
    simulation_allowed: bool
    next_action: str
    blockers: list[str]
    simulation_hash: str
    reasons: list[str]


class CortexWorldModelSimulationSlotJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexWorldModelSimulationSlotRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexWorldModelSimulationSlotRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex world model simulation slot {line_number}") from exc
        return records

    def save(self, records: list[CortexWorldModelSimulationSlotRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_world_model_simulation_slot(profile: Path) -> dict[str, object]:
    adapter = _latest_adapter(profile)
    record = _simulation_record(profile, adapter)
    path = profile / CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME
    store = CortexWorldModelSimulationSlotJsonlStore(path)
    current = store.load()
    if record.source_adapter_hash and any(item.source_adapter_hash == record.source_adapter_hash for item in current):
        records: list[CortexWorldModelSimulationSlotRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "simulation_type": "cortex_world_model_simulation_slot",
        "profile_path": str(profile),
        "simulation_path": str(path),
        "simulation_count": count,
        "simulation_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_world_model_simulation_slots(path: Path) -> dict[str, object]:
    records = CortexWorldModelSimulationSlotJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.simulation_allowed]
    return {
        "inspect_type": "cortex_world_model_simulation_slot",
        "path": str(path),
        "exists": path.exists(),
        "total_simulation_count": len(records),
        "allowed_simulation_count": len(allowed),
        "latest_simulation_id": latest.simulation_id if latest else None,
        "latest_simulation_status": latest.simulation_status if latest else None,
        "latest_simulation_decision": latest.simulation_decision if latest else None,
        "latest_simulation_allowed": latest.simulation_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_benefit_score": latest.benefit_score if latest else None,
        "latest_cost_score": latest.cost_score if latest else None,
        "latest_risk_score": latest.risk_score if latest else None,
        "latest_surprise_score": latest.surprise_score if latest else None,
        "latest_confidence_score": latest.confidence_score if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_simulation_hash": latest.simulation_hash if latest else None,
    }


def _latest_adapter(profile: Path) -> CortexLocalCompactExpertAdapterRecord | None:
    records = CortexLocalCompactExpertAdapterJsonlStore(profile / CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME).load()
    return records[-1] if records else None


def _simulation_record(profile: Path, adapter: CortexLocalCompactExpertAdapterRecord | None) -> CortexWorldModelSimulationSlotRecord:
    blockers = _blockers(adapter)
    allowed = not blockers
    benefit_score = 0.90 if allowed else 0.0
    cost_score = 0.20 if allowed else 1.0
    risk_score = 0.15 if allowed else 1.0
    surprise_score = 0.10 if allowed else 1.0
    confidence_score = 0.88 if allowed else 0.0
    status = "ready" if allowed else "blocked"
    decision = "world_model_simulation_ready" if allowed else "world_model_simulation_blocked"
    next_action = "prepare_frontier_oracle_fallback" if allowed else "repair_world_model_simulation_slot"
    reasons = ["adapter_ready", "latent_simulation_prepared", "low_surprise_prediction"] if allowed else blockers
    candidate_action = "prepare_frontier_oracle_fallback"
    current_state = _current_state_summary(adapter) if adapter else "missing adapter state"
    predicted_state = _predicted_next_state_summary(adapter) if adapter else "simulation blocked pending adapter repair"
    simulation_hash = _hash(
        str(profile),
        adapter.adapter_hash if adapter else "missing_adapter",
        adapter.selected_skill_key if adapter and adapter.selected_skill_key else "missing_skill",
        str(benefit_score),
        str(cost_score),
        str(risk_score),
        str(surprise_score),
        decision,
        next_action,
        *reasons,
    )
    return CortexWorldModelSimulationSlotRecord(
        profile_path=str(profile),
        source_adapter_id=adapter.adapter_id if adapter else None,
        source_adapter_hash=adapter.adapter_hash if adapter else None,
        selected_skill_key=adapter.selected_skill_key if adapter else None,
        selected_domain=adapter.selected_domain if adapter else None,
        expert_kind=adapter.expert_kind if adapter else None,
        candidate_action=candidate_action,
        current_state_summary=current_state,
        predicted_next_state_summary=predicted_state,
        benefit_score=benefit_score,
        cost_score=cost_score,
        risk_score=risk_score,
        surprise_score=surprise_score,
        confidence_score=confidence_score,
        simulation_status=status,
        simulation_decision=decision,
        simulation_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        simulation_hash=simulation_hash,
        reasons=reasons,
    )


def _blockers(adapter: CortexLocalCompactExpertAdapterRecord | None) -> list[str]:
    blockers = []
    if adapter is None:
        return ["missing_local_compact_expert_adapter"]
    if adapter.adapter_allowed is not True:
        blockers.append("local_compact_expert_adapter_not_allowed")
    if adapter.adapter_decision != "local_compact_expert_adapter_ready":
        blockers.append("local_compact_expert_adapter_not_ready")
    if adapter.next_action != "prepare_world_model_simulation_slot":
        blockers.append("adapter_not_waiting_world_model_slot")
    if not adapter.selected_skill_key or not adapter.expert_kind:
        blockers.append("missing_selected_skill_or_expert")
    if adapter.selected_route_score < 0.75:
        blockers.append("selected_route_score_below_world_model_threshold")
    return blockers


def _current_state_summary(adapter: CortexLocalCompactExpertAdapterRecord) -> str:
    return (
        f"Selected {adapter.selected_skill_key} for {adapter.selected_domain}; "
        f"expert={adapter.expert_kind}; policy={adapter.model_policy}; route_score={adapter.selected_route_score}."
    )


def _predicted_next_state_summary(adapter: CortexLocalCompactExpertAdapterRecord) -> str:
    return (
        "A frontier oracle fallback can be prepared for exceptional audit cases while the compact local expert remains the default path; "
        "no direct execution is introduced."
    )


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
