import json
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import append_transition_jsonl
from hex_cortex.memory.cortex_observed_transition_dataset import build_transition_dataset_manifest
from hex_cortex.memory.cortex_observed_transition_dataset import capture_observed_transition
from hex_cortex.memory.cortex_observed_transition_dataset import load_transition_records


def _runner(image_path, model_ref, pooling, device, local_files_only):
    if image_path.name.startswith("next"):
        vector = [0.0, 1.0, 0.0, 0.0]
    else:
        vector = [1.0, 0.0, 0.0, 0.0]
    return vector, {
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
        "hidden_size": 4,
        "patch_size": 14,
    }


def _images(tmp_path: Path) -> tuple[Path, Path, Path]:
    comfy_root = tmp_path / "ComfyUI"
    output = comfy_root / "output"
    output.mkdir(parents=True)
    current = output / "current.png"
    next_image = output / "next.png"
    current.write_bytes(b"current")
    next_image.write_bytes(b"next")
    return comfy_root, current, next_image


def test_capture_observed_transition_is_hash_only(tmp_path: Path) -> None:
    comfy_root, current, next_image = _images(tmp_path)
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    record = capture_observed_transition(
        comfy_root=comfy_root,
        current_image_path=current,
        next_image_path=next_image,
        action=[0.1, 0.0, -0.2, 0.0],
        split="train",
        encoder_descriptor=descriptor,
        encoder_runner=_runner,
    )

    assert record["record_type"] == "observed_transition_v1"
    assert record["split"] == "train"
    assert record["encoder"]["latent_dim"] == 4
    assert record["action_values"] == [0.1, 0.0, -0.2, 0.0]
    assert record["raw_image_persisted"] is False
    assert record["latent_vector_persisted"] is False
    assert record["evaluation"]["surprising"] is True
    assert "volatile_embedding" not in json.dumps(record)


def test_capture_rejects_image_outside_comfy_output(tmp_path: Path) -> None:
    comfy_root, current, _ = _images(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    record = capture_observed_transition(
        comfy_root=comfy_root,
        current_image_path=current,
        next_image_path=outside,
        action=[0.0, 0.0, 0.0, 0.0],
        encoder_descriptor=descriptor,
        encoder_runner=_runner,
    )

    assert record["status"] == "blocked"
    assert "image_outside_comfyui_output" in record["blockers"]


def test_append_is_idempotent(tmp_path: Path) -> None:
    comfy_root, current, next_image = _images(tmp_path)
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    record = capture_observed_transition(
        comfy_root=comfy_root,
        current_image_path=current,
        next_image_path=next_image,
        action=[0.0, 0.0, 0.0, 0.0],
        split="train",
        encoder_descriptor=descriptor,
        encoder_runner=_runner,
    )
    target = tmp_path / "dataset.jsonl"

    first = append_transition_jsonl(target, record)
    second = append_transition_jsonl(target, record)

    assert first["appended"] is True
    assert second["duplicate"] is True
    assert len(load_transition_records(target)) == 1


def test_manifest_reports_training_readiness(tmp_path: Path) -> None:
    comfy_root, current, _ = _images(tmp_path)
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    records = []
    splits = ["train", "train", "validation", "test"]
    for index, split in enumerate(splits):
        image = comfy_root / "output" / f"next-{index}.png"
        image.write_bytes(f"next-{index}".encode())
        record = capture_observed_transition(
            comfy_root=comfy_root,
            current_image_path=current,
            next_image_path=image,
            action=[index / 10, 0.0, 0.0, 0.0],
            split=split,
            encoder_descriptor=descriptor,
            encoder_runner=_runner,
        )
        records.append(record)

    manifest = build_transition_dataset_manifest(
        records,
        min_train=2,
        min_validation=1,
        min_test=1,
    )

    assert manifest["manifest_allowed"] is True
    assert manifest["smoke_ready"] is True
    assert manifest["training_ready"] is True
    assert manifest["promotion_ready"] is True
    assert manifest["split_counts"] == {"train": 2, "validation": 1, "test": 1}


def test_manifest_blocks_mixed_encoder_descriptors(tmp_path: Path) -> None:
    comfy_root, current, next_image = _images(tmp_path)
    first_descriptor = build_frozen_encoder_descriptor(device="cpu")
    second_descriptor = build_frozen_encoder_descriptor(model_ref="other/model", device="cpu")
    first = capture_observed_transition(
        comfy_root=comfy_root,
        current_image_path=current,
        next_image_path=next_image,
        action=[0.0, 0.0, 0.0, 0.0],
        split="train",
        encoder_descriptor=first_descriptor,
        encoder_runner=_runner,
    )
    other = comfy_root / "output" / "next-other.png"
    other.write_bytes(b"other")
    second = capture_observed_transition(
        comfy_root=comfy_root,
        current_image_path=current,
        next_image_path=other,
        action=[0.1, 0.0, 0.0, 0.0],
        split="validation",
        encoder_descriptor=second_descriptor,
        encoder_runner=_runner,
    )

    manifest = build_transition_dataset_manifest([first, second])

    assert manifest["manifest_allowed"] is False
    assert "mixed_encoder_descriptors" in manifest["blockers"]
