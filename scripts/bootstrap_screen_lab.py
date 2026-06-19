from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_screen_lab import bootstrap_screen_lab


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace-root", default=".hex-cortex/environments/screen_lab_v1")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--model-ref", default="facebook/dinov2-base")
    parser.add_argument("--pooling", choices=("cls", "mean_patch"), default="cls")
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="cpu")
    parser.add_argument("--replace-existing-source", action="store_true")
    parser.add_argument("--operator-approved", action="store_true")
    args = parser.parse_args()

    descriptor = build_frozen_encoder_descriptor(
        model_ref=args.model_ref,
        pooling=args.pooling,
        device=args.device,
    )
    payload = bootstrap_screen_lab(
        workspace_root=Path(args.workspace_root),
        encoder_descriptor=descriptor,
        operator_approved=args.operator_approved,
        seed=args.seed,
        replace_existing_source=args.replace_existing_source,
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
