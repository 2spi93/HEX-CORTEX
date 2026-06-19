from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageEnhance

from hex_cortex.memory.cortex_compact_world_model import build_cached_dinov2_runner
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_observed_transition_dataset import append_transition_jsonl
from hex_cortex.memory.cortex_observed_transition_dataset import capture_observed_transition


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_image")
    parser.add_argument("--comfy-root", required=True)
    parser.add_argument("--dataset-jsonl", required=True)
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args()
    if not args.operator_approved:
        print(json.dumps({"status": "blocked", "blockers": ["operator_approval_required"]}))
        return 2
    if not 3 <= args.count <= 128:
        print(json.dumps({"status": "blocked", "blockers": ["count_out_of_range"]}))
        return 2
    comfy_root = Path(args.comfy_root).resolve()
    output_root = (comfy_root / "output").resolve()
    base_image = Path(args.base_image).resolve()
    if not base_image.is_file() or not base_image.is_relative_to(output_root):
        print(json.dumps({"status": "blocked", "blockers": ["base_image_invalid"]}))
        return 2
    generated_root = output_root / "hex-cortex-transitions"
    generated_root.mkdir(parents=True, exist_ok=True)
    descriptor = build_frozen_encoder_descriptor(device=args.device)
    runner = build_cached_dinov2_runner()
    appended = 0
    duplicates = 0
    split_counts = {"train": 0, "validation": 0, "test": 0}
    with Image.open(base_image) as opened:
        source = opened.convert("RGB")
        for index in range(args.count):
            action = _action(index, args.seed)
            transformed = _apply(source, action)
            target = generated_root / f"controlled-{args.seed}-{index:04d}.png"
            transformed.save(target, format="PNG", optimize=True)
            split = _split(index, args.count)
            record = capture_observed_transition(
                comfy_root=comfy_root,
                current_image_path=base_image,
                next_image_path=target,
                action=action,
                action_schema=["brightness", "contrast", "translate_x", "translate_y"],
                split=split,
                domain="controlled_visual_transform_v1",
                encoder_descriptor=descriptor,
                encoder_runner=runner,
            )
            if record.get("blockers"):
                print(json.dumps(record, sort_keys=True))
                return 2
            receipt = append_transition_jsonl(Path(args.dataset_jsonl), record)
            appended += int(receipt["appended"] is True)
            duplicates += int(receipt["duplicate"] is True)
            split_counts[split] += int(receipt["appended"] is True)
    print(
        json.dumps(
            {
                "status": "completed",
                "dataset_jsonl": str(Path(args.dataset_jsonl).resolve()),
                "sample_count": args.count,
                "appended_count": appended,
                "duplicate_count": duplicates,
                "split_counts": split_counts,
                "domain": "controlled_visual_transform_v1",
                "network_call_performed": False,
                "training_performed": False,
                "next_action": "build_transition_manifest",
            },
            sort_keys=True,
            indent=2,
        )
    )
    return 0


def _action(index: int, seed: int) -> list[float]:
    digest = hashlib.sha256(f"{seed}:{index}".encode("utf-8")).digest()
    values = [round(((digest[offset] / 255.0) * 2.0 - 1.0) * 0.75, 4) for offset in range(4)]
    if all(abs(value) < 0.05 for value in values):
        values[0] = 0.25
    return values


def _split(index: int, count: int) -> str:
    validation = max(1, round(count * 0.15))
    test = max(1, round(count * 0.15))
    train = count - validation - test
    if index < train:
        return "train"
    if index < train + validation:
        return "validation"
    return "test"


def _apply(source: Image.Image, action: list[float]) -> Image.Image:
    image = ImageEnhance.Brightness(source).enhance(max(0.2, 1.0 + action[0] * 0.4))
    image = ImageEnhance.Contrast(image).enhance(max(0.2, 1.0 + action[1] * 0.4))
    tx = int(round(action[2] * source.width * 0.1))
    ty = int(round(action[3] * source.height * 0.1))
    return image.transform(
        source.size,
        Image.Transform.AFFINE,
        (1, 0, -tx, 0, 1, -ty),
        resample=Image.Resampling.BICUBIC,
        fillcolor=(0, 0, 0),
    )


if __name__ == "__main__":
    raise SystemExit(main())
