from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_V14_RUNTIME_ORCHESTRATOR_FILENAME = "cortex-v14-runtime-orchestrator.jsonl"
LOCAL_COMPACT_EXPERT_CONTRACT_FILENAME = "cortex-local-compact-expert-runtime-contract.jsonl"
LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME = "cortex-latent-world-model-simulation-contract.jsonl"
FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME = "cortex-frontier-oracle-fallback-contract.jsonl"

_ORCHESTRATION_ORDER = [
    "local_compact_expert",
    "latent_world_model_simulation",
    "frontier_oracle_fallback_only_if_gate",
]


def build_cortex_v14_runtime_orchestrator(profile: Path) -> dict[str, object]:
    sources = {
        "local_compact_expert": _latest_jsonl(profile / LOCAL_COMPACT_EXPERT_CONTRACT_FILENAME),
        "latent_world_model_simulation": _latest_jsonl(profile / LATENT_WORLD_MODEL_SIMULATION_CONTRACT_FILENAME),
        "frontier_oracle_fallback": _latest_jsonl(profile / FRONTIER_ORACLE_FALLBACK_CONTRACT_FILENAME),
    }
    blockers = _blockers(sources)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "v1_4_runtime_orchestrator_ready" if allowed else "v1_4_runtime_orchestrator_blocked"
    next_action = "prepare_v14_safety_gate" if allowed else "repair_v14_runtime_orchestrator"
    reasons = [
        "local_compact_expert_contract_ready",
        "latent_world_model_contract_ready",
        "frontier_oracle_contract_ready",
        "orchestration_order_defined",
        "no_runtime_model_binding_yet",
    ] if allowed else blockers
    source_hashes = _source_hashes(sources)
    orchestrator_hash = _hash(
        str(profile),
        decision,
        next_action,
        *_ORCHESTRATION_ORDER,
        *source_hashes.values(),
        *reasons,
    )
    record = {
        "orchestrator_id": f"cortex_v14_runtime_orchestrator_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "orchestrator_status": status,
        "orchestrator_decision": decision,
        "orchestrator_allowed": allowed,
        "orchestration_order": _ORCHESTRATION_ORDER if allowed else [],
        "source_hashes": source_hashes,
        "runtime_binding": "none_contract_orchestrator_only",
        "model_call_policy": "no_model_calls_yet",
        "execution_policy": "no_direct_execution_no_state_mutation",
        "local_path_primary": True if allowed else False,
        "oracle_policy": "gated_fallback_only_after_explicit_operator_gate",
        "receipt_policy": "receipts_required_before_future_mutation",
        "state_policy": "read_contracts_only_write_orchestrator_receipt",
        "verification_commands": ["python -m pytest", "python -m hex_cortex.memory.cortex_v14_runtime_orchestrator_cli .hex-cortex --summary --pretty"],
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "orchestrator_hash": orchestrator_hash,
    }
    path = profile / CORTEX_V14_RUNTIME_ORCHESTRATOR_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("orchestrator_hash") == orchestrator_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {"orchestrator_type": "cortex_v14_runtime_orchestrator", "profile_path": str(profile), "orchestrator_path": str(path), "orchestrator_count": len(records), "orchestrator_records": [record]}


def summarize_cortex_v14_runtime_orchestrators(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_v14_runtime_orchestrator",
        "path": str(path),
        "exists": path.exists(),
        "total_orchestrator_count": len(records),
        "allowed_orchestrator_count": sum(1 for item in records if item.get("orchestrator_allowed") is True),
        "latest_orchestrator_status": latest.get("orchestrator_status") if latest else None,
        "latest_orchestrator_decision": latest.get("orchestrator_decision") if latest else None,
        "latest_orchestrator_allowed": latest.get("orchestrator_allowed") if latest else None,
        "latest_runtime_binding": latest.get("runtime_binding") if latest else None,
        "latest_execution_policy": latest.get("execution_policy") if latest else None,
        "latest_oracle_policy": latest.get("oracle_policy") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_orchestrator_hash": latest.get("orchestrator_hash") if latest else None,
    }


def _blockers(sources: dict[str, dict[str, object] | None]) -> list[str]:
    blockers = []
    local = sources["local_compact_expert"]
    world = sources["latent_world_model_simulation"]
    oracle = sources["frontier_oracle_fallback"]
    if not _allowed(local, "contract_allowed"):
        blockers.append("missing_or_blocked_local_compact_expert_contract")
    elif local.get("next_action") != "prepare_latent_world_model_simulation_contract":
        blockers.append("local_compact_expert_contract_unexpected_next_action")
    if not _allowed(world, "contract_allowed"):
        blockers.append("missing_or_blocked_latent_world_model_contract")
    elif world.get("next_action") != "prepare_frontier_oracle_fallback_contract":
        blockers.append("latent_world_model_contract_unexpected_next_action")
    if not _allowed(oracle, "contract_allowed"):
        blockers.append("missing_or_blocked_frontier_oracle_contract")
    elif oracle.get("next_action") != "prepare_v14_runtime_orchestrator":
        blockers.append("frontier_oracle_contract_unexpected_next_action")
    if oracle and oracle.get("write_policy") != "no_autonomous_write_no_runtime_state_mutation":
        blockers.append("frontier_oracle_write_policy_unexpected")
    return blockers


def _source_hashes(sources: dict[str, dict[str, object] | None]) -> dict[str, str | None]:
    return {
        "local_compact_expert": _field(sources["local_compact_expert"], "contract_hash"),
        "latent_world_model_simulation": _field(sources["latent_world_model_simulation"], "contract_hash"),
        "frontier_oracle_fallback": _field(sources["frontier_oracle_fallback"], "contract_hash"),
    }


def _allowed(row: dict[str, object] | None, key: str) -> bool:
    return bool(row and row.get(key) is True)


def _field(row: dict[str, object] | None, key: str) -> str | None:
    value = row.get(key) if row else None
    return value if isinstance(value, str) else None


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    records = _load_jsonl(path)
    return records[-1] if records else None


def _load_jsonl(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_jsonl(path: Path, records: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
