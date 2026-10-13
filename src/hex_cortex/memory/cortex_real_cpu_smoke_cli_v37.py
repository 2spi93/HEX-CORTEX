"""Operator-gated V37 MobileSAM synthetic CPU smoke CLI."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_real_cpu_smoke_v37 import run_real_cpu_smoke_v37


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V37 synthetic CPU MobileSAM smoke; not real image quality proof",
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-model-load", action="store_true")
    parser.add_argument("--approve-temp-write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "model_called": False, "files_read": False,
            "files_written": False, "gpu_used": False, "independent_visual_generalization_attested": False,
        }, sort_keys=True))
        return 0
    try:
        result = run_real_cpu_smoke_v37(
            project_root=Path(args.project_root),
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            approved_read=args.approve_read,
            approved_model_load=args.approve_model_load,
            approved_temp_write=args.approve_temp_write,
        )
    except (OSError, ValueError, RuntimeError, ImportError) as exc:
        raw_reason = str(exc)
        result = {
            "status": "blocked",
            "reason": raw_reason if raw_reason.startswith(("v36_", "v37_")) else "v37_runtime_error",
            "successful_model_run_attested": False,
            "persistent_files_written": False,
            "gpu_used": False,
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "synthetic_smoke_executed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
