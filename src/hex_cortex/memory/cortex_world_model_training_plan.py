from __future__ import annotations

import hashlib
import json


def build_world_model_training_plan() -> dict[str, object]:
    return {
        "plan_type": "world_model_training_evaluation_v1",
        "stack": ["pytorch", "hydra", "accelerate", "mlflow"],
        "dataset_contract": "versioned_latent_transition_samples",
        "objectives": [
            "multi_step_latent_prediction",
            "uncertainty_calibration",
            "representation_anti_collapse",
            "action_conditioned_transition",
        ],
        "evaluation_groups": [
            "representation",
            "prediction",
            "surprise_and_ood",
            "planning",
            "generalization",
            "system_performance",
        ],
        "manual_approval_required": True,
        "automatic_deployment_allowed": False,
        "rollback_checkpoint_required": True,
        "next_action": "materialize_dataset_manifest",
    }


def build_world_model_dataset_manifest(
    *,
    dataset_id: str,
    dataset_version: str,
    sample_hashes: list[str],
    train_count: int,
    validation_count: int,
    test_count: int,
    encoder_id: str,
    encoder_version: str,
) -> dict[str, object]:
    if not dataset_id.strip() or not dataset_version.strip():
        raise ValueError("dataset identifiers must be non-empty")
    if not encoder_id.strip() or not encoder_version.strip():
        raise ValueError("encoder identifiers must be non-empty")
    if min(train_count, validation_count, test_count) < 1:
        raise ValueError("all dataset splits must be non-empty")
    if train_count + validation_count + test_count != len(sample_hashes):
        raise ValueError("split counts must equal sample hash count")
    if len(set(sample_hashes)) != len(sample_hashes):
        raise ValueError("sample hashes must be unique")
    if not all(_is_sha256(value) for value in sample_hashes):
        raise ValueError("sample hashes must be sha256 hex digests")
    stable = {
        "dataset_id": dataset_id,
        "dataset_version": dataset_version,
        "sample_hashes": sorted(sample_hashes),
        "train_count": train_count,
        "validation_count": validation_count,
        "test_count": test_count,
        "encoder_id": encoder_id,
        "encoder_version": encoder_version,
    }
    return {
        "manifest_type": "world_model_dataset_manifest",
        **stable,
        "sample_count": len(sample_hashes),
        "raw_sensor_data_persisted": False,
        "raw_latents_persisted": False,
        "manifest_hash": _hash(stable),
    }


def build_training_run_receipt(
    *,
    dataset_manifest: dict[str, object],
    run_id: str,
    config: dict[str, object],
    seed: int,
    checkpoint_hash: str,
    metrics: dict[str, float],
) -> dict[str, object]:
    if not run_id.strip() or seed < 0:
        raise ValueError("run identifier and seed are invalid")
    if not _is_sha256(str(dataset_manifest.get("manifest_hash", ""))):
        raise ValueError("dataset manifest hash missing")
    if not _is_sha256(checkpoint_hash):
        raise ValueError("checkpoint hash must be sha256")
    if not metrics or not all(
        isinstance(key, str) and isinstance(value, int | float)
        for key, value in metrics.items()
    ):
        raise ValueError("metrics must be numeric")
    stable = {
        "dataset_manifest_hash": dataset_manifest["manifest_hash"],
        "run_id": run_id,
        "config_hash": _hash(config),
        "seed": seed,
        "checkpoint_hash": checkpoint_hash,
        "metrics": metrics,
    }
    return {
        "receipt_type": "world_model_training_run",
        **stable,
        "raw_config_persisted": False,
        "raw_dataset_persisted": False,
        "checkpoint_bytes_persisted": False,
        "receipt_hash": _hash(stable),
        "next_action": "compare_candidate_to_baseline",
    }


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value.lower())


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
