"""Explicit exact-math fact -> Spine -> Replay -> promotion -> checkpoint CLI.

CPU-only Python arithmetic, no Ollama or model calls. Files are written
only when the operator supplies both target paths and --approve-persist.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_verified_math_memory import (
    append_verified_math_fact,
    verify_math_fact_task,
)
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="ExactMathCell fact to governed memory without a model or GPU."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--expression", required=True)
    parser.add_argument("--query")
    parser.add_argument("--approve-record", action="store_true")
    parser.add_argument("--approve-promote", action="store_true")
    parser.add_argument("--approve-persist", action="store_true")
    parser.add_argument("--spine-output")
    parser.add_argument("--checkpoint-output")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "will_call_model": False,
            "will_read_files": False,
            "will_write_files": False,
            "will_use_gpu": False,
            "will_promote_if_authorized": args.approve_promote,
        }, sort_keys=True))
        return 0
    if args.approve_persist and not args.approve_record:
        parser.error("persistence requires approved fact creation")
    if args.checkpoint_output and not args.approve_promote:
        parser.error("checkpoint requires explicit memory promotion")
    if (args.spine_output or args.checkpoint_output) and not args.approve_persist:
        parser.error("saving files requires --approve-persist")
    if args.approve_persist and not (args.spine_output and args.checkpoint_output):
        parser.error("persistence requires both independent Spine and checkpoint paths")

    try:
        root = args.project_root.resolve(strict=True)
        spine = CanonicalSpine()
        creation = append_verified_math_fact(
            spine, task_id=args.task_id, expression=args.expression,
            approved=args.approve_record,
        )
        if not verify_math_fact_task(spine, args.task_id):
            raise ValueError("math_fact_not_independently_verified")
        learning = VerifiedLearningLoop(spine=spine)
        outcome = learning.run(
            task_id=args.task_id,
            query=RetrievalQuery(query=args.query or args.expression),
            approve_promotion=args.approve_promote,
        )
        if args.approve_persist:
            if outcome.promotion is None or outcome.promotion.status.value != "promoted":
                raise ValueError("math_fact_cannot_persist_without_valid_promotion")
            assert args.spine_output is not None and args.checkpoint_output is not None
            spine_path = VerifiedLearningLoop._target(root, Path(args.spine_output))
            checkpoint_path = VerifiedLearningLoop._target(
                root, Path(args.checkpoint_output)
            )
            if spine_path == checkpoint_path or spine_path.exists() or checkpoint_path.exists():
                raise ValueError("math_fact_paths_must_be_new_and_distinct")
            CanonicalSpineJsonlStore(spine_path).save(spine)
            learning.save_checkpoint(
                project_root=root,
                relative_path=Path(args.checkpoint_output), approved=True,
            )
        print(json.dumps({
            "status": creation["status"],
            "task_id": args.task_id,
            "math_fact_verified": True,
            "spine_integrity_ok": spine.verify_integrity().ok,
            "replay_status": outcome.replay.status.value,
            "promotion_status": outcome.promotion.status.value
            if outcome.promotion else None,
            "retrieval_count": len(outcome.context.results),
            "checkpoint_records": len(learning.checkpoint_records),
            "saved": bool(args.approve_persist),
            "spine_file": args.spine_output if args.approve_persist else None,
            "checkpoint_file": args.checkpoint_output if args.approve_persist else None,
            "model_called": False,
            "gpu_used": False,
        }, sort_keys=True))
        return 0
    except (ValueError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
