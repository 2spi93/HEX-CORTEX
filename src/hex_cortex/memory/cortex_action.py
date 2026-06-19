from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hex_cortex.memory.cortex_goal import evaluate_cortex_cost
from hex_cortex.memory.cortex_outputs import get_cortex_output

CORTEX_ACTION_FILENAME = "cortex-action.jsonl"


def build_default_action_candidates(
    *,
    goal_record: dict[str, object],
    current_state: dict[str, object],
) -> list[dict[str, object]]:
    desired = _string_list(goal_record.get("desired_capabilities"))
    current = _state_capabilities(current_state)
    missing = sorted(set(desired) - set(current))
    candidates: list[dict[str, object]] = []
    if missing:
        candidates.append(
            {
                "action_id": "acquire_missing_capabilities",
                "output_id": "request_tool",
                "expected_capabilities": missing,
                "confidence_delta": 0.10,
                "risk_penalty": 0.20,
                "surprise_score": 0.20,
                "horizon_steps": 1,
            }
        )
    candidates.extend(
        [
            {
                "action_id": "increase_confidence",
                "output_id": "generate_plan",
                "expected_capabilities": [],
                "confidence_delta": 0.15,
                "risk_penalty": 0.05,
                "surprise_score": 0.10,
                "horizon_steps": 1,
            },
            {
                "action_id": "hold_and_review",
                "output_id": "write_text",
                "expected_capabilities": [],
                "confidence_delta": 0.0,
                "risk_penalty": 0.0,
                "surprise_score": 0.0,
                "horizon_steps": 1,
            },
        ]
    )
    return candidates


def build_cortex_action_proposals(
    profile: Path,
    *,
    goal_record: dict[str, object],
    current_state: dict[str, object],
    candidate_actions: list[dict[str, object]] | None = None,
    top_k: int = 3,
) -> dict[str, object]:
    actions = (
        build_default_action_candidates(
            goal_record=goal_record,
            current_state=current_state,
        )
        if candidate_actions is None
        else candidate_actions
    )
    blockers = _proposal_blockers(
        goal_record=goal_record,
        current_state=current_state,
        candidate_actions=actions,
        top_k=top_k,
    )
    allowed = not blockers
    ranked: list[dict[str, object]] = []
    if allowed:
        ranked = _rank_actions(
            profile=profile,
            goal_record=goal_record,
            current_state=current_state,
            candidate_actions=actions,
        )
    limited = ranked[:top_k]
    recommended = next(
        (
            item
            for item in limited
            if item.get("within_cost_budget") is True
        ),
        None,
    )
    recommendation_allowed = recommended is not None and allowed
    proposal_hash = _hash(
        str(profile),
        str(goal_record.get("goal_hash")),
        _state_hash(current_state),
        json.dumps(actions, sort_keys=True),
        str(top_k),
        *blockers,
    )
    record = {
        "proposal_id": f"cortex_action_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "proposal_status": "ready" if allowed else "blocked",
        "proposal_allowed": allowed,
        "goal_id": goal_record.get("goal_id"),
        "goal_hash": goal_record.get("goal_hash"),
        "source_state_hash": _state_hash(current_state),
        "candidate_count": len(actions),
        "ranked_action_count": len(limited),
        "ranked_actions": limited,
        "recommended_action_id": (
            recommended.get("action_id") if recommended else None
        ),
        "recommended_requires_operator": (
            recommended.get("requires_operator") if recommended else None
        ),
        "recommendation_allowed": recommendation_allowed,
        "action_executed": False,
        "model_call_performed": False,
        "network_call_performed": False,
        "next_action": _next_action(recommended, allowed),
        "blockers": blockers,
        "proposal_hash": proposal_hash,
    }
    path = profile / CORTEX_ACTION_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("proposal_hash") == proposal_hash),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "proposal_type": "cortex_action_proposal",
        "proposal_path": str(path),
        "proposal_count": len(rows),
        "proposal_records": [selected],
    }


def summarize_cortex_action_proposals(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_action_proposal",
        "path": str(path),
        "exists": path.exists(),
        "total_proposal_count": len(rows),
        "latest_proposal_allowed": (
            latest.get("proposal_allowed") if latest else None
        ),
        "latest_recommended_action_id": (
            latest.get("recommended_action_id") if latest else None
        ),
        "latest_next_action": (
            latest.get("next_action") if latest else None
        ),
    }


def _rank_actions(
    *,
    profile: Path,
    goal_record: dict[str, object],
    current_state: dict[str, object],
    candidate_actions: list[dict[str, object]],
) -> list[dict[str, object]]:
    ranked = []
    current_capabilities = _state_capabilities(current_state)
    current_confidence = _state_confidence(current_state)
    source_hash = _state_hash(current_state)
    for action in candidate_actions:
        output = get_cortex_output(str(action["output_id"]))
        predicted_capabilities = sorted(
            set(current_capabilities).union(
                _string_list(action.get("expected_capabilities"))
            )
        )
        predicted_confidence = round(
            min(
                1.0,
                max(
                    0.0,
                    current_confidence
                    + float(action.get("confidence_delta", 0.0)),
                ),
            ),
            4,
        )
        action_hash = _hash(
            source_hash,
            json.dumps(action, sort_keys=True),
        )
        candidate_state = {
            "transition_allowed": True,
            "transition_hash": action_hash,
            "predicted_state_hash": _hash(
                action_hash,
                *predicted_capabilities,
                str(predicted_confidence),
            ),
            "predicted_capabilities": predicted_capabilities,
            "predicted_average_confidence": predicted_confidence,
        }
        cost = evaluate_cortex_cost(
            profile,
            goal_record=goal_record,
            candidate_state=candidate_state,
            risk_penalty=float(action.get("risk_penalty", 0.0)),
            surprise_score=float(action.get("surprise_score", 0.0)),
            horizon_steps=int(action.get("horizon_steps", 1)),
        )["cost_records"][0]
        ranked.append(
            {
                "action_id": action["action_id"],
                "output_id": action["output_id"],
                "requires_operator": output.get("requires_operator") is True,
                "expected_capabilities": predicted_capabilities,
                "predicted_confidence": predicted_confidence,
                "predicted_state_hash": candidate_state[
                    "predicted_state_hash"
                ],
                "horizon_steps": action.get("horizon_steps"),
                "total_cost": cost.get("total_cost"),
                "utility_score": cost.get("utility_score"),
                "progress_score": cost.get("progress_score"),
                "goal_satisfied": cost.get("goal_satisfied"),
                "within_cost_budget": cost.get("within_cost_budget"),
                "decision": cost.get("decision"),
                "cost_hash": cost.get("cost_hash"),
                "action_hash": action_hash,
            }
        )
    return sorted(
        ranked,
        key=lambda item: (
            float(item.get("total_cost", 1.0)),
            bool(item.get("requires_operator")),
            int(item.get("horizon_steps", 1)),
            str(item.get("action_id", "")),
        ),
    )


def _proposal_blockers(
    *,
    goal_record: dict[str, object],
    current_state: dict[str, object],
    candidate_actions: list[dict[str, object]],
    top_k: int,
) -> list[str]:
    blockers = []
    if goal_record.get("goal_allowed") is not True:
        blockers.append("goal_not_allowed")
    if not isinstance(goal_record.get("goal_hash"), str):
        blockers.append("missing_goal_hash")
    if current_state.get("state_allowed") is not True:
        blockers.append("current_state_not_allowed")
    if not _state_hash(current_state):
        blockers.append("missing_current_state_hash")
    if not isinstance(candidate_actions, list) or not candidate_actions:
        blockers.append("candidate_actions_missing")
        return blockers
    if len(candidate_actions) > 32:
        blockers.append("candidate_actions_limit_exceeded")
    if top_k < 1 or top_k > 10:
        blockers.append("top_k_out_of_range")
    action_ids = []
    max_horizon = int(goal_record.get("max_horizon_steps", 0))
    for index, action in enumerate(candidate_actions):
        prefix = f"action_{index}"
        action_id = action.get("action_id")
        if not isinstance(action_id, str) or not action_id.strip():
            blockers.append(f"{prefix}_id_invalid")
        else:
            action_ids.append(action_id)
        output_id = action.get("output_id")
        output = get_cortex_output(str(output_id))
        if output.get("state") == "blocked":
            blockers.append(f"{prefix}_output_unknown")
        expected = action.get("expected_capabilities", [])
        if not isinstance(expected, list) or not all(
            isinstance(item, str) for item in expected
        ):
            blockers.append(f"{prefix}_capabilities_invalid")
        delta = action.get("confidence_delta", 0.0)
        if not _bounded_number(delta, -1.0, 1.0):
            blockers.append(f"{prefix}_confidence_delta_invalid")
        for name in ("risk_penalty", "surprise_score"):
            if not _bounded_number(action.get(name, 0.0), 0.0, 1.0):
                blockers.append(f"{prefix}_{name}_invalid")
        horizon = action.get("horizon_steps", 1)
        if (
            not isinstance(horizon, int)
            or isinstance(horizon, bool)
            or horizon < 1
            or horizon > max_horizon
        ):
            blockers.append(f"{prefix}_horizon_invalid")
    if len(action_ids) != len(set(action_ids)):
        blockers.append("duplicate_action_ids")
    return blockers


def _next_action(
    recommended: dict[str, object] | None,
    allowed: bool,
) -> str:
    if not allowed:
        return "repair_action_proposal"
    if recommended is None:
        return "revise_action_candidates"
    if recommended.get("requires_operator") is True:
        return "request_operator_for_action"
    return "review_action_proposal"


def _state_capabilities(state: dict[str, object]) -> list[str]:
    return _string_list(state.get("capabilities"))


def _state_confidence(state: dict[str, object]) -> float:
    value = state.get("average_confidence")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return min(1.0, max(0.0, float(value)))
    return 0.0


def _state_hash(state: dict[str, object]) -> str:
    value = state.get("state_hash")
    return value if isinstance(value, str) else ""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted(item for item in value if isinstance(item, str))


def _bounded_number(value: object, minimum: float, maximum: float) -> bool:
    return (
        isinstance(value, int | float)
        and not isinstance(value, bool)
        and minimum <= float(value) <= maximum
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
