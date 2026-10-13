"""Deep disk integrity and leakage audit of existing world-model artifacts.

No downloads, PyTorch, GPU, model inference, training, or modifications.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_active_world_integrity_v31 import (
    audit_active_compact_integrity,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify actual V1 active world model bytes, hashes, dataset and split overlaps."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "files_written": False, "models_called": False,
            "gpu_used": False, "hardware_polled": False,
        }))
        return 0
    if not args.approve_read:
        print(json.dumps({
            "status": "blocked",
            "reason": "active_integrity_file_read_requires_approval",
            "files_read": False, "files_written": False,
        }))
        return 2
    try:
        report = audit_active_compact_integrity(
            project_root=args.project_root,
            state_root=args.state_root,
            approved=True,
        )
    except (ValueError, OSError, PermissionError, TypeError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["integrity_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
