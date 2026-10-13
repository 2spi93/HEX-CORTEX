"""Command-line V40 replay of V38 masks; no implicit writes or GPU."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_mask_visual_inspection_v40 import (
    export_verified_v40_masks,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V40: replay and visually inspect existing V38 CPU masks"
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--checkpoint", default="weights/mobile_sam.pt")
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--source-run", default="latest")
    parser.add_argument("--manifest", default="research/v38_uploaded/boxes.json")
    parser.add_argument("--scene", action="append")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-model-load", action="store_true")
    parser.add_argument("--approve-write", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "files_read": False, "files_written": False,
            "model_called": False, "selected_scene_names": args.scene or [
                "scene03_jump", "scene07_racecar", "scene09_factory_handover",
            ],
        }, sort_keys=True))
        return 0
    try:
        result = export_verified_v40_masks(
            project_root=Path(args.project_root),
            checkpoint_path=args.checkpoint,
            checkpoint_sha256=args.checkpoint_sha256,
            scenes=args.scene,
            run_selection=args.source_run,
            manifest_path=args.manifest,
            approved_read=args.approve_read,
            approved_model_load=args.approve_model_load,
            approved_write=args.approve_write,
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError, ImportError) as exc:
        message = str(exc)
        result = {
            "status": "blocked",
            "reason": message if message.startswith(("v36_", "v39_", "v40_")) else "v40_execution_failed",
            "files_written": False,
            "model_called_successfully": False,
            "old_v38_evidence_changed": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "verified_mask_replay_exported" else 2


if __name__ == "__main__":
    raise SystemExit(main())
