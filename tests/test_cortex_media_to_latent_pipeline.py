import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_media_to_latent_pipeline import append_receipt_jsonl
from hex_cortex.memory.cortex_media_to_latent_pipeline import build_baseline_action_weights
from hex_cortex.memory.cortex_media_to_latent_pipeline import build_existing_output_receipt
from hex_cortex.memory.cortex_media_to_latent_pipeline import resolve_comfyui_output_asset
from hex_cortex.memory.cortex_media_to_latent_pipeline import run_media_to_latent_pipeline


def _make_output(tmp_path: Path, name: str = "image.png") -> tuple[Path, Path]:
    comfy_root = tmp_path / "ComfyUI"
    output = comfy_root / "output"
    output.mkdir(parents=True)
    image = output / name
    image.write_bytes(b"png-bytes")
    return comfy_root, image


def _runner(image_path, model_ref, pooling, device, local_files_only):
    if image_path.name == "observed.png":
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


def test_existing_output_receipt_keeps_relative_manifest(tmp_path: Path) -> None:
    comfy_root, image = _make_output(tmp_path)

    receipt = build_existing_output_receipt(
        comfy_root=comfy_root,
        image_path=image,
        source_receipt_hash="abc123",
    )

    assert receipt["status"] == "observed"
    assert receipt["output_manifest"][0]["filename"] == "image.png"
    assert receipt["source_receipt_hash"] == "abc123"
    assert receipt["generation_performed"] is False


def test_existing_output_outside_comfy_root_is_blocked(tmp_path: Path) -> None:
    comfy_root, _ = _make_output(tmp_path)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside")

    receipt = build_existing_output_receipt(
        comfy_root=comfy_root,
        image_path=outside,
    )

    assert receipt["status"] == "blocked"
    assert "image_outside_comfyui_output" in receipt["blockers"]


def test_asset_resolution_blocks_path_escape(tmp_path: Path) -> None:
    comfy_root, _ = _make_output(tmp_path)

    path, receipt = resolve_comfyui_output_asset(
        comfy_root=comfy_root,
        asset={
            "asset_kind": "images",
            "filename": "secret.png",
            "subfolder": "../private",
            "folder_type": "output",
        },
    )

    assert path is None
    assert receipt["asset_resolved"] is False
    assert "asset_subfolder_unsafe" in receipt["blockers"]
    assert receipt["absolute_path_persisted"] is False


def test_baseline_weights_are_deterministic() -> None:
    first = build_baseline_action_weights(4, 2, scale=0.1)
    second = build_baseline_action_weights(4, 2, scale=0.1)

    assert first == second
    assert first == [[0.1, 0.0], [0.0, 0.1], [-0.1, 0.0], [0.0, -0.1]]


def test_pipeline_encodes_and_predicts_without_persisting_latent(tmp_path: Path) -> None:
    comfy_root, image = _make_output(tmp_path)
    source = build_existing_output_receipt(comfy_root=comfy_root, image_path=image)
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = run_media_to_latent_pipeline(
        source_receipt=source,
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        action=[0.0, 0.0],
        encoder_runner=_runner,
    )

    assert receipt["pipeline_completed"] is True
    assert receipt["status"] == "completed"
    assert receipt["latent_dim"] == 4
    assert receipt["predictor_trained"] is False
    assert receipt["network_call_performed"] is False
    assert receipt["embedding_vector_persisted"] is False
    assert receipt["latent_vector_persisted"] is False
    assert "volatile_embedding" not in receipt["encoder"]


def test_pipeline_evaluates_observed_image_surprise(tmp_path: Path) -> None:
    comfy_root, image = _make_output(tmp_path)
    observed = comfy_root / "output" / "observed.png"
    observed.write_bytes(b"observed")
    source = build_existing_output_receipt(comfy_root=comfy_root, image_path=image)
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = run_media_to_latent_pipeline(
        source_receipt=source,
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        action=[0.0, 0.0],
        observed_image_path=observed,
        encoder_runner=_runner,
    )

    assert receipt["pipeline_completed"] is True
    assert receipt["surprise_evaluated"] is True
    assert receipt["evaluation"]["surprising"] is True
    assert receipt["model_call_count"] == 2
    assert "volatile_embedding" not in receipt["observed_encoder"]


def test_pipeline_rejects_incomplete_execution_receipt(tmp_path: Path) -> None:
    comfy_root, _ = _make_output(tmp_path)
    descriptor = build_frozen_encoder_descriptor(device="cpu")

    receipt = run_media_to_latent_pipeline(
        source_receipt={
            "receipt_type": "comfyui_execution_v1",
            "status": "timeout",
            "generation_performed": False,
            "output_manifest": [],
        },
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        encoder_runner=_runner,
    )

    assert receipt["pipeline_completed"] is False
    assert "comfyui_execution_not_completed" in receipt["blockers"]
    assert "generation_not_performed" in receipt["blockers"]


def test_completed_receipt_can_be_appended_to_jsonl(tmp_path: Path) -> None:
    comfy_root, image = _make_output(tmp_path)
    source = build_existing_output_receipt(comfy_root=comfy_root, image_path=image)
    descriptor = build_frozen_encoder_descriptor(device="cpu")
    receipt = run_media_to_latent_pipeline(
        source_receipt=source,
        comfy_root=comfy_root,
        encoder_descriptor=descriptor,
        encoder_runner=_runner,
    )
    target = tmp_path / "receipts" / "media-latent.jsonl"

    append_receipt_jsonl(target, receipt)

    row = json.loads(target.read_text(encoding="utf-8"))
    assert row["receipt_hash"] == receipt["receipt_hash"]
    assert row["latent_vector_persisted"] is False


def test_blocked_receipt_cannot_be_persisted(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="completed"):
        append_receipt_jsonl(
            tmp_path / "blocked.jsonl",
            {"pipeline_completed": False},
        )
