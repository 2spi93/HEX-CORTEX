from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_world_model_decision_router import DecisionModelRunner
from hex_cortex.memory.cortex_world_model_decision_router import append_world_model_route
from hex_cortex.memory.cortex_world_model_decision_router import route_world_model_decision


def route_world_model_decision_guarded(
    *,
    active_registry_path: Path,
    environment_root: Path,
    current_image_path: Path,
    goal_image_path: Path,
    environment_domain: str,
    action_candidates: list[dict[str, object]],
    encoder_descriptor: dict[str, object],
    profile: Path | None = None,
    route_store_path: Path | None = None,
    model_runner: DecisionModelRunner | None = None,
) -> dict[str, object]:
    route = route_world_model_decision(
        active_registry_path=active_registry_path,
        environment_root=environment_root,
        current_image_path=current_image_path,
        goal_image_path=goal_image_path,
        environment_domain=environment_domain,
        action_candidates=action_candidates,
        encoder_descriptor=encoder_descriptor,
        profile=profile,
        route_store_path=None,
        model_runner=model_runner,
    )
    if route.get("status") != "advisory_ready":
        return route
    rankings = route.get("candidate_rankings")
    if not isinstance(rankings, list) or not rankings:
        return {
            "route_type": "active_world_model_decision_route_v1",
            "status": "blocked",
            "advisory_only": True,
            "dispatch_allowed": False,
            "execution_performed": False,
            "model_call_performed": bool(route.get("model_call_performed")),
            "blockers": ["candidate_rankings_missing"],
            "next_action": "repair_world_model_route_outputs",
        }

    normalized_rows: list[dict[str, object]] = []
    for raw_row in rankings:
        if not isinstance(raw_row, dict):
            return {
                "route_type": "active_world_model_decision_route_v1",
                "status": "blocked",
                "advisory_only": True,
                "dispatch_allowed": False,
                "execution_performed": False,
                "model_call_performed": bool(route.get("model_call_performed")),
                "blockers": ["candidate_ranking_row_invalid"],
                "next_action": "repair_world_model_route_outputs",
            }
        row = dict(raw_row)
        closeness = _unit_interval(row.get("goal_closeness_score"))
        improvement = _unit_interval(row.get("improvement_fraction"), floor_negative=True)
        decision_score = _unit_interval(0.7 * closeness + 0.3 * improvement)
        row["goal_closeness_score"] = round(closeness, 8)
        row["decision_score"] = round(decision_score, 8)
        normalized_rows.append(row)

    normalized_rows.sort(
        key=lambda row: (
            -float(row["decision_score"]),
            float(row.get("predicted_goal_mse", 0.0)),
            str(row.get("action_id", "")),
        )
    )
    for rank, row in enumerate(normalized_rows, start=1):
        row["rank"] = rank
    selected = normalized_rows[0]
    guarded = dict(route)
    guarded["candidate_rankings"] = normalized_rows
    guarded["recommended_action_id"] = selected.get("action_id")
    guarded["recommended_action_label"] = selected.get("action_label")
    guarded["recommended_decision_score"] = selected.get("decision_score")
    guarded["score_bounds_enforced"] = True
    guarded.pop("route_hash", None)
    guarded.pop("route_store", None)
    guarded["route_hash"] = _stable_hash(guarded)
    if route_store_path is not None:
        guarded["route_store"] = append_world_model_route(route_store_path, guarded)
    return guarded


def _unit_interval(value: object, *, floor_negative: bool = False) -> float:
    if not isinstance(value, int | float):
        return 0.0
    numeric = float(value)
    if floor_negative and numeric < 0.0:
        return 0.0
    return max(0.0, min(1.0, numeric))


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
