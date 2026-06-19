from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Callable

from hex_cortex.memory.cortex_compact_world_model import _build_model
from hex_cortex.memory.cortex_compact_world_model import build_cached_dinov2_runner
from hex_cortex.memory.cortex_frozen_encoder import encode_image_to_latent
from hex_cortex.memory.planner_decision_packet import (
    PLANNER_PACKET_FILENAME,
    PlannerDecisionPacketJsonlStore,
)

WORLD_MODEL_ROUTE_FILENAME = "world-model-route.jsonl"
DecisionModelRunner = Callable[
    [Path, Path, Path, dict[str, object], dict[str, object], list[dict[str, object]]],
    dict[str, object],
]


def route_world_model_decision(
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
    active_bundle, blockers = _load_active_bundle(active_registry_path)
    blockers.extend(
        _validate_route_inputs(
            environment_root=environment_root,
            current_image_path=current_image_path,
            goal_image_path=goal_image_path,
            environment_domain=environment_domain,
            action_candidates=action_candidates,
            encoder_descriptor=encoder_descriptor,
            active_bundle=active_bundle,
        )
    )
    if blockers:
        return _blocked_route(blockers)

    runner = model_runner or _run_active_model_candidates
    runtime = runner(
        active_bundle["weights_path"],
        current_image_path.resolve(),
        goal_image_path.resolve(),
        active_bundle["candidate"],
        encoder_descriptor,
        action_candidates,
    )
    if runtime.get("allowed") is not True:
        return _blocked_route(list(runtime.get("blockers", ["active_model_runtime_failed"])))

    current_latent = runtime.get("current_latent")
    goal_latent = runtime.get("goal_latent")
    predictions = runtime.get("predictions")
    if not isinstance(current_latent, list) or not isinstance(goal_latent, list):
        return _blocked_route(["runtime_latents_missing"])
    if not isinstance(predictions, list) or len(predictions) != len(action_candidates):
        return _blocked_route(["runtime_prediction_count_mismatch"])

    baseline_distance = _mse(current_latent, goal_latent)
    ranked_rows: list[dict[str, object]] = []
    distances: list[float] = []
    for candidate, predicted in zip(action_candidates, predictions, strict=True):
        if not isinstance(predicted, list) or len(predicted) != len(goal_latent):
            return _blocked_route(["runtime_prediction_dimension_mismatch"])
        distance = _mse(predicted, goal_latent)
        distances.append(distance)
        improvement = (
            (baseline_distance - distance) / baseline_distance
            if baseline_distance > 1e-12
            else 0.0
        )
        ranked_rows.append(
            {
                "action_id": candidate["action_id"],
                "action_label": candidate.get("action_label", candidate["action_id"]),
                "action_hash": _stable_hash(candidate["action_values"]),
                "predicted_latent_hash": _vector_hash(predicted),
                "predicted_goal_mse": round(distance, 10),
                "improvement_fraction": round(improvement, 8),
            }
        )
    minimum = min(distances)
    maximum = max(distances)
    for row in ranked_rows:
        distance = float(row["predicted_goal_mse"])
        closeness = 1.0 if maximum - minimum <= 1e-12 else 1.0 - (distance - minimum) / (
            maximum - minimum
        )
        positive_improvement = max(0.0, min(1.0, float(row["improvement_fraction"])))
        row["goal_closeness_score"] = round(closeness, 8)
        row["decision_score"] = round(0.7 * closeness + 0.3 * positive_improvement, 8)
    ranked_rows.sort(
        key=lambda row: (
            -float(row["decision_score"]),
            float(row["predicted_goal_mse"]),
            str(row["action_id"]),
        )
    )
    for rank, row in enumerate(ranked_rows, start=1):
        row["rank"] = rank

    planner_context = _load_planner_context(profile) if profile is not None else None
    selected = ranked_rows[0]
    route = {
        "route_type": "active_world_model_decision_route_v1",
        "status": "advisory_ready",
        "environment_domain": environment_domain,
        "active_candidate_hash": active_bundle["active"].get("candidate_hash"),
        "active_registry_hash": active_bundle["active"].get("registry_hash"),
        "encoder_descriptor_hash": encoder_descriptor.get("descriptor_hash"),
        "current_image_hash": runtime.get("current_image_hash"),
        "goal_image_hash": runtime.get("goal_image_hash"),
        "current_latent_hash": runtime.get("current_latent_hash"),
        "goal_latent_hash": runtime.get("goal_latent_hash"),
        "baseline_goal_mse": round(baseline_distance, 10),
        "recommended_action_id": selected["action_id"],
        "recommended_action_label": selected["action_label"],
        "recommended_decision_score": selected["decision_score"],
        "candidate_rankings": ranked_rows,
        "planner_context": planner_context,
        "advisory_only": True,
        "dispatch_allowed": False,
        "execution_performed": False,
        "model_call_performed": True,
        "network_call_performed": False,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": [],
        "next_action": "attach_world_model_advice_to_decision_router",
    }
    route["route_hash"] = _stable_hash(route)
    if route_store_path is not None:
        append_receipt = append_world_model_route(route_store_path, route)
        route["route_store"] = append_receipt
    return route


def bridge_world_model_route_to_planner(
    *,
    profile: Path,
    route: dict[str, object],
    enforce_action_match: bool = False,
) -> dict[str, object]:
    blockers: list[str] = []
    if route.get("route_type") != "active_world_model_decision_route_v1":
        blockers.append("route_type_invalid")
    if route.get("status") != "advisory_ready":
        blockers.append("world_model_route_not_ready")
    if route.get("dispatch_allowed") is not False:
        blockers.append("world_model_route_must_remain_advisory")
    planner_records = PlannerDecisionPacketJsonlStore(
        profile.resolve() / PLANNER_PACKET_FILENAME
    ).load()
    planner = planner_records[-1] if planner_records else None
    if planner is None:
        blockers.append("planner_decision_packet_missing")
    elif planner.action_allowed is not True:
        blockers.append("planner_action_not_allowed")

    action_match = False
    if planner is not None:
        recommendation = {
            str(route.get("recommended_action_id")),
            str(route.get("recommended_action_label")),
        }
        action_match = planner.selected_action in recommendation
        if enforce_action_match and not action_match:
            blockers.append("planner_world_model_action_mismatch")

    blockers = sorted(set(blockers))
    attached = not blockers
    packet = {
        "bridge_type": "world_model_planner_bridge_v1",
        "profile_path": str(profile.resolve()),
        "status": "attached_for_operator_review" if attached else "blocked",
        "planner_packet_id": planner.packet_id if planner is not None else None,
        "planner_selected_action": planner.selected_action if planner is not None else None,
        "planner_action_allowed": planner.action_allowed if planner is not None else False,
        "planner_overall_confidence": planner.overall_confidence if planner is not None else 0.0,
        "world_model_route_hash": route.get("route_hash"),
        "world_model_candidate_hash": route.get("active_candidate_hash"),
        "world_model_recommended_action": route.get("recommended_action_id"),
        "world_model_decision_score": route.get("recommended_decision_score"),
        "action_match": action_match,
        "enforce_action_match": enforce_action_match,
        "context_attached": attached,
        "advisory_only": True,
        "execution_allowed": False,
        "execution_performed": False,
        "blockers": blockers,
        "next_action": "operator_review_world_model_advice" if attached else "repair_router_bridge",
    }
    packet["bridge_hash"] = _stable_hash(packet)
    return packet


def append_world_model_route(path: Path, route: dict[str, object]) -> dict[str, object]:
    if route.get("route_type") != "active_world_model_decision_route_v1":
        raise ValueError("invalid world model route type")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    route_hash = route.get("route_hash")
    if target.is_file():
        with target.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                if not raw_line.strip():
                    continue
                existing = json.loads(raw_line)
                if existing.get("route_hash") == route_hash:
                    return {
                        "append_type": "world_model_route_append_v1",
                        "appended": False,
                        "duplicate": True,
                        "route_hash": route_hash,
                        "path": str(target),
                    }
    with target.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(route, sort_keys=True, separators=(",", ":")) + "\n")
    return {
        "append_type": "world_model_route_append_v1",
        "appended": True,
        "duplicate": False,
        "route_hash": route_hash,
        "path": str(target),
    }


def _load_active_bundle(path: Path) -> tuple[dict[str, object], list[str]]:
    blockers: list[str] = []
    try:
        active = json.loads(path.resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}, ["active_registry_invalid"]
    if not isinstance(active, dict) or active.get("registry_type") != "active_compact_world_model_v1":
        return {}, ["active_registry_type_invalid"]
    root = path.resolve().parent
    candidate_file = active.get("candidate_file")
    weights_file = active.get("weights_file")
    if not isinstance(candidate_file, str) or Path(candidate_file).name != candidate_file:
        blockers.append("active_candidate_filename_invalid")
    if not isinstance(weights_file, str) or Path(weights_file).name != weights_file:
        blockers.append("active_weights_filename_invalid")
    if blockers:
        return {"active": active}, blockers
    candidate_path = root / candidate_file
    weights_path = root / weights_file
    try:
        candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"active": active}, ["active_candidate_invalid"]
    if not isinstance(candidate, dict):
        blockers.append("active_candidate_not_object")
    if not weights_path.is_file():
        blockers.append("active_weights_missing")
    elif _file_hash(weights_path) != active.get("weights_hash"):
        blockers.append("active_weights_hash_mismatch")
    if isinstance(candidate, dict) and candidate.get("candidate_hash") != active.get("candidate_hash"):
        blockers.append("active_candidate_hash_mismatch")
    return {
        "active": active,
        "candidate": candidate,
        "candidate_path": candidate_path,
        "weights_path": weights_path,
    }, blockers


def _validate_route_inputs(
    *,
    environment_root: Path,
    current_image_path: Path,
    goal_image_path: Path,
    environment_domain: str,
    action_candidates: list[dict[str, object]],
    encoder_descriptor: dict[str, object],
    active_bundle: dict[str, object],
) -> list[str]:
    blockers: list[str] = []
    active = active_bundle.get("active")
    candidate = active_bundle.get("candidate")
    if not isinstance(active, dict) or not isinstance(candidate, dict):
        return ["active_bundle_incomplete"]
    if active.get("dataset_domain") != environment_domain:
        blockers.append("active_model_domain_mismatch")
    if active.get("encoder_descriptor_hash") != encoder_descriptor.get("descriptor_hash"):
        blockers.append("active_encoder_descriptor_mismatch")
    output_root = (environment_root.resolve() / "output").resolve()
    for name, path in (("current", current_image_path), ("goal", goal_image_path)):
        resolved = path.resolve()
        if not resolved.is_file():
            blockers.append(f"{name}_image_missing")
        elif not resolved.is_relative_to(output_root):
            blockers.append(f"{name}_image_outside_environment_output")
    config = candidate.get("config")
    action_dim = config.get("action_dim") if isinstance(config, dict) else None
    if not isinstance(action_dim, int):
        blockers.append("active_action_dim_missing")
        return blockers
    if not 1 <= len(action_candidates) <= 64:
        blockers.append("action_candidate_count_out_of_range")
    seen: set[str] = set()
    for index, action in enumerate(action_candidates):
        action_id = action.get("action_id")
        values = action.get("action_values")
        if not isinstance(action_id, str) or not action_id:
            blockers.append(f"action_id_invalid:{index}")
        elif action_id in seen:
            blockers.append(f"action_id_duplicate:{action_id}")
        else:
            seen.add(action_id)
        if not isinstance(values, list) or len(values) != action_dim:
            blockers.append(f"action_dimension_mismatch:{index}")
            continue
        for value in values:
            if not isinstance(value, int | float) or not math.isfinite(float(value)):
                blockers.append(f"action_value_invalid:{index}")
                break
            if abs(float(value)) > 1.0:
                blockers.append(f"action_value_out_of_range:{index}")
                break
    return sorted(set(blockers))


def _run_active_model_candidates(
    weights_path: Path,
    current_image_path: Path,
    goal_image_path: Path,
    candidate: dict[str, object],
    encoder_descriptor: dict[str, object],
    action_candidates: list[dict[str, object]],
) -> dict[str, object]:
    try:
        import torch
        from safetensors.torch import load_file
    except ImportError:
        return {"allowed": False, "blockers": ["torch_or_safetensors_missing"]}
    config = candidate.get("config")
    if not isinstance(config, dict):
        return {"allowed": False, "blockers": ["active_candidate_config_invalid"]}
    runner = build_cached_dinov2_runner()
    current_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=current_image_path,
        include_vector=True,
        runner=runner,
    )
    goal_receipt = encode_image_to_latent(
        descriptor=encoder_descriptor,
        image_path=goal_image_path,
        include_vector=True,
        runner=runner,
    )
    current_latent = current_receipt.pop("volatile_embedding", None)
    goal_latent = goal_receipt.pop("volatile_embedding", None)
    if not isinstance(current_latent, list) or not isinstance(goal_latent, list):
        return {"allowed": False, "blockers": ["environment_encoding_failed"]}
    model = _build_model(
        torch,
        latent_dim=int(config["latent_dim"]),
        action_dim=int(config["action_dim"]),
        hidden_dim=int(config["hidden_dim"]),
    )
    model.load_state_dict(load_file(str(weights_path), device="cpu"))
    model.eval()
    state_tensor = torch.tensor([current_latent], dtype=torch.float32)
    predictions: list[list[float]] = []
    with torch.inference_mode():
        for action in action_candidates:
            action_tensor = torch.tensor([action["action_values"]], dtype=torch.float32)
            predictions.append(model(state_tensor, action_tensor)[0].tolist())
    return {
        "allowed": True,
        "current_latent": current_latent,
        "goal_latent": goal_latent,
        "predictions": predictions,
        "current_image_hash": current_receipt.get("image_hash"),
        "goal_image_hash": goal_receipt.get("image_hash"),
        "current_latent_hash": current_receipt.get("embedding_hash"),
        "goal_latent_hash": goal_receipt.get("embedding_hash"),
        "blockers": [],
    }


def _load_planner_context(profile: Path) -> dict[str, object] | None:
    records = PlannerDecisionPacketJsonlStore(
        profile.resolve() / PLANNER_PACKET_FILENAME
    ).load()
    if not records:
        return None
    latest = records[-1]
    return {
        "packet_id": latest.packet_id,
        "selected_action": latest.selected_action,
        "selected_skill": latest.selected_skill,
        "action_allowed": latest.action_allowed,
        "overall_confidence": latest.overall_confidence,
        "planner_status": latest.planner_status,
        "planner_decision": latest.planner_decision,
    }


def _mse(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        raise ValueError("latent vectors must be non-empty and have equal dimensions")
    return sum((float(a) - float(b)) ** 2 for a, b in zip(left, right, strict=True)) / len(left)


def _vector_hash(vector: list[float]) -> str:
    return _stable_hash([round(float(value), 10) for value in vector])


def _blocked_route(blockers: list[str]) -> dict[str, object]:
    return {
        "route_type": "active_world_model_decision_route_v1",
        "status": "blocked",
        "advisory_only": True,
        "dispatch_allowed": False,
        "execution_performed": False,
        "model_call_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_world_model_route_inputs",
    }


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
