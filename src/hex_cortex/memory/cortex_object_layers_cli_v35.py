"""Real, CPU-only object RGBA compositing; masks supplied by operator/SAM.

No model is downloaded or called. No output files unless the operator
specifies a fresh project-contained directory AND --approve-write.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_object_layers_v35 import compose_visible_object_layers


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Extract visible objects from approved masks and verify exact pixel recomposition.")
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--image", required=True, help="Approved relative input image")
    p.add_argument("--mask", action="append", default=[], help="ObjectID=relative_mask_path.png; repeat for each object")
    p.add_argument("--export-dir", help="Fresh relative directory under project root")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-write", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "files_read": False, "files_written": False,
            "model_called": False, "gpu_used": False,
        }))
        return 0
    masks = []
    for item in args.mask:
        if "=" not in item:
            p.error("--mask must have the form object_id=relative_mask.png")
        name, path = item.split("=", 1)
        masks.append((name, path))
    try:
        receipt = compose_visible_object_layers(
            project_root=args.project_root, image_path=args.image,
            object_masks=masks, approved_read=args.approve_read,
            export_dir=args.export_dir, approved_write=args.approve_write,
        )
    except (ValueError, OSError, TypeError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "visible_object_layers_exactly_recomposed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
