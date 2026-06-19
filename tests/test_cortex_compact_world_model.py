import hashlib
import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_compact_world_model import build_compact_predictor_plan
from hex_cortex.memory.cortex_compact_world_model import promote_compact_predictor
from hex_cortex.memory.cortex_compact_world_model import train_compact_predictor
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import build_transition_dataset_manifest
from hex_cortex.memory.cortex_observed_transition_dataset import capture_observed_transition


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _runner(image_path, model_ref, pooling, device, local_files_only):
    mapping = {
        "current-a.png": [1.0, 0.0, 0.0, 0.0],
        "next-a.png": [0.9, 0.1, 0.0, 0.0],
        "current-b.png": [0.0, 1.0, 0.0, 0.0],
        "next-b.png": [0.1, 0.9, 0.0, 0.0],
        "current-c.png": [0.0, 0.0, 1.0, 0.0],
        "next-c.png": [0.0, 0.1, 0.9, 0.0],
        "current-d.png": [0.0, 0.0, 0.0, 1.0],
        "next-d.png": [0.0, 0.0, 0.1, 0.9],
    }
    return mapping[image_path.name], {
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
        "hidden_size": 4,
        "patch_size": 14,
    }


def _manifest(tmp_path: Path):
    comfy_root = tmp_path / "ComfyUI"
    output = comfy_root / "output"
    output.mkdir(parents=True)
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    records = []
    specs = [
        ("a", "train", [0.1, 0.0]),
        ("b", "train", [0.0, 0.1]),
        ("c", "validation", [-0.1, 0.0]),
        ("d", "test", [0.0, -0.1]),
    ]
    for name, split, action in specs:
        current = output / f"current-{name}.png"
        next_image = output / f"next-{name}.png"
        current.write_bytes(f"current-{name}".encode())
        next_image.write_bytes(f"next-{name}".encode())
        records.append(
            capture_observed_transition(
                comfy_root=comfy_root,
                current_image_path=current,
                next_image_path=next_image,
                action=action,
                action_schema=["x", "y"],
                split=split,
                encoder_descriptor=descriptor,
                encoder_runner=_runner,
            )
        )
    manifest = build_transition_dataset_manifest(
        records,
        min_train=2,
        min_validation=1,
        min_test=1,
    )
    return comfy_root, descriptor, manifest


def test_training_plan_requires_ready_dataset() -> None:
    plan = build_compact_predictor_plan(
        manifest={"manifest_allowed": True, "training_ready": False},
    )

    assert plan["plan_allowed"] is False
    assert "dataset_not_training_ready" in plan["blockers"]


def test_training_plan_is_bounded(tmp_path: Path) -> None:
    _, _, manifest = _manifest(tmp_path)

    plan = build_compact_predictor_plan(
        manifest=manifest,
        hidden_dim=16,
        epochs=3,
        batch_size=2,
        max_seconds=30,
    )

    assert plan["plan_allowed"] is True
    assert plan["config"]["architecture"] == "residual_mlp_v1"
    assert plan["training_performed"] is False


def test_training_requires_explicit_approval(tmp_path: Path) -> None:
    comfy_root, descriptor, manifest = _manifest(tmp_path)
    plan = build_compact_predictor_plan(
        manifest=manifest,
        hidden_dim=16,
        epochs=2,
        batch_size=2,
        max_seconds=30,
    )

    receipt = train_compact_predictor(
        plan=plan,
        manifest=manifest,
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        output_dir=tmp_path / "candidate",
        operator_approved=False,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "blocked"
    assert receipt["training_performed"] is False


def test_tiny_training_writes_safetensors_candidate(tmp_path: Path) -> None:
    pytest.importorskip("torch")
    pytest.importorskip("safetensors")
    comfy_root, descriptor, manifest = _manifest(tmp_path)
    plan = build_compact_predictor_plan(
        manifest=manifest,
        hidden_dim=8,
        epochs=2,
        batch_size=2,
        max_seconds=30,
        device="cpu",
    )
    output_dir = tmp_path / "candidate"

    receipt = train_compact_predictor(
        plan=plan,
        manifest=manifest,
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        output_dir=output_dir,
        operator_approved=True,
        encoder_runner=_runner,
    )

    assert receipt["status"] == "trained"
    assert receipt["training_performed"] is True
    assert receipt["checkpoint_written"] is True
    assert (output_dir / "predictor.safetensors").is_file()
    candidate = json.loads((output_dir / "candidate.json").read_text(encoding="utf-8"))
    assert candidate["architecture"] == "residual_mlp_v1"
    assert candidate["latent_vector_persisted"] is False


def test_promotion_copies_verified_candidate(tmp_path: Path) -> None:
    candidate_dir = tmp_path / "candidate"
    candidate_dir.mkdir()
    weights = candidate_dir / "predictor.safetensors"
    weights.write_bytes(b"weights")
    candidate = {
        "candidate_type": "compact_world_model_candidate_v1",
        "candidate_hash": "c" * 64,
        "promotion_allowed": True,
        "weights_file": weights.name,
        "weights_hash": _hash(weights),
        "dataset_domain": "controlled_visual_transform_v1",
        "encoder_descriptor_hash": "e" * 64,
    }
    candidate_path = candidate_dir / "candidate.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    receipt = promote_compact_predictor(
        candidate_manifest_path=candidate_path,
        registry_dir=tmp_path / "registry",
        operator_approved=True,
    )

    assert receipt["status"] == "promoted"
    assert receipt["promotion_performed"] is True
    assert (tmp_path / "registry" / "active.json").is_file()
    assert (tmp_path / "registry" / "active_predictor.safetensors").is_file()
