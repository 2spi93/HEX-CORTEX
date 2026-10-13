"""Read-only by default CLI for the verified local learning loop.

Usage: python -m hex_cortex.memory.verified_learning_cli --help
Only loads explicitly named local files; it does not invoke a model.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _existing_spine_path(root: Path, supplied: str) -> Path:
    raw = root / supplied
    if raw.is_symlink() or raw.parent.is_symlink():
        raise ValueError("spine_symlink_denied")
    target = raw.resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise ValueError("spine_must_be_existing_file_inside_project")
    return target


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Opt-in offline replay/promotion/retrieval, without a model or GPU."
    )
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--spine-file", required=True)
    parser.add_argument("--task-id")
    parser.add_argument("--query", required=True)
    parser.add_argument("--approve-promotion", action="store_true")
    parser.add_argument("--override-low-confidence", action="store_true")
    parser.add_argument("--save-checkpoint")
    parser.add_argument("--approve-persist", action="store_true")
    parser.add_argument("--restore-checkpoint")
    args = parser.parse_args(argv)
    if args.restore_checkpoint and (args.task_id or args.approve_promotion or args.save_checkpoint):
        parser.error("restore-checkpoint cannot be combined with task or promotion")
    if not args.restore_checkpoint and not args.task_id:
        parser.error("--task-id is required unless --restore-checkpoint is supplied")
    if args.override_low_confidence and not args.approve_promotion:
        parser.error("confidence override requires explicit promotion approval")
    if args.save_checkpoint and not (args.approve_promotion and args.approve_persist):
        parser.error("checkpoint persistence requires both explicit approvals")
    if args.approve_persist and not args.save_checkpoint:
        parser.error("--approve-persist requires --save-checkpoint")

    root = Path(args.project_root).resolve(strict=True)
    spine_path = _existing_spine_path(root, args.spine_file)
    spine = CanonicalSpineJsonlStore(spine_path).load()
    query = RetrievalQuery(query=args.query)
    if args.restore_checkpoint:
        loop = VerifiedLearningLoop.restore_checkpoint(
            project_root=root,
            relative_path=Path(args.restore_checkpoint),
            spine=spine,
        )
        # Never re-promote during a restore-only retrieval.
        result = loop.run(task_id="__checkpoint_read_only__", query=query)
    else:
        loop = VerifiedLearningLoop(spine=spine)
        result = loop.run(
            task_id=args.task_id,
            query=query,
            approve_promotion=args.approve_promotion,
            override_low_confidence=args.override_low_confidence,
        )
        if args.save_checkpoint:
            if not loop.checkpoint_records:
                raise ValueError("no_verified_promotion_to_checkpoint")
            loop.save_checkpoint(
                project_root=root,
                relative_path=Path(args.save_checkpoint),
                approved=args.approve_persist,
            )
    print(json.dumps({
        "replay_status": result.replay.status.value,
        "promotion_status": result.promotion.status.value if result.promotion else None,
        "retrieval_method": result.context.method.value,
        "retrieval_count": len(result.context.results),
        "checkpoint_records": len(loop.checkpoint_records),
        "spine_integrity_ok": spine.verify_integrity().ok,
        "real_model_amplification_measured": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
