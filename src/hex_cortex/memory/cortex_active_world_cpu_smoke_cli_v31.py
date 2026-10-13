"""Operator-gated single real CPU forward of already-active compact weights."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_active_world_cpu_smoke_v31 import (
    run_active_world_cpu_smoke,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify real active safetensors CPU runtime, without encoder or device."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-inference", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "model_forward_calls": 0, "gpu_used": False,
            "files_written": False, "hardware_polled": False,
        }, sort_keys=True))
        return 0
    if not args.approve_read or not args.approve_inference:
        print(json.dumps({
            "status": "blocked",
            "reason": "active_world_smoke_requires_read_and_cpu_inference_approval",
            "model_forward_calls": 0, "files_written": False,
        }))
        return 2
    try:
        result = run_active_world_cpu_smoke(
            project_root=args.project_root,
            approved_read=True, approved_inference=True,
        )
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "cpu_forward_completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
