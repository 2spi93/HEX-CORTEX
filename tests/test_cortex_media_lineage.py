from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_media_to_latent_pipeline import build_existing_output_receipt
from hex_cortex.memory.cortex_media_to_latent_pipeline import run_media_to_latent_pipeline


def _runner(image_path, model_ref, pooling, device, local_files_only):
    return [1.0, 0.0, 0.0, 0.0], {
        "device": "cpu",
        "model_eval_mode": True,
        "requires_grad": False,
    }


def test_pipeline_preserves_original_upstream_receipt_hash(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    output_root = comfy_root / "output"
    output_root.mkdir(parents=True)
    image = output_root / "image.png"
    image.write_bytes(b"png")
    original_hash = "f" * 64
    source = build_existing_output_receipt(
        comfy_root=comfy_root,
        image_path=image,
        source_receipt_hash=original_hash,
    )

    receipt = run_media_to_latent_pipeline(
        source_receipt=source,
        comfy_root=comfy_root,
        encoder_descriptor=build_frozen_encoder_descriptor(device="cpu"),
        encoder_runner=_runner,
    )

    assert receipt["source_receipt_hash"] == source["receipt_hash"]
    assert receipt["upstream_source_receipt_hash"] == original_hash
    assert receipt["receipt_hash"]


def test_direct_execution_receipt_uses_its_own_hash_as_upstream(tmp_path: Path) -> None:
    comfy_root = tmp_path / "ComfyUI"
    output_root = comfy_root / "output"
    output_root.mkdir(parents=True)
    image = output_root / "image.png"
    image.write_bytes(b"png")
    execution_hash = "a" * 64
    source = {
        "receipt_type": "comfyui_execution_v1",
        "status": "completed",
        "generation_performed": True,
        "receipt_hash": execution_hash,
        "output_manifest": [
            {
                "asset_kind": "images",
                "filename": "image.png",
                "subfolder": "",
                "folder_type": "output",
                "node_id": "9",
            }
        ],
    }

    receipt = run_media_to_latent_pipeline(
        source_receipt=source,
        comfy_root=comfy_root,
        encoder_descriptor=build_frozen_encoder_descriptor(device="cpu"),
        encoder_runner=_runner,
    )

    assert receipt["source_receipt_hash"] == execution_hash
    assert receipt["upstream_source_receipt_hash"] == execution_hash
