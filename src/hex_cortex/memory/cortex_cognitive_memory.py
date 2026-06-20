from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_BASELINE_TYPE = "competency_baseline_v1"
_INTERVENTION_TYPE = "causal_intervention_record_v1"
_SKILL_NODE_TYPE = "cognitive_skill_graph_node_v1"
_ADAPTER_EVENT_TYPE = "cognitive_adapter_registry_event_v1"
_ADAPTER_TRANSITIONS = {
    "candidate": {"evaluated", "rejected"},
    "evaluated": {"promoted", "rejected"},
    "promoted": {"revoked"},
    "rejected": set(),
    "revoked": set(),
}


def append_competency_baseline(
    path: Path,
    *,
    model_id: str,
    suite_ref: str,
    metrics: dict[str, float],
    critical_competencies: Iterable[str],
) -> dict[str, object]:
    if not model_id.strip():
        raise ValueError("model_id must be non-empty")
    if not suite_ref.strip():
        raise ValueError("suite_ref must be non-empty")
    if not metrics:
        raise ValueError("metrics must be non-empty")
    if not all(
        isinstance(name, str)
        and name.strip()
        and isinstance(value, int | float)
        and -1_000_000.0 <= float(value) <= 1_000_000.0
        for name, value in metrics.items()
    ):
        raise ValueError("metrics invalid")
    critical = sorted(set(_clean_values(critical_competencies)))
    unknown = sorted(set(critical).difference(metrics))
    if unknown:
        raise ValueError("critical competency missing from metrics")

    normalized = {name: float(value) for name, value in sorted(metrics.items())}
    record = {
        "record_type": _BASELINE_TYPE,
        "baseline_id": f"cbase_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "model_id_hash": _hash_text(model_id),
        "suite_ref_hash": _hash_text(suite_ref),
        "metrics": normalized,
        "critical_competencies": critical,
        "base_model_checkpoint_required": True,
        "raw_model_identifier_persisted": False,
        "raw_suite_persisted": False,
        "raw_secret_persisted": False,
    }
    record["baseline_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def append_causal_intervention(
    path: Path,
    *,
    residual_signature: str,
    intervention_id: str,
    control_ref: str,
    treatment_ref: str,
    verifier_ref: str,
    outcome_delta: float,
    verified: bool,
) -> dict[str, object]:
    if len(residual_signature) != 64:
        raise ValueError("residual_signature invalid")
    for label, value in {
        "intervention_id": intervention_id,
        "control_ref": control_ref,
        "treatment_ref": treatment_ref,
        "verifier_ref": verifier_ref,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if outcome_delta < -1_000_000.0 or outcome_delta > 1_000_000.0:
        raise ValueError("outcome_delta out of range")

    record = {
        "record_type": _INTERVENTION_TYPE,
        "intervention_record_id": f"cint_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "residual_signature": residual_signature,
        "intervention_id": intervention_id,
        "control_ref_hash": _hash_text(control_ref),
        "treatment_ref_hash": _hash_text(treatment_ref),
        "verifier_ref_hash": _hash_text(verifier_ref),
        "outcome_delta": float(outcome_delta),
        "verified": verified,
        "causal_improvement_observed": verified and outcome_delta > 0.0,
        "raw_control_persisted": False,
        "raw_treatment_persisted": False,
        "raw_secret_persisted": False,
    }
    record["record_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def append_skill_graph_node(
    path: Path,
    *,
    skill_id: str,
    domain: str,
    source_residual_signature: str,
    dependencies: Iterable[str],
    verification_ref: str,
    status: str = "candidate",
) -> dict[str, object]:
    if status not in {"candidate", "active", "revoked"}:
        raise ValueError("skill status invalid")
    for label, value in {
        "skill_id": skill_id,
        "domain": domain,
        "verification_ref": verification_ref,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if len(source_residual_signature) != 64:
        raise ValueError("source_residual_signature invalid")

    rows = read_cognitive_memory(path)
    existing = {
        str(row.get("skill_id"))
        for row in rows
        if row.get("record_type") == _SKILL_NODE_TYPE
    }
    if skill_id in existing:
        raise ValueError("skill_id already exists")
    dependency_list = sorted(set(_clean_values(dependencies)))
    missing_dependencies = sorted(set(dependency_list).difference(existing))
    if missing_dependencies:
        raise ValueError("skill dependency missing")

    record = {
        "record_type": _SKILL_NODE_TYPE,
        "skill_id": skill_id,
        "created_at": datetime.now(UTC).isoformat(),
        "domain": domain,
        "source_residual_signature": source_residual_signature,
        "dependencies": dependency_list,
        "verification_ref_hash": _hash_text(verification_ref),
        "status": status,
        "base_model_independent": True,
        "raw_training_example_persisted": False,
        "raw_secret_persisted": False,
    }
    record["node_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def project_skill_graph(path: Path) -> dict[str, object]:
    nodes = [
        row
        for row in read_cognitive_memory(path)
        if row.get("record_type") == _SKILL_NODE_TYPE
    ]
    by_id = {str(row.get("skill_id")): row for row in nodes}
    missing = sorted(
        {
            dependency
            for row in nodes
            for dependency in row.get("dependencies", [])
            if isinstance(dependency, str) and dependency not in by_id
        }
    )
    cycles = _find_cycles(
        {
            skill_id: [
                item
                for item in row.get("dependencies", [])
                if isinstance(item, str)
            ]
            for skill_id, row in by_id.items()
        }
    )
    active = sorted(
        skill_id
        for skill_id, row in by_id.items()
        if row.get("status") == "active"
    )
    payload = {
        "projection_type": "cognitive_skill_graph_v1",
        "node_count": len(nodes),
        "active_skill_count": len(active),
        "active_skills": active,
        "missing_dependencies": missing,
        "cycles": cycles,
        "graph_valid": not missing and not cycles,
        "raw_training_examples_persisted": False,
        "next_action": "operate_skill_graph" if not missing and not cycles else "repair_skill_graph",
    }
    payload["projection_hash"] = _stable_hash(payload)
    return payload


def register_adapter_candidate(
    path: Path,
    *,
    adapter_id: str,
    base_model_id: str,
    skill_id: str,
    plan_hash: str,
    checkpoint_hash: str,
    reversible: bool,
) -> dict[str, object]:
    for label, value in {
        "adapter_id": adapter_id,
        "base_model_id": base_model_id,
        "skill_id": skill_id,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if len(plan_hash) != 64 or len(checkpoint_hash) != 64:
        raise ValueError("adapter hash invalid")
    if not reversible:
        raise ValueError("adapter candidate must be reversible")
    state = project_adapter_registry(path)
    if adapter_id in state["adapters"]:
        raise ValueError("adapter_id already exists")

    event = {
        "record_type": _ADAPTER_EVENT_TYPE,
        "event_id": f"cadapt_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "adapter_id": adapter_id,
        "event": "registered",
        "status": "candidate",
        "base_model_id_hash": _hash_text(base_model_id),
        "skill_id": skill_id,
        "plan_hash": plan_hash,
        "checkpoint_hash": checkpoint_hash,
        "reversible": True,
        "base_model_immutable": True,
        "raw_weights_persisted": False,
        "raw_secret_persisted": False,
    }
    event["event_hash"] = _stable_hash(event)
    _append_jsonl(path, event)
    return event


def transition_adapter_status(
    path: Path,
    *,
    adapter_id: str,
    new_status: str,
    evaluation_hash: str,
    operator_approved: bool,
) -> dict[str, object]:
    if len(evaluation_hash) != 64:
        raise ValueError("evaluation_hash invalid")
    state = project_adapter_registry(path)
    adapter = state["adapters"].get(adapter_id)
    if not isinstance(adapter, dict):
        raise ValueError("adapter not found")
    current = str(adapter.get("status"))
    if new_status not in _ADAPTER_TRANSITIONS.get(current, set()):
        raise ValueError("adapter status transition invalid")
    if new_status in {"promoted", "revoked"} and not operator_approved:
        raise ValueError("operator approval required")

    event = {
        "record_type": _ADAPTER_EVENT_TYPE,
        "event_id": f"cadapt_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "adapter_id": adapter_id,
        "event": "status_transition",
        "previous_status": current,
        "status": new_status,
        "evaluation_hash": evaluation_hash,
        "operator_approved": operator_approved,
        "reversible": adapter.get("reversible") is True,
        "base_model_immutable": True,
        "raw_weights_persisted": False,
        "raw_secret_persisted": False,
    }
    event["event_hash"] = _stable_hash(event)
    _append_jsonl(path, event)
    return event


def project_adapter_registry(path: Path) -> dict[str, object]:
    rows = [
        row
        for row in read_cognitive_memory(path)
        if row.get("record_type") == _ADAPTER_EVENT_TYPE
    ]
    adapters: dict[str, dict[str, object]] = {}
    for row in rows:
        adapter_id = str(row.get("adapter_id", ""))
        if not adapter_id:
            continue
        if row.get("event") == "registered":
            adapters[adapter_id] = dict(row)
        elif adapter_id in adapters:
            adapters[adapter_id].update(row)
    promoted = sorted(
        adapter_id
        for adapter_id, row in adapters.items()
        if row.get("status") == "promoted"
    )
    revoked = sorted(
        adapter_id
        for adapter_id, row in adapters.items()
        if row.get("status") == "revoked"
    )
    payload = {
        "projection_type": "cognitive_adapter_registry_v1",
        "event_count": len(rows),
        "adapter_count": len(adapters),
        "promoted_adapter_ids": promoted,
        "revoked_adapter_ids": revoked,
        "base_model_immutable": True,
        "adapters": adapters,
        "next_action": "operate_adapter_registry",
    }
    payload["projection_hash"] = _stable_hash(payload)
    return payload


def read_cognitive_memory(path: Path) -> list[dict[str, object]]:
    target = path.resolve()
    if not target.exists():
        return []
    rows: list[dict[str, object]] = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid cognitive memory JSONL at line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"cognitive memory record at line {line_number} must be an object")
        rows.append(payload)
    return rows


def _find_cycles(graph: dict[str, list[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    visited: set[str] = set()
    active: list[str] = []

    def visit(node: str) -> None:
        if node in active:
            index = active.index(node)
            cycle = active[index:] + [node]
            if cycle not in cycles:
                cycles.append(cycle)
            return
        if node in visited:
            return
        active.append(node)
        for dependency in graph.get(node, []):
            visit(dependency)
        active.pop()
        visited.add(node)

    for node in sorted(graph):
        visit(node)
    return cycles


def _clean_values(values: Iterable[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
