from __future__ import annotations

import hashlib
import json


def build_world_model_dataset_manifest(
    samples: list[dict[str, object]],
) -> dict[str, object]:
    blockers = []
    accepted = []
    seen: set[str] = set()
    for sample in samples:
        sample_id = sample.get("sample_id")
        split = sample.get("split")
        hashes = (
            sample.get("state_hash"),
            sample.get("action_hash"),
            sample.get("next_state_hash"),
        )
        if not isinstance(sample_id, str) or not sample_id:
            blockers.append("sample_id_missing")
            continue
        if sample_id in seen:
            blockers.append("duplicate_sample_id")
            continue
        if split not in {"train", "validation", "test"}:
            blockers.append("sample_split_invalid")
            continue
        if not all(_is_sha256(value) for value in hashes):
            blockers.append("sample_hash_invalid")
            continue
        seen.add(sample_id)
        accepted.append(
            {
                "sample_id": sample_id,
                "split": split,
                "state_hash": hashes[0],
                "action_hash": hashes[1],
                "next_state_hash": hashes[2],
            }
        )
    split_counts = {
        name: sum(row["split"] == name for row in accepted)
        for name in ("train", "validation", "test")
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
        "next_action": "prepare_world_model_training" if allowed else "repair_dataset_manifest",
    }


def build_world_model_training_plan(
    *,
    manifest: dict[str, object],
    lab_spec: dict[str, object],
    seed: int = 42,
    epochs: int = 10,
    batch_size: int = 32,
    learning_rate: float = 0.0003,
    max_gpu_hours: float = 8.0,
) -> dict[str, object]:
    blockers = []
    if manifest.get("manifest_allowed") is not True:
        blockers.append("dataset_manifest_not_allowed")
    if lab_spec.get("spec_allowed") is not True:
        blockers.append("latent_lab_spec_not_allowed")
    if seed < 0 or seed > 2**31 - 1:
        blockers.append("seed_out_of_range")
    if not 1 <= epochs <= 10_000:
        blockers.append("epochs_out_of_range")
    if not 1 <= batch_size <= 65_536:
        blockers.append("batch_size_out_of_range")
    if not 0.0 < learning_rate <= 1.0:
        blockers.append("learning_rate_out_of_range")
    if not 0.1 <= max_gpu_hours <= 10_000:
        blockers.append("gpu_budget_out_of_range")
    allowed = not blockers
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
    return {
        "plan_type": "world_model_training_plan_v1",
        "plan_allowed": allowed,
        "manifest_hash": manifest.get("manifest_hash"),
        "spec_hash": lab_spec.get("spec_hash"),
        "framework_stack": ["pytorch", "hydra", "accelerate", "mlflow"],
        "configuration": config,
        "checkpoint_policy": "best_validation_plus_last",
        "mixed_precision_policy": "hardware_selected",
        "distributed_policy": "disabled_until_explicitly_configured",
        "training_performed": False,
        "process_started": False,
        "network_call_performed": False,
        "plan_hash": _stable_hash(stable),
        "blockers": blockers,
        "next_action": "execute_training_in_isolated_runner" if allowed else "repair_training_plan",
    }


def build_default_training_blueprint() -> dict[str, object]:
    return {
        "blueprint_type": "world_model_training_evaluation_v1",
        "data_contract": {
            "required_splits": ["train", "validation", "test"],
            "sample_fields": ["state_hash", "action_hash", "next_state_hash"],
            "raw_observation_storage": "external_only",
        },
        "model_contract": {
            "encoder": "frozen_first",
            "predictor": "action_conditioned_compact",
            "uncertainty_head": True,
            "horizons": [1, 4, 16, 64],
        },
        "evaluation_contract": {
            "representation": ["state_separation", "temporal_consistency"],
            "prediction": ["latent_rmse", "rollout_divergence"],
            "surprise": ["surprise_auroc", "ood_detection"],
            "planning": ["goal_success_rate", "replanning_success_rate"],
            "system": ["latency_ms", "peak_vram_gb", "reproducibility"],
        },
        "promotion_policy": "baseline_comparison_and_zero_critical_regressions",
        "next_action": "build_dataset_manifest",
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
