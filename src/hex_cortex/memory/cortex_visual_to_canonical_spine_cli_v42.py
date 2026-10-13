"""V42 integration of real verified object pixels with existing CanonicalSpine."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_visual_to_canonical_spine_v42 import (
    integrate_v41_with_canonical_spine_v42,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="V42 visually verified mask prediction -> real hash-chained CanonicalSpine"
    )
    p.add_argument("--project-root", default=".")
    p.add_argument("--inspection-run", default="latest")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--persist", action="store_true")
    p.add_argument("--approve-write", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run",
            "files_read": False,
            "files_written": False,
            "model_called": False,
            "spine_event_created": False,
        }, sort_keys=True))
        return 0
    try:
        output = integrate_v41_with_canonical_spine_v42(
            project_root=Path(args.project_root),
            inspection_run=args.inspection_run,
            approved_read=args.approve_read,
            persist=args.persist,
            approved_write=args.approve_write,
        )
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as exc:
        error = str(exc)
        output = {
            "status": "blocked",
            "reason": error if error.startswith(("v39_", "v41_", "v42_")) else "v42_execution_blocked",
            "files_written": False,
            "model_called": False,
        }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0 if output["status"] in {
        "canonical_spine_visual_predictions_persisted",
        "canonical_spine_visual_predictions_staged_in_memory",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
