"""Read-only actual new-image test on operator-provided pair and action.

Does not create example images: the operator must provide two genuine
locally available different frames and the action applied between them.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_novel_visual_pair_v33 import evaluate_new_visual_pair


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Check exact image novelty; optionally compare DINOv2+active compact on CPU."
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--image-root", type=Path, required=True)
    p.add_argument("--current-image", required=True)
    p.add_argument("--next-image", required=True)
    p.add_argument("--action", required=True,
                   help="Four comma-separated values matching the historical visual-transform action schema.")
    p.add_argument("--action-schema", default="brightness,contrast,translate_x,translate_y")
    p.add_argument("--model-ref", default="facebook/dinov2-base")
    p.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-encode", action="store_true")
    p.add_argument("--approve-inference", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "encoder_calls": 0, "model_forward_calls": 0,
            "gpu_used": False, "files_written": False,
        }))
        return 0
    if (args.approve_encode or args.approve_inference) and not (
        args.approve_encode and args.approve_inference and args.approve_read
    ):
        p.error("CPU evaluation requires ALL three flags: --approve-read --approve-encode --approve-inference")
    try:
        action = [float(chunk) for chunk in args.action.split(",")]
        schema = args.action_schema.split(",")
        report = evaluate_new_visual_pair(
            project_root=args.project_root, image_root=args.image_root,
            current_image=args.current_image, next_image=args.next_image,
            action=action, action_schema=schema,
            approved_read=args.approve_read,
            approved_encoding=args.approve_encode,
            approved_inference=args.approve_inference,
            model_ref=args.model_ref, pooling=args.pooling,
        )
    except (ValueError, OSError, TypeError, RuntimeError, OverflowError) as exc:
        print(json.dumps({
            "status": "blocked",
            "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] in (
        "novel_pair_preflight_only",
        "single_novel_pair_cpu_comparison_recorded",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
