"""Operator-authorized local cached DINOv2 image embedding, CPU-only."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_vision_bridge_v26 import encode_operator_image


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Read PNG and encode using already-cached local DINOv2 weights."
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--image", type=Path, required=True)
    p.add_argument("--model-ref", default="facebook/dinov2-base")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-encode", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "files_written": False, "encoder_called": False,
            "network_allowed": False, "device": "cpu",
        }))
        return 0
    try:
        output = encode_operator_image(
            project_root=args.project_root, image_path=args.image,
            approved_read=args.approve_read,
            approved_encoding=args.approve_encode,
            model_ref=args.model_ref,
        )
    except (ValueError, OSError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(output, sort_keys=True))
    return 0 if output["status"] == "embedding_created" else 2


if __name__ == "__main__":
    raise SystemExit(main())
