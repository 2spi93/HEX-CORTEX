"""Optional completely offline cached DINOv2 readiness for active compact model."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_dinov2_active_preflight_v34 import (
    inspect_active_dinov2,
)


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Match active world descriptor, optionally inspect/load cached DINOv2 CPU only."
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--model-ref", default="facebook/dinov2-base")
    p.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-cache", action="store_true")
    p.add_argument("--approve-load", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "cache_probed": False, "encoder_loaded": False,
            "gpu_used": False, "files_written": False,
        }, sort_keys=True))
        return 0
    try:
        report = inspect_active_dinov2(
            project_root=args.project_root, approved_read=args.approve_read,
            approved_cache_probe=args.approve_cache,
            approved_load=args.approve_load,
            model_ref=args.model_ref, pooling=args.pooling,
        )
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] in (
        "active_encoder_descriptor_matches",
        "active_encoder_cached_files_detected_not_loaded",
        "active_encoder_cached_weights_loaded_cpu",
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
