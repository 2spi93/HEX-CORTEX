from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_GOAL_FILENAME = "cortex-goal.jsonl"
CORTEX_COST_FILENAME = "cortex-cost.jsonl"

_DEFAULT_WEIGHTS = {
    "goal_gap": 0.35,
    "risk": 0.20,
    "uncertainty": 0.15,
    "surprise": 0.15,
    "horizon": 0.15,
}


def build_cortex_goal(
    profile: Path,
    *,
    goal_id: str,
    desired_capabilities: list[str],
    target_confidence: float,
    max_horizon_steps: int = 8,
    max_total_cost: float = 0.5,
    priority: float = 0.5,
) -> dict[str, object]:
    blockers = _goal_blockers(
        goal_id=goal_id,
        desired_capabilities=desired_capabilities,
        target_confidence=target_confidence,
        max_horizon_steps=max_horizon_steps,
        max_total_cost=max_total_cost,
        priority=priority,
    )
    allowed = not blockers
    canonical_capabilities = sorted(set(desired_capabilities))
    goal_hash = _hash(
        str(profile),
        goal_id,
        *canonical_capabilities,
        str(target_confidence),
        str(max_horizon_steps),
        str(max_total_cost),
        str(priority),
        *blockers,
    )
    record = {
        "goal_record_id": f"cortex_goal_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "goal_status": "ready" if allowed else "blocked",
        "goal_allowed": allowed,
        "goal_id": goal_id,
        "desired_capabilities": canonical_capabilities,
        "target_confidence": target_confidence,
        "max_horizon_steps": max_horizon_steps,
        "max_total_cost": max_total_cost,
        "priority": priority,
        "next_action": "evaluate_goal_cost" if allowed else "repair_goal",
        "blockers": blockers,
        "goal_hash": goal_hash,
    }
    path = profile / CORTEX_GOAL_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("goal_hash") == goal_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "goal_type": "cortex_goal",
        "goal_path": str(path),
        "goal_count": len(rows),
        "goal_records": [selected],
    }


def evaluate_cortex_cost(
    profile: Path,
    *,
    goal_record: dict[str, object],
    candidate_state: dict[str, object],
    risk_penalty: float = 0.0,
    surprise_score: float = 0.0,
    horizon_steps: int = 1,
    weights: dict[str, float] | None = None,
) -> dict[str, object]:
    selected_weights = dict(_DEFAULT_WEIGHTS if weights is None else weights)
    blockers = _cost_blockers(
        goal_record=goal_record,
        candidate_state=candidate_state,
        risk_penalty=risk_penalty,
        surprise_score=surprise_score,
        horizon_steps=horizon_steps,
        weights=selected_weights,
    )
    allowed = not blockers
    desired = _string_list(goal_record.get("desired_capabilities"))
    actual = _candidate_capabilities(candidate_state)
    target_confidence = _number(
        goal_record.get("target_confidence"),
        default=0.0,
    )
    actual_confidence = _candidate_confidence(candidate_state)
    max_horizon_steps = int(
        _number(goal_record.get("max_horizon_steps"), default=1.0)
    )
    missing = sorted(set(desired) - set(actual))
    unexpected = sorted(set(actual) - set(desired))
    capability_gap = (
        round(len(missing) / len(set(desired)), 4)
        if desired
        else 0.0
    )
    confidence_gap = round(
        max(0.0, target_confidence - actual_confidence),
        4,
    )
    goal_gap = round(0.7 * capability_gap + 0.3 * confidence_gap, 4)
    uncertainty_penalty = round(1.0 - actual_confidence, 4)
    horizon_penalty = round(
        min(1.0, horizon_steps / max(1, max_horizon_steps)),
        4,
    )
    components = {
        "goal_gap": goal_gap,
        "risk": risk_penalty,
        "uncertainty": uncertainty_penalty,
        "surprise": surprise_score,
        "horizon": horizon_penalty,
    }
    total_cost = round(
        sum(
            selected_weights[name] * components[name]
            for name in _DEFAULT_WEIGHTS
        ),
        4,
    )
    progress_score = round(1.0 - goal_gap, 4)
    utility_score = round(1.0 - total_cost, 4)
    max_total_cost = _number(
        goal_record.get("max_total_cost"),
        default=0.0,
    )
    goal_satisfied = (
        not missing
        and actual_confidence >= target_confidence
        and allowed
    )
    within_cost_budget = total_cost <= max_total_cost and allowed
    decision = _decision(
        allowed=allowed,
        goal_satisfied=goal_satisfied,
        within_cost_budget=within_cost_budget,
    )
    candidate_hash = _candidate_hash(candidate_state)
    cost_hash = _hash(
        str(profile),
        str(goal_record.get("goal_hash")),
        candidate_hash,
        str(risk_penalty),
        str(surprise_score),
        str(horizon_steps),
        json.dumps(selected_weights, sort_keys=True),
        *blockers,
    )
    record = {
        "cost_record_id": f"cortex_cost_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "cost_status": "ready" if allowed else "blocked",
        "cost_allowed": allowed,
        "goal_id": goal_record.get("goal_id"),
        "goal_hash": goal_record.get("goal_hash"),
        "candidate_state_hash": candidate_hash,
        "missing_capabilities": missing,
        "unexpected_capabilities": unexpected,
        "actual_confidence": actual_confidence,
        "target_confidence": target_confidence,
        "components": components,
        "weights": selected_weights,
        "total_cost": total_cost,
        "progress_score": progress_score,
        "utility_score": utility_score,
        "goal_satisfied": goal_satisfied,
        "within_cost_budget": within_cost_budget,
        "decision": decision,
        "model_call_performed": False,
        "network_call_performed": False,
        "raw_state_persisted": False,
        "next_action": (
            "propose_actions"
            if allowed
            else "repair_goal_cost_input"
        ),
        "blockers": blockers,
        "cost_hash": cost_hash,
    }
    path = profile / CORTEX_COST_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("cost_hash") == cost_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "cost_type": "cortex_goal_cost",
        "cost_path": str(path),
        "cost_count": len(rows),
        "cost_records": [selected],
    }


def summarize_cortex_costs(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_goal_cost",
        "path": str(path),
        "exists": path.exists(),
        "total_cost_count": len(rows),
        "latest_cost_allowed": latest.get("cost_allowed") if latest else None,
        "latest_goal_id": latest.get("goal_id") if latest else None,
        "latest_total_cost": latest.get("total_cost") if latest else None,
        "latest_decision": latest.get("decision") if latest else None,
    }


def _goal_blockers(
    *,
    goal_id: str,
    desired_capabilities: list[str],
    target_confidence: float,
    max_horizon_steps: int,
    max_total_cost: float,
    priority: float,
) -> list[str]:
    blockers = []
    if not goal_id.strip():
        blockers.append("missing_goal_id")
    if not desired_capabilities or not all(
        isinstance(item, str) and item.strip()
        for item in desired_capabilities
    ):
        blockers.append("desired_capabilities_invalid")
    if not _in_unit_interval(target_confidence):
        blockers.append("target_confidence_out_of_range")
    if max_horizon_steps < 1 or max_horizon_steps > 128:
        blockers.append("max_horizon_steps_out_of_range")
    if not _in_unit_interval(max_total_cost):
        blockers.append("max_total_cost_out_of_range")
    if not _in_unit_interval(priority):
        blockers.append("priority_out_of_range")
    return blockers


def _cost_blockers(
    *,
    goal_record: dict[str, object],
    candidate_state: dict[str, object],
    risk_penalty: float,
    surprise_score: float,
    horizon_steps: int,
    weights: dict[str, float],
) -> list[str]:
    blockers = []
    if goal_record.get("goal_allowed") is not True:
        blockers.append("goal_not_allowed")
    if not isinstance(goal_record.get("goal_hash"), str):
        blockers.append("missing_goal_hash")
    if not _candidate_allowed(candidate_state):
        blockers.append("candidate_state_not_allowed")
    if not _candidate_hash(candidate_state):
        blockers.append("missing_candidate_state_hash")
    if not _in_unit_interval(risk_penalty):
        blockers.append("risk_penalty_out_of_range")
    if not _in_unit_interval(surprise_score):
        blockers.append("surprise_score_out_of_range")
    max_horizon = int(
        _number(goal_record.get("max_horizon_steps"), default=0.0)
    )
    if horizon_steps < 1 or horizon_steps > max_horizon:
        blockers.append("horizon_steps_out_of_range")
    if set(weights) != set(_DEFAULT_WEIGHTS):
        blockers.append("cost_weights_keys_invalid")
    elif not all(_in_unit_interval(value) for value in weights.values()):
        blockers.append("cost_weights_out_of_range")
    elif not math.isclose(sum(weights.values()), 1.0, abs_tol=1e-9):
        blockers.append("cost_weights_sum_invalid")
    return blockers


def _candidate_allowed(candidate_state: dict[str, object]) -> bool:
    return (
        candidate_state.get("state_allowed") is True
        or candidate_state.get("transition_allowed") is True
    )


def _candidate_hash(candidate_state: dict[str, object]) -> str:
    for key in ("state_hash", "predicted_state_hash", "transition_hash"):
        value = candidate_state.get(key)
        if isinstance(value, str):
            return value
    return ""


def _candidate_capabilities(candidate_state: dict[str, object]) -> list[str]:
    for key in ("capabilities", "predicted_capabilities"):
        value = candidate_state.get(key)
        if isinstance(value, list):
            return sorted(
                item for item in value if isinstance(item, str)
            )
    return []


def _candidate_confidence(candidate_state: dict[str, object]) -> float:
    for key in (
        "average_confidence",
        "predicted_average_confidence",
    ):
        value = candidate_state.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return min(1.0, max(0.0, float(value)))
    return 0.0


def _decision(
    *,
    allowed: bool,
    goal_satisfied: bool,
    within_cost_budget: bool,
) -> str:
    if not allowed:
        return "blocked"
    if goal_satisfied and within_cost_budget:
        return "accept_candidate"
    if within_cost_budget:
        return "continue_planning"
    return "reject_candidate"


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(item for item in value if isinstance(item, str))


def _number(value: object, *, default: float) -> float:
    if isinstance(value, int | float) and not isinstance(value, bool):
        return float(value)
    return default


def _in_unit_interval(value: object) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and 0 <= float(value) <= 1
    )


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
