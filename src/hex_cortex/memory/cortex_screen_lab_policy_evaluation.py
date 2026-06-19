from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Callable

from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records
from hex_cortex.memory.cortex_world_model_decision_router import route_world_model_decision

DecisionRouter = Callable[..., dict[str, object]]


def evaluate_screen_lab_policy(
    *,
    active_registry_path: Path,
    environment_root: Path,
    dataset_jsonl: Path,
    environment_domain: str,
    action_candidates: list[dict[str, object]],
    encoder_descriptor: dict[str, object],
    split: str = "test",
    minimum_samples: int = 4,
    minimum_top1_accuracy: float = 1.0,
    minimum_positive_improvement_rate: float = 1.0,
    decision_router: DecisionRouter | None = None,
) -> dict[str, object]:
    blockers = _validate_thresholds(
        split=split,
        minimum_samples=minimum_samples,
        minimum_top1_accuracy=minimum_top1_accuracy,
        minimum_positive_improvement_rate=minimum_positive_improvement_rate,
    )
    if blockers:
        return _blocked_evaluation(blockers)
    try:
        records = load_transition_records(dataset_jsonl)
    except (OSError, ValueError):
        return _blocked_evaluation(["dataset_invalid"])

    action_ids = [candidate.get("action_id") for candidate in action_candidates]
    if not action_candidates or any(not isinstance(action_id, str) or not action_id for action_id in action_ids):
        return _blocked_evaluation(["action_candidates_invalid"])
    if len(set(action_ids)) != len(action_ids):
        return _blocked_evaluation(["action_candidate_ids_duplicate"])

    evaluation_records = [
        record
        for record in records
        if record.get("split") == split
        and record.get("domain") == environment_domain
        and record.get("source_kind") == "real_environment_sequence_v1"
    ]
    if len(evaluation_records) < minimum_samples:
        return _blocked_evaluation(
            ["insufficient_policy_evaluation_samples"],
            sample_count=len(evaluation_records),
        )

    router = decision_router or route_world_model_decision
    rows: list[dict[str, object]] = []
    route_blockers: list[str] = []
    output_root = (environment_root.resolve() / "output").resolve()
    for index, record in enumerate(evaluation_records):
        actual_action = record.get("action_id")
        if not isinstance(actual_action, str) or actual_action not in action_ids:
            route_blockers.append(f"record_{index}:actual_action_missing_from_candidates")
            continue
        current_image = _resolve_output_ref(output_root, record.get("current_image_ref"))
        next_image = _resolve_output_ref(output_root, record.get("next_image_ref"))
        if current_image is None:
            route_blockers.append(f"record_{index}:current_image_ref_invalid")
            continue
        if next_image is None:
            route_blockers.append(f"record_{index}:next_image_ref_invalid")
            continue
        route = router(
            active_registry_path=active_registry_path,
            environment_root=environment_root,
            current_image_path=current_image,
            goal_image_path=next_image,
            environment_domain=environment_domain,
            action_candidates=action_candidates,
            encoder_descriptor=encoder_descriptor,
            profile=None,
            route_store_path=None,
        )
        if route.get("status") != "advisory_ready":
            for blocker in route.get("blockers", ["route_not_ready"]):
                route_blockers.append(f"record_{index}:{blocker}")
            continue
        rankings = route.get("candidate_rankings")
        if not isinstance(rankings, list):
            route_blockers.append(f"record_{index}:candidate_rankings_missing")
            continue
        actual_row = next(
            (
                row
                for row in rankings
                if isinstance(row, dict) and row.get("action_id") == actual_action
            ),
            None,
        )
        if actual_row is None:
            route_blockers.append(f"record_{index}:actual_action_not_ranked")
            continue
        actual_rank = actual_row.get("rank")
        actual_score = actual_row.get("decision_score")
        actual_improvement = actual_row.get("improvement_fraction")
        if not isinstance(actual_rank, int) or actual_rank < 1:
            route_blockers.append(f"record_{index}:actual_rank_invalid")
            continue
        if not isinstance(actual_score, int | float):
            route_blockers.append(f"record_{index}:actual_score_invalid")
            continue
        if not isinstance(actual_improvement, int | float):
            route_blockers.append(f"record_{index}:actual_improvement_invalid")
            continue
        other_scores = [
            float(row["decision_score"])
            for row in rankings
            if isinstance(row, dict)
            and row.get("action_id") != actual_action
            and isinstance(row.get("decision_score"), int | float)
        ]
        best_other_score = max(other_scores) if other_scores else 0.0
        rows.append(
            {
                "sample_id": record.get("sample_id"),
                "episode_id": record.get("episode_id"),
                "step_index": record.get("step_index"),
                "actual_action_id": actual_action,
                "recommended_action_id": route.get("recommended_action_id"),
                "actual_action_rank": actual_rank,
                "actual_action_decision_score": round(float(actual_score), 8),
                "actual_action_improvement_fraction": round(float(actual_improvement), 8),
                "correct_action_score_margin": round(float(actual_score) - best_other_score, 8),
                "route_hash": route.get("route_hash"),
                "top1_correct": actual_rank == 1,
                "top2_correct": actual_rank <= 2,
            }
        )

    if route_blockers:
        return _blocked_evaluation(route_blockers, sample_count=len(rows), rows=rows)
    if len(rows) < minimum_samples:
        return _blocked_evaluation(
            ["insufficient_successful_policy_routes"],
            sample_count=len(rows),
            rows=rows,
        )

    sample_count = len(rows)
    top1_accuracy = sum(bool(row["top1_correct"]) for row in rows) / sample_count
    top2_accuracy = sum(bool(row["top2_correct"]) for row in rows) / sample_count
    mean_reciprocal_rank = sum(
        1.0 / int(row["actual_action_rank"]) for row in rows
    ) / sample_count
    positive_improvement_rate = sum(
        float(row["actual_action_improvement_fraction"]) > 0.0 for row in rows
    ) / sample_count
    mean_correct_action_margin = sum(
        float(row["correct_action_score_margin"]) for row in rows
    ) / sample_count

    gate_blockers: list[str] = []
    if top1_accuracy + 1e-12 < minimum_top1_accuracy:
        gate_blockers.append("top1_action_accuracy_below_threshold")
    if positive_improvement_rate + 1e-12 < minimum_positive_improvement_rate:
        gate_blockers.append("positive_improvement_rate_below_threshold")
    if any(float(row["correct_action_score_margin"]) <= 0.0 for row in rows):
        gate_blockers.append("correct_action_not_strictly_preferred")
    policy_ready = not gate_blockers
    receipt = {
        "evaluation_type": "screen_lab_policy_evaluation_v1",
        "status": "policy_ready" if policy_ready else "policy_blocked",
        "environment_domain": environment_domain,
        "split": split,
        "sample_count": sample_count,
        "action_candidate_count": len(action_candidates),
        "metrics": {
            "top1_action_accuracy": round(top1_accuracy, 8),
            "top2_action_accuracy": round(top2_accuracy, 8),
            "mean_reciprocal_rank": round(mean_reciprocal_rank, 8),
            "positive_improvement_rate": round(positive_improvement_rate, 8),
            "mean_correct_action_score_margin": round(mean_correct_action_margin, 8),
        },
        "thresholds": {
            "minimum_samples": minimum_samples,
            "minimum_top1_accuracy": minimum_top1_accuracy,
            "minimum_positive_improvement_rate": minimum_positive_improvement_rate,
            "strict_positive_correct_action_margin_required": True,
        },
        "rows": rows,
        "policy_ready": policy_ready,
        "planner_advice_allowed": policy_ready,
        "execution_allowed": False,
        "execution_performed": False,
        "model_call_performed": True,
        "network_call_performed": False,
        "raw_image_persisted": False,
        "latent_vector_persisted": False,
        "blockers": sorted(set(gate_blockers)),
        "next_action": (
            "create_domain_specific_planner_packet"
            if policy_ready
            else "collect_more_sequences_or_retrain_policy_model"
        ),
    }
    receipt["evaluation_hash"] = _stable_hash(receipt)
    return receipt


def write_policy_evaluation(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(payload, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def _validate_thresholds(
    *,
    split: str,
    minimum_samples: int,
    minimum_top1_accuracy: float,
    minimum_positive_improvement_rate: float,
) -> list[str]:
    blockers: list[str] = []
    if split not in {"train", "validation", "test"}:
        blockers.append("split_invalid")
    if minimum_samples < 1:
        blockers.append("minimum_samples_invalid")
    for name, value in (
        ("minimum_top1_accuracy", minimum_top1_accuracy),
        ("minimum_positive_improvement_rate", minimum_positive_improvement_rate),
    ):
        if not 0.0 <= value <= 1.0:
            blockers.append(f"{name}_invalid")
    return blockers


def _resolve_output_ref(output_root: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    candidate = (output_root / value).resolve()
    if not candidate.is_relative_to(output_root) or not candidate.is_file():
        return None
    return candidate


def _blocked_evaluation(
    blockers: list[str],
    *,
    sample_count: int = 0,
    rows: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    payload = {
        "evaluation_type": "screen_lab_policy_evaluation_v1",
        "status": "blocked",
        "sample_count": sample_count,
        "rows": rows or [],
        "policy_ready": False,
        "planner_advice_allowed": False,
        "execution_allowed": False,
        "execution_performed": False,
        "model_call_performed": False,
        "blockers": sorted(set(blockers)),
        "next_action": "repair_policy_evaluation_inputs",
    }
    payload["evaluation_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
