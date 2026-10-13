"""Governed physics/chemistry fact -> Spine -> Replay -> optional checkpoint.

The CLI runs existing exact idealized science cells, not a model, GPU,
physical instrument or web provider. Checkpoint persistence is opt-in.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cortex_verified_science_circuit_cli import _EXAMPLES
from hex_cortex.memory.cortex_verified_science_memory_v23 import (
    append_verified_science_fact,
    verify_science_fact_task,
)
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore

_DOMAINS = ("physics", "chemistry")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline verified idealized science facts through Replay/Memory."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--domain", choices=_DOMAINS, required=True)
    parser.add_argument("--task-id", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--example", action="store_true")
    source.add_argument("--request")
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
            "domain": args.domain,
            "model_called": False,
            "gpu_used": False,
            "calculation_performed": False,
            "files_read": False,
            "files_written": False,
        }, sort_keys=True))
        return 0
    if args.approve_persist and not (args.approve_record and args.approve_promote):
        parser.error("persistence requires approved fact creation and promotion")
    if args.spine_output or args.checkpoint_output:
        if not args.approve_persist:
            parser.error("output paths require --approve-persist")
    if args.approve_persist and not (args.spine_output and args.checkpoint_output):
        parser.error("persistence requires two distinct explicit output paths")

    try:
        root = args.project_root.resolve(strict=True)
        spine = CanonicalSpine()
        append_verified_science_fact(
            spine, domain=args.domain, task_id=args.task_id,
            request_text=_EXAMPLES[args.domain] if args.example else args.request,
            approved=args.approve_record,
        )
        if not verify_science_fact_task(spine, args.task_id):
            raise ValueError("science_fact_verification_failed")
        loop = VerifiedLearningLoop(spine=spine)
        result = loop.run(
            task_id=args.task_id,
            query=RetrievalQuery(query="Verified idealized"),
            approve_promotion=args.approve_promote,
        )
        if args.approve_persist:
            if result.promotion is None or result.promotion.status.value != "promoted":
                raise ValueError("science_fact_promotion_not_approved")
            assert args.spine_output is not None
            assert args.checkpoint_output is not None
            source_path = VerifiedLearningLoop._target(
                root, Path(args.spine_output)
            )
            checkpoint_path = VerifiedLearningLoop._target(
                root, Path(args.checkpoint_output)
            )
            if (
                source_path == checkpoint_path
                or source_path.exists()
                or checkpoint_path.exists()
            ):
                raise ValueError("science_fact_outputs_must_be_new_and_distinct")
            CanonicalSpineJsonlStore(source_path).save(spine)
            loop.save_checkpoint(
                project_root=root,
                relative_path=Path(args.checkpoint_output),
                approved=True,
            )
        print(json.dumps({
            "status": "verified_science_fact",
            "domain": args.domain,
            "model_called": False,
            "spine_verified": spine.verify_integrity().ok,
            "replay_status": result.replay.status.value,
            "promotion_status": result.promotion.status.value
            if result.promotion else None,
            "retrieval_count": len(result.context.results),
            "checkpoint_records": len(loop.checkpoint_records),
            "files_saved": bool(args.approve_persist),
            "physical_world_science_certified": False,
        }, sort_keys=True))
        return 0
    except (ValueError, TypeError, OSError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
