from __future__ import annotations

import json
from pathlib import Path


def audit_world_model_completion(
    project_root: Path,
    *,
    state_root: Path | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    memory_root = root / "src" / "hex_cortex" / "memory"
    state = (state_root or (root / ".hex-cortex")).resolve()
    code_paths = {
        "media_runtime": memory_root / "cortex_media_runtime.py",
        "comfyui_operational": memory_root / "cortex_comfyui_operational.py",
        "frozen_encoder": memory_root / "cortex_frozen_encoder.py",
        "media_to_latent": memory_root / "cortex_media_to_latent_pipeline.py",
        "observed_transition_dataset": memory_root / "cortex_observed_transition_dataset.py",
        "compact_world_model": memory_root / "cortex_compact_world_model.py",
        "world_training_cli": memory_root / "cortex_world_training_cli.py",
    }
    code_facts = {name: path.is_file() for name, path in code_paths.items()}
    dataset_path = state / "world-model" / "transitions.jsonl"
    manifest_path = state / "world-model" / "manifest.json"
    candidate_path = state / "world-model" / "candidate" / "candidate.json"
    active_path = state / "world-model" / "registry" / "active.json"
    manifest = _read_json(manifest_path)
    candidate = _read_json(candidate_path)
    active = _read_json(active_path)
    dataset_exists = dataset_path.is_file() and dataset_path.stat().st_size > 0
    manifest_allowed = bool(manifest and manifest.get("manifest_allowed") is True)
    training_ready = bool(manifest and manifest.get("training_ready") is True)
    candidate_trained = bool(candidate and candidate.get("status") == "trained")
    candidate_promotable = bool(candidate and candidate.get("promotion_allowed") is True)
    active_ready = bool(active and active.get("registry_type") == "active_compact_world_model_v1")
    architecture_ready = all(code_facts.values())
    if not architecture_ready:
        next_action = "repair_world_model_code_contracts"
    elif not dataset_exists:
        next_action = "capture_observed_transitions"
    elif not manifest_allowed:
        next_action = "build_transition_manifest"
    elif not training_ready:
        next_action = "collect_more_observed_transitions"
    elif not candidate_trained:
        next_action = "train_compact_predictor"
    elif not candidate_promotable:
        next_action = "improve_candidate_or_dataset"
    elif not active_ready:
        next_action = "promote_compact_predictor"
    else:
        next_action = "run_active_predictor_and_collect_real_transitions"
    return {
        "audit_type": "world_model_completion_audit_v1",
        "project_root": str(root),
        "state_root": str(state),
        "architecture_ready": architecture_ready,
        "dataset_exists": dataset_exists,
        "manifest_allowed": manifest_allowed,
        "training_ready": training_ready,
        "candidate_trained": candidate_trained,
        "candidate_promotable": candidate_promotable,
        "active_predictor_ready": active_ready,
        "engineering_complete": architecture_ready,
        "learning_complete": active_ready,
        "code_facts": code_facts,
        "artifact_paths": {
            "dataset": str(dataset_path),
            "manifest": str(manifest_path),
            "candidate": str(candidate_path),
            "active_registry": str(active_path),
        },
        "network_probe_performed": False,
        "model_call_performed": False,
        "next_action": next_action,
    }


def _read_json(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None
