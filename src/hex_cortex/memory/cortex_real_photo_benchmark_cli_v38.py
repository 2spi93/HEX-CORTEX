"""Operator-controlled V38 real-photo IoU and CPU load-inclusive benchmark CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_real_photo_benchmark_v38 import (
    evaluate_real_photo_masks_v38,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V38 operator-real-photos; masks must be independently annotated"
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-model-load", action="store_true")
    parser.add_argument("--preflight-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        result = {
            "status": "dry_run", "files_read": False, "model_called": False,
            "files_written": False, "gpu_used": False,
            "independent_visual_generalization_attested": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 0
    try:
        result = evaluate_real_photo_masks_v38(
            project_root=Path(args.project_root),
            manifest_path=args.manifest,
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            approved_read=args.approve_read,
            approved_model_load=args.approve_model_load,
            preflight_only=args.preflight_only,
        )
    except (OSError, ValueError, TypeError, RuntimeError, ImportError) as exc:
        reason = str(exc)
        result = {
            "status": "blocked",
            "reason": reason if reason.startswith(("v36_", "v38_")) else "v38_runtime_or_input_error",
            "files_written": False, "gpu_used": False,
            "independent_visual_generalization_attested": False,
        }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] in (
        "manifest_preflight_pass", "operator_real_photo_benchmark_executed",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
