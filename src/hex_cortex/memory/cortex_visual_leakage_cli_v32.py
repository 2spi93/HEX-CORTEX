"""Explicit read-only V32 audit on verified existing V1 transition records."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_active_world_integrity_v31 import (
    audit_active_compact_integrity,
)
from hex_cortex.memory.cortex_observed_transition_dataset import (
    load_transition_records,
)
from hex_cortex.memory.cortex_visual_leakage_graph_v32 import (
    inspect_visual_overlap_graph,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect actual image-source cross-split graph, no changes."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "files_read": False,
            "model_called": False, "data_modified": False,
            "files_written": False, "gpu_used": False,
        }))
        return 0
    if not args.approve_read:
        print(json.dumps({
            "status": "blocked", "reason": "visual_overlap_graph_approval_required",
            "files_read": False, "files_written": False,
        }))
        return 2
    try:
        root = args.project_root.resolve(strict=True)
        integrity = audit_active_compact_integrity(
            project_root=root, approved=True,
        )
        if integrity.get("artifact_chain_ok") is not True:
            print(json.dumps({
                "status": "blocked",
                "reason": "active_dataset_integrity_must_be_verified_first",
                "artifact_integrity_blockers": [
                    item for item in integrity["blockers"]
                    if item not in (
                        "exact_image_overlap_between_splits",
                        "exact_transition_pair_overlap_between_splits",
                    )
                ],
                "files_written": False,
            }, sort_keys=True))
            return 2
        dataset = root / ".hex-cortex" / "world-model" / "transitions.jsonl"
        if dataset.is_symlink() or not dataset.is_file():
            raise ValueError("visual_graph_dataset_unavailable")
        records = load_transition_records(dataset)
        report = inspect_visual_overlap_graph(records, approved=True)
        report["artifact_chain_verified_before_graph"] = True
        report["underlying_checkpoint_executes_cpu"] = "not_evaluated_by_this_command"
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "files_written": False,
        }))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    # Leakage detection is a successful DIAGNOSTIC, not a command error.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
