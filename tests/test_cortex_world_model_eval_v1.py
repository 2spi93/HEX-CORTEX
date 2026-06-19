import hashlib

from hex_cortex.memory.cortex_latent_lab import build_latent_lab_spec
from hex_cortex.memory.cortex_world_model_eval import build_world_model_dataset_manifest
from hex_cortex.memory.cortex_world_model_eval import build_world_model_run_plan
from hex_cortex.memory.cortex_world_model_eval import evaluate_world_model_candidate


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _samples() -> list[dict[str, object]]:
    return [
        {
            "sample_id": "train-1",
            "split": "train",
            "state_hash": _digest("s1"),
            "action_hash": _digest("a1"),
            "next_state_hash": _digest("n1"),
        },
        {
            "sample_id": "validation-1",
            "split": "validation",
            "state_hash": _digest("s2"),
            "action_hash": _digest("a2"),
            "next_state_hash": _digest("n2"),
        },
        {
            "sample_id": "test-1",
            "split": "test",
            "state_hash": _digest("s3"),
            "action_hash": _digest("a3"),
            "next_state_hash": _digest("n3"),
        },
    ]


def test_dataset_manifest_requires_all_splits_and_hashes() -> None:
    manifest = build_world_model_dataset_manifest(_samples())
    assert manifest["manifest_allowed"] is True
    assert manifest["sample_count"] == 3
    assert manifest["split_counts"] == {"train": 1, "validation": 1, "test": 1}
    assert manifest["observation_storage"] == "external_hash_references_only"
    assert len(manifest["manifest_hash"]) == 64


def test_dataset_manifest_rejects_invalid_rows() -> None:
    manifest = build_world_model_dataset_manifest(
        [
            {
                "sample_id": "bad",
                "split": "train",
                "state_hash": "not-a-hash",
                "action_hash": _digest("a"),
                "next_state_hash": _digest("n"),
            }
        ]
    )
    assert manifest["manifest_allowed"] is False
    assert "sample_hash_invalid" in manifest["blockers"]


def test_run_plan_is_bounded_and_does_not_execute() -> None:
    manifest = build_world_model_dataset_manifest(_samples())
    spec = build_latent_lab_spec(latent_dim=8, action_dim=4)
    plan = build_world_model_run_plan(
        manifest=manifest,
        lab_spec=spec,
        seed=7,
        epochs=20,
        batch_size=16,
        max_gpu_hours=2.0,
    )
    assert plan["plan_allowed"] is True
    assert plan["run_performed"] is False
    assert plan["checkpoint_written"] is False
    assert plan["config"]["max_gpu_hours"] == 2.0
    assert len(plan["plan_hash"]) == 64


def test_candidate_review_can_pass_without_regression() -> None:
    result = evaluate_world_model_candidate(
        baseline={
            "prediction_error": 0.20,
            "surprise_calibration": 0.70,
            "planning_success": 0.60,
        },
        candidate={
            "prediction_error": 0.15,
            "surprise_calibration": 0.75,
            "planning_success": 0.66,
        },
    )
    assert result["evaluation_allowed"] is True
    assert result["promotion_allowed"] is True
    assert result["regression_metrics"] == []
    assert result["next_action"] == "prepare_candidate_review"


def test_candidate_review_retains_baseline_on_regression() -> None:
    result = evaluate_world_model_candidate(
        baseline={
            "prediction_error": 0.20,
            "surprise_calibration": 0.70,
            "planning_success": 0.60,
        },
        candidate={
            "prediction_error": 0.15,
            "surprise_calibration": 0.75,
            "planning_success": 0.40,
        },
    )
    assert result["promotion_allowed"] is False
    assert "planning_success" in result["regression_metrics"]
    assert result["next_action"] == "retain_baseline"
