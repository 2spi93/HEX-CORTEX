from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_world_model_simulation_slot import (
    CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME,
    CortexWorldModelSimulationSlotJsonlStore,
    CortexWorldModelSimulationSlotRecord,
)

CORTEX_FRONTIER_ORACLE_FALLBACK_FILENAME = "cortex-frontier-oracle-fallback.jsonl"


class CortexFrontierOracleFallbackRecord(BaseModel):
    fallback_id: str = Field(default_factory=lambda: f"cortex_frontier_oracle_fallback_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_simulation_id: str | None
    source_simulation_hash: str | None
    selected_skill_key: str | None
    selected_domain: str | None
    benefit_score: float = Field(ge=0.0, le=1.0)
    risk_score: float = Field(ge=0.0, le=1.0)
    surprise_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    oracle_mode: str | None
    oracle_required: bool
    oracle_recommendation: str | None
    local_path_remains_primary: bool
    fallback_status: str
    fallback_decision: str
    fallback_allowed: bool
    next_action: str
    blockers: list[str]
    fallback_hash: str
    reasons: list[str]


class CortexFrontierOracleFallbackJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexFrontierOracleFallbackRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexFrontierOracleFallbackRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex frontier oracle fallback {line_number}") from exc
        return records

    def save(self, records: list[CortexFrontierOracleFallbackRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_frontier_oracle_fallback(profile: Path) -> dict[str, object]:
    simulation = _latest_simulation(profile)
    record = _fallback_record(profile, simulation)
    path = profile / CORTEX_FRONTIER_ORACLE_FALLBACK_FILENAME
    store = CortexFrontierOracleFallbackJsonlStore(path)
    current = store.load()
    if record.source_simulation_hash and any(item.source_simulation_hash == record.source_simulation_hash for item in current):
        records: list[CortexFrontierOracleFallbackRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "fallback_type": "cortex_frontier_oracle_fallback",
        "profile_path": str(profile),
        "fallback_path": str(path),
        "fallback_count": count,
        "fallback_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_frontier_oracle_fallbacks(path: Path) -> dict[str, object]:
    records = CortexFrontierOracleFallbackJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.fallback_allowed]
    return {
        "inspect_type": "cortex_frontier_oracle_fallback",
        "path": str(path),
        "exists": path.exists(),
        "total_fallback_count": len(records),
        "allowed_fallback_count": len(allowed),
        "latest_fallback_id": latest.fallback_id if latest else None,
        "latest_fallback_status": latest.fallback_status if latest else None,
        "latest_fallback_decision": latest.fallback_decision if latest else None,
        "latest_fallback_allowed": latest.fallback_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_oracle_mode": latest.oracle_mode if latest else None,
        "latest_oracle_required": latest.oracle_required if latest else None,
        "latest_local_path_remains_primary": latest.local_path_remains_primary if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_fallback_hash": latest.fallback_hash if latest else None,
    }


def _latest_simulation(profile: Path) -> CortexWorldModelSimulationSlotRecord | None:
    records = CortexWorldModelSimulationSlotJsonlStore(profile / CORTEX_WORLD_MODEL_SIMULATION_SLOT_FILENAME).load()
    return records[-1] if records else None


def _fallback_record(profile: Path, simulation: CortexWorldModelSimulationSlotRecord | None) -> CortexFrontierOracleFallbackRecord:
    blockers = _blockers(simulation)
    allowed = not blockers
    oracle_required = _oracle_required(simulation) if simulation and allowed else False
    oracle_mode = "rare_audit_recommended" if oracle_required else ("standby_audit" if allowed else None)
    recommendation = _oracle_recommendation(simulation, oracle_required) if simulation and allowed else None
    status = "ready" if allowed else "blocked"
    decision = "frontier_oracle_fallback_ready" if allowed else "frontier_oracle_fallback_blocked"
    next_action = "prepare_ui_cockpit_readiness" if allowed else "repair_frontier_oracle_fallback"
    reasons = ["world_model_ready", "local_path_primary", "oracle_guarded"] if allowed else blockers
    fallback_hash = _hash(
        str(profile),
        simulation.simulation_hash if simulation else "missing_simulation",
        simulation.selected_skill_key if simulation and simulation.selected_skill_key else "missing_skill",
        oracle_mode or "missing_oracle_mode",
        str(oracle_required),
        decision,
        next_action,
        *reasons,
    )
    return CortexFrontierOracleFallbackRecord(
        profile_path=str(profile),
        source_simulation_id=simulation.simulation_id if simulation else None,
        source_simulation_hash=simulation.simulation_hash if simulation else None,
        selected_skill_key=simulation.selected_skill_key if simulation else None,
        selected_domain=simulation.selected_domain if simulation else None,
        benefit_score=simulation.benefit_score if simulation else 0.0,
        risk_score=simulation.risk_score if simulation else 1.0,
        surprise_score=simulation.surprise_score if simulation else 1.0,
        confidence_score=simulation.confidence_score if simulation else 0.0,
        oracle_mode=oracle_mode,
        oracle_required=oracle_required,
        oracle_recommendation=recommendation,
        local_path_remains_primary=allowed,
        fallback_status=status,
        fallback_decision=decision,
        fallback_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        fallback_hash=fallback_hash,
        reasons=reasons,
    )


def _blockers(simulation: CortexWorldModelSimulationSlotRecord | None) -> list[str]:
    blockers = []
    if simulation is None:
        return ["missing_world_model_simulation"]
    if simulation.simulation_allowed is not True:
        blockers.append("world_model_simulation_not_allowed")
    if simulation.simulation_decision != "world_model_simulation_ready":
        blockers.append("world_model_simulation_not_ready")
    if simulation.next_action != "prepare_frontier_oracle_fallback":
        blockers.append("simulation_not_waiting_oracle_fallback")
    if not simulation.selected_skill_key:
        blockers.append("missing_selected_skill")
    return blockers


def _oracle_required(simulation: CortexWorldModelSimulationSlotRecord) -> bool:
    if simulation.risk_score >= 0.35:
        return True
    if simulation.surprise_score >= 0.35:
        return True
    if simulation.confidence_score < 0.70:
        return True
    return False


def _oracle_recommendation(simulation: CortexWorldModelSimulationSlotRecord, required: bool) -> str:
    if required:
        return "Run frontier oracle audit before using the compact local expert output for high-impact guidance."
    return "Keep frontier oracle in standby; local compact expert path remains sufficient for this low-risk simulation."


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
