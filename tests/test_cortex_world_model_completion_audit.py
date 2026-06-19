import json
from pathlib import Path

from hex_cortex.memory.cortex_world_model_completion_audit import audit_world_model_completion


def _code_contracts(root: Path) -> None:
    memory_root = root / "src" / "hex_cortex" / "memory"
    memory_root.mkdir(parents=True)
    for name in (
        "cortex_media_runtime.py",
        "cortex_comfyui_operational.py",
        "cortex_frozen_encoder.py",
        "cortex_media_to_latent_pipeline.py",
        "cortex_observed_transition_dataset.py",
        "cortex_compact_world_model.py",
        "cortex_world_training_cli.py",
    ):
        (memory_root / name).touch()


def test_audit_reports_dataset_as_next_missing_stage(tmp_path: Path) -> None:
    _code_contracts(tmp_path)

    payload = audit_world_model_completion(tmp_path)

    assert payload["architecture_ready"] is True
    assert payload["learning_complete"] is False
    assert payload["next_action"] == "capture_observed_transitions"


def test_audit_reports_active_predictor_ready(tmp_path: Path) -> None:
    _code_contracts(tmp_path)
    state = tmp_path / ".hex-cortex" / "world-model"
    candidate = state / "candidate"
    registry = state / "registry"
    candidate.mkdir(parents=True)
    registry.mkdir(parents=True)
    (state / "transitions.jsonl").write_text("{}\n", encoding="utf-8")
    (state / "manifest.json").write_text(
        json.dumps({"manifest_allowed": True, "training_ready": True}),
        encoding="utf-8",
    )
    (candidate / "candidate.json").write_text(
        json.dumps({"status": "trained", "promotion_allowed": True}),
        encoding="utf-8",
    )
    (registry / "active.json").write_text(
        json.dumps({"registry_type": "active_compact_world_model_v1"}),
        encoding="utf-8",
    )

    payload = audit_world_model_completion(tmp_path)

    assert payload["learning_complete"] is True
    assert payload["active_predictor_ready"] is True
    assert payload["next_action"] == "run_active_predictor_and_collect_real_transitions"
