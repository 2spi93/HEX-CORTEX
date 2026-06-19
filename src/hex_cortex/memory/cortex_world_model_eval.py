from __future__ import annotations

import hashlib
import json


def build_world_model_dataset_manifest(
    samples: list[dict[str, object]],
) -> dict[str, object]:
    blockers: list[str] = []
    accepted: list[dict[str, object]] = []
    seen: set[str] = set()
    for sample in samples:
        sample_id = sample.get("sample_id")
        split = sample.get("split")
        state_hash = sample.get("state_hash")
        action_hash = sample.get("action_hash")
        next_state_hash = sample.get("next_state_hash")
        if not isinstance(sample_id, str) or not sample_id:
            blockers.append("sample_id_missing")
            continue
        if sample_id in seen:
            blockers.append("duplicate_sample_id")
            continue
        if split not in {"train", "validation", "test"}:
            blockers.append("sample_split_invalid")
            continue
        if not all(_is_sha256(value) for value in (state_hash, action_hash, next_state_hash)):
            blockers.append("sample_hash_invalid")
            continue
        seen.add(sample_id)
        accepted.append(
            {
                "sample_id": sample_id,
                "split": split,
                "state_hash": state_hash,
                "action_hash": action_hash,
                "next_state_hash": next_state_hash,
            }
        )
    split_counts = {
        split: sum(row["split"] == split for row in accepted)
        for split in ("train", "validation", "test")
    }
    if accepted and any(count == 0 for count in split_counts.values()):
        blockers.append("all_dataset_splits_required")
    blockers = sorted(set(blockers))
    allowed = bool(accepted) and not blockers
    return {
        "manifest_type": "world_model_dataset_v1",
        "manifest_allowed": allowed,
        "sample_count": len(accepted),
        "split_counts": split_counts,
        "samples": accepted,
        "observation_storage": "external_hash_references_only",
        "manifest_hash": _stable_hash(accepted),
        "blockers": blockers,
        "next_action": "prepare_world_model_run" if allowed else "repair_dataset_manifest",
    }


def build_world_model_run_plan(
    *,
    manifest: dict[str, object],
    lab_spec: dict[str, object],
    seed: int = 42,
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 0.0003,
    max_gpu_hours: float = 8.0,
) -> dict[str, object]:
    blockers: list[str] = []
    if manifest.get("manifest_allowed") is not True:
        blockers.append("dataset_manifest_not_allowed")
    if lab_spec.get("spec_allowed") is not True:
        blockers.append("latent_lab_spec_not_allowed")
    if not 0 <= seed <= 2**31 - 1:
        blockers.append("seed_out_of_range")
    if not 1 <= epochs <= 10_000:
        blockers.append("epochs_out_of_range")
    if not 1 <= batch_size <= 65_536:
        blockers.append("batch_size_out_of_range")
    if not 0.0 < learning_rate <= 1.0:
        blockers.append("learning_rate_out_of_range")
    if not 0.1 <= max_gpu_hours <= 10_000:
        blockers.append("gpu_budget_out_of_range")
    config = {
        "seed": seed,
        "epochs": epochs,
        "batch_size": batch_size,
        "learning_rate": learning_rate,
        "max_gpu_hours": max_gpu_hours,
        "latent_dim": lab_spec.get("latent_dim"),
        "action_dim": lab_spec.get("action_dim"),
        "horizons": lab_spec.get("horizons"),
        "encoder_policy": lab_spec.get("encoder_policy"),
        "predictor_kind": lab_spec.get("predictor_kind"),
    }
    stable = {
        "manifest_hash": manifest.get("manifest_hash"),
        "spec_hash": lab_spec.get("spec_hash"),
        "config": config,
        "blockers": blockers,
    }
    allowed = not blockers
    return {
        "plan_type": "world_model_run_plan_v1",
        "plan_allowed": allowed,
        "manifest_hash": manifest.get("manifest_hash"),
        "spec_hash": lab_spec.get("spec_hash"),
        "config": config,
        "run_performed": False,
        "checkpoint_written": False,
        "network_call_performed": False,
        "plan_hash": _stable_hash(stable),
        "blockers": blockers,
        "next_action": "run_in_bounded_environment" if allowed else "repair_world_model_run_plan",
    }


def evaluate_world_model_candidate(
    *,
    baseline: dict[str, float],
    candidate: dict[str, float],
    required_metrics: list[str] | None = None,
    max_regression_fraction: float = 0.02,
    minimum_improvement_fraction: float = 0.01,
) -> dict[str, object]:
    required = list(required_metrics or ["prediction_error", "surprise_calibration", "planning_success"])
    blockers: list[str] = []
    if not required:
        blockers.append("required_metrics_empty")
    if not 0.0 <= max_regression_fraction <= 1.0:
        blockers.append("max_regression_fraction_out_of_range")
    if not 0.0 <= minimum_improvement_fraction <= 1.0:
        blockers.append("minimum_improvement_fraction_out_of_range")
    for metric in required:
        if metric not in baseline or metric not in candidate:
            blockers.append(f"missing_metric:{metric}")
        elif not isinstance(baseline[metric], int | float) or not isinstance(candidate[metric], int | float):
            blockers.append(f"metric_not_numeric:{metric}")
    if blockers:
        return {
            "evaluation_type": "world_model_candidate_evaluation_v1",
            "evaluation_allowed": False,
            "promotion_allowed": False,
            "blockers": blockers,
            "next_action": "repair_world_model_metrics",
        }
    deltas: dict[str, float] = {}
    regressions: list[str] = []
    improvements: list[str] = []
    for metric in required:
        base = float(baseline[metric])
        value = float(candidate[metric])
        higher_is_better = metric in {"surprise_calibration", "planning_success"}
        denominator = max(abs(base), 1e-9)
        gain = (value - base) / denominator if higher_is_better else (base - value) / denominator
        deltas[metric] = round(gain, 8)
        if gain < -max_regression_fraction:
            regressions.append(metric)
        if gain >= minimum_improvement_fraction:
            improvements.append(metric)
    promotion_allowed = not regressions and bool(improvements)
    stable = {
        "required_metrics": required,
        "deltas": deltas,
        "regressions": regressions,
        "improvements": improvements,
        "promotion_allowed": promotion_allowed,
    }
    return {
        "evaluation_type": "world_model_candidate_evaluation_v1",
        "evaluation_allowed": True,
        "promotion_allowed": promotion_allowed,
        "metric_deltas": deltas,
        "regression_metrics": regressions,
        "improvement_metrics": improvements,
        "baseline_hash": _stable_hash(baseline),
        "candidate_hash": _stable_hash(candidate),
        "evaluation_hash": _stable_hash(stable),
        "blockers": [] if promotion_allowed else ["candidate_not_promotable"],
        "next_action": "prepare_candidate_review" if promotion_allowed else "retain_baseline",
    }


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value.lower())
    )


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
