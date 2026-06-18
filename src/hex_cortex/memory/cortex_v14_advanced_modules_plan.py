from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_V14_ADVANCED_MODULES_PLAN_FILENAME = "cortex-v14-advanced-modules-plan.jsonl"
PRODUCT_HARDENING_SEAL_FILENAME = "cortex-product-hardening-seal.jsonl"

_V14_MODULES = [
    {
        "module_id": "v14_module_001",
        "module_key": "local_compact_expert_runtime_contract",
        "title": "Local compact expert runtime contract",
        "role": "local_first_specialist_reasoning",
        "architecture_hint": "small local model plus prompt adapter plus optional future LoRA candidate",
        "safety_policy": "advisory_only_no_direct_execution",
        "expected_output": "Define a stable local expert interface before choosing a model backend.",
    },
    {
        "module_id": "v14_module_002",
        "module_key": "latent_world_model_simulation_contract",
        "title": "Latent world-model simulation contract",
        "role": "predict_state_transition_and_surprise",
        "architecture_hint": "JEPA-inspired latent state predictor over memory evidence and planned actions",
        "safety_policy": "simulation_only_no_state_mutation",
        "expected_output": "Define state, action, predicted_state, risk, surprise, and confidence fields.",
    },
    {
        "module_id": "v14_module_003",
        "module_key": "frontier_oracle_fallback_contract",
        "title": "Frontier oracle fallback contract",
        "role": "escalate_uncertain_cases_to_external_frontier_model",
        "architecture_hint": "guarded fallback for audit, synthesis, or ambiguity; local path remains primary",
        "safety_policy": "explicit_gate_required_no_autonomous_write",
        "expected_output": "Define when an external oracle is allowed, what evidence it sees, and how its answer is logged.",
    },
]


def build_cortex_v14_advanced_modules_plan(profile: Path) -> dict[str, object]:
    seal = _latest_jsonl(profile / PRODUCT_HARDENING_SEAL_FILENAME)
    blockers = []
    if not seal:
        blockers.append("missing_product_hardening_seal")
    elif seal.get("hardening_allowed") is not True:
        blockers.append("product_hardening_seal_not_allowed")
    elif seal.get("next_action") != "tag_hex_cortex_v1_3_product_hardened_or_begin_v1_4":
        blockers.append("product_hardening_seal_not_waiting_v1_4")
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "v1_4_advanced_modules_plan_ready" if allowed else "v1_4_advanced_modules_plan_blocked"
    next_action = "prepare_local_compact_expert_runtime_contract" if allowed else "repair_v1_4_advanced_modules_plan"
    reasons = ["product_hardening_seal_ready", "advanced_modules_planned", "runtime_implementation_deferred"] if allowed else blockers
    plan_hash = _hash(
        str(profile),
        str(seal.get("seal_hash") if seal else "missing_seal"),
        decision,
        next_action,
        *[item["module_id"] + item["module_key"] for item in _V14_MODULES],
        *reasons,
    )
    record = {
        "plan_id": f"cortex_v14_advanced_modules_plan_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "source_product_hardening_seal_hash": seal.get("seal_hash") if seal else None,
        "source_hardening_level": seal.get("hardening_level") if seal else None,
        "v14_status": status,
        "v14_decision": decision,
        "v14_allowed": allowed,
        "module_count": len(_V14_MODULES) if allowed else 0,
        "modules": _V14_MODULES if allowed else [],
        "implementation_policy": "contract_first_no_runtime_model_binding_yet" if allowed else "blocked",
        "next_action": next_action,
        "blockers": blockers,
        "reasons": reasons,
        "plan_hash": plan_hash,
    }
    path = profile / CORTEX_V14_ADVANCED_MODULES_PLAN_FILENAME
    records = _load_jsonl(path)
    if not any(item.get("plan_hash") == plan_hash for item in records):
        records.append(record)
    _write_jsonl(path, records)
    return {
        "plan_type": "cortex_v14_advanced_modules_plan",
        "profile_path": str(profile),
        "plan_path": str(path),
        "plan_count": len(records),
        "plan_records": [record],
    }


def summarize_cortex_v14_advanced_modules_plans(path: Path) -> dict[str, object]:
    records = _load_jsonl(path)
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_v14_advanced_modules_plan",
        "path": str(path),
        "exists": path.exists(),
        "total_plan_count": len(records),
        "allowed_plan_count": sum(1 for item in records if item.get("v14_allowed") is True),
        "latest_v14_status": latest.get("v14_status") if latest else None,
        "latest_v14_decision": latest.get("v14_decision") if latest else None,
        "latest_v14_allowed": latest.get("v14_allowed") if latest else None,
        "latest_module_count": latest.get("module_count") if latest else None,
        "latest_implementation_policy": latest.get("implementation_policy") if latest else None,
        "latest_next_action": latest.get("next_action") if latest else None,
        "latest_plan_hash": latest.get("plan_hash") if latest else None,
    }


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
