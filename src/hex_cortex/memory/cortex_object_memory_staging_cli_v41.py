"""Read-only, opt-in V41 object pixel evidence staging, no CanonicalSpine mutation."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_object_memory_staging_v41 import (
    stage_verified_object_candidates_v41,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="V41: stage SHA-verified V40 object masks as unpromoted candidates"
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--inspection-run", default="latest")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "dry_run", "files_read": False, "files_written": False,
            "model_called": False, "promotion_to_long_term_memory_permitted": False,
        }, sort_keys=True))
        return 0
    try:
        result = stage_verified_object_candidates_v41(
            project_root=Path(args.project_root),
            inspection_run=args.inspection_run, approved_read=args.approve_read,
        )
    except (OSError, ValueError, TypeError, KeyError, ImportError) as exc:
        reason = str(exc)
        result = {
            "status": "blocked",
            "reason": reason if reason.startswith(("v39_", "v41_")) else "v41_input_invalid",
            "files_written": False,
            "model_called": False,
            "promotion_to_long_term_memory_permitted": False,
        }
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "verified_pixels_pending_memory_lineage" else 2


if __name__ == "__main__":
    raise SystemExit(main())
