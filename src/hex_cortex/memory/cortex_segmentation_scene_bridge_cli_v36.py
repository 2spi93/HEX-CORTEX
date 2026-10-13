"""V36-C read-approved CLI to map saved segmentation JSON to object scene metadata."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_segmentation_scene_bridge_v36 import (
    build_scene_from_cpu_masks,
)


def _labels(values: list[str]) -> dict[str, str]:
    out = {}
    for spec in values:
        if "=" not in spec:
            raise ValueError("v36_bridge_label_syntax_invalid")
        key, val = spec.split("=", 1)
        if not key or not val or key in out:
            raise ValueError("v36_bridge_label_syntax_invalid")
        out[key] = val
    return out


def _denied_constant(value: str):
    raise ValueError("v36_bridge_nonfinite_json_denied")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="V36: read-approved segmentation receipt to scene")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--receipt", required=True, help="relative JSON file within project")
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--source-group", required=True)
    parser.add_argument("--split", required=True, choices=("train", "validation", "test"))
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--source-event-id", action="append", required=True)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run or not args.approve_read:
        result = {
            "status": "dry_run" if args.dry_run else "blocked",
            "reason": None if args.dry_run else "v36_bridge_approval_required",
            "files_read": False, "files_written": False,
            "model_called": False,
        }
        print(json.dumps(result, sort_keys=True))
        return 0 if args.dry_run else 2
    try:
        root = Path(args.project_root).resolve(strict=True)
        rel = Path(args.receipt)
        if rel.is_absolute() or ".." in rel.parts or rel.suffix.lower() != ".json":
            raise ValueError("v36_bridge_receipt_path_denied")
        path = root / rel
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("v36_bridge_receipt_path_denied")
        if not path.is_file() or not 0 < path.stat().st_size <= 2_000_000:
            raise ValueError("v36_bridge_receipt_file_denied")
        with path.open("r", encoding="utf-8") as source:
            data = json.load(source, parse_constant=_denied_constant)
        result = build_scene_from_cpu_masks(
            segmentation_receipt=data,
            scene_id=args.scene_id,
            source_group=args.source_group,
            split=args.split,
            object_labels=_labels(args.label),
            source_event_ids=args.source_event_id,
        )
    except (OSError, ValueError, TypeError) as exc:
        reason = str(exc)
        if not reason.startswith("v36_"):
            reason = "v36_bridge_input_invalid"
        result = {
            "status": "blocked", "reason": reason,
            "files_written": False, "model_called": False,
        }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "v36_cpu_segmentation_scene_built" else 2


if __name__ == "__main__":
    raise SystemExit(main())
