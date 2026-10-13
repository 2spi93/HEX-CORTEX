"""CLI: approved CPU MobileSAM box segmentation with no implicit files/network."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_cpu_segmentation_v36 import segment_boxes_cpu_v36


def _boxes(values: list[str]) -> dict[str, tuple[int, int, int, int]]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError("v36_box_syntax_invalid")
        label, coords = value.split("=", 1)
        parts = coords.split(",")
        if label in result or len(parts) != 4:
            raise ValueError("v36_box_syntax_invalid")
        try:
            result[label] = tuple(int(v) for v in parts)
        except ValueError as exc:
            raise ValueError("v36_box_syntax_invalid") from exc
    return result


def _masks(values: list[str]) -> dict[str, str]:
    result = {}
    for value in values:
        if "=" not in value:
            raise ValueError("v36_reference_mask_syntax_invalid")
        label, path = value.split("=", 1)
        if label in result or not path:
            raise ValueError("v36_reference_mask_syntax_invalid")
        result[label] = path
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V36 real opt-in CPU MobileSAM, manually supplied 2D object boxes"
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--image", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--box", action="append", required=True)
    parser.add_argument("--reference-mask", action="append", default=[])
    parser.add_argument("--export-dir")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-model-load", action="store_true")
    parser.add_argument("--approve-write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "files_read": False, "files_written": False,
            "model_called": False, "network_requested": False, "gpu_used": False,
        }, sort_keys=True))
        return 0
    try:
        report = segment_boxes_cpu_v36(
            project_root=Path(args.project_root),
            image_path=args.image,
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            object_boxes=_boxes(args.box),
            reference_masks=_masks(args.reference_mask) if args.reference_mask else None,
            approved_read=args.approve_read,
            approved_model_load=args.approve_model_load,
            export_dir=args.export_dir,
            approved_write=args.approve_write,
        )
    except (ValueError, OSError) as exc:
        code = str(exc)
        if not code.startswith("v36_"):
            code = "v36_runtime_or_input_error"
        report = {
            "status": "blocked", "reason": code, "model_result_ready": False,
            "files_written": False, "gpu_used": False,
        }
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "segmented_cpu_masks_ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
