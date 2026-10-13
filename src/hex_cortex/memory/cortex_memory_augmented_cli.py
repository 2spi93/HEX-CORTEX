"""Explicit local-only Ollama entry point for the verified memory-augmented Harness."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_memory_augmented_run import run_memory_augmented_task
from hex_cortex.memory.schemas import RetrievalQuery
from hex_cortex.memory.verified_learning_cli import _existing_spine_path
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CPU-only opt-in local Ollama reasoning, optionally with verified memory."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--spine-file", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--target-math-expression")
    parser.add_argument("--task-id", required=True)
    parser.add_argument("--instruction", required=True)
    parser.add_argument("--domain", default="general")
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=256)
    parser.add_argument("--approve-model", action="store_true")
    parser.add_argument("--approve-memory-use", action="store_true")
    parser.add_argument("--print-answer", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.approve_memory_use and not args.approve_model:
        parser.error("--approve-memory-use requires --approve-model")
    if args.approve_memory_use and not args.checkpoint:
        parser.error("--approve-memory-use requires --checkpoint")
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "model": args.model,
            "num_gpu": 0,
            "provider": "ollama_local",
            "will_call_model": False,
            "will_read_spine": False,
            "will_write_files": False,
            "use_memory_if_authorized": args.approve_memory_use,
        }, sort_keys=True))
        return 0

    try:
        root = args.project_root.resolve(strict=True)
        spine_path = _existing_spine_path(root, args.spine_file)
        spine = CanonicalSpineJsonlStore(spine_path).load()
        if args.approve_memory_use:
            assert args.checkpoint is not None
            learning = VerifiedLearningLoop.restore_checkpoint(
                project_root=root,
                relative_path=Path(args.checkpoint),
                spine=spine,
            )
        else:
            learning = VerifiedLearningLoop(spine=spine)
        harness = LocalHarness(
            session=Session(session_id="memory-augmented-local", project_root=root),
            grants=frozenset({Capability.CALL_MODEL}) if args.approve_model else frozenset(),
            budget=Budget(max_model_calls=1, max_tool_calls=0),
            spine=spine,
        )
        brain = LocalOllamaBrain(
            endpoint=args.endpoint, timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens,
            num_gpu=0,
        )
        result = run_memory_augmented_task(
            harness=harness,
            learning=learning,
            task=Task(task_id=args.task_id, domain=args.domain, instruction=args.instruction),
            models=[args.model],
            brain=brain,
            approve_model=args.approve_model,
            approve_memory_use=args.approve_memory_use,
            query=RetrievalQuery(query=args.instruction[:512]),
            target_math_expression=args.target_math_expression,
        )
    except (ValueError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    output = result.get("output")
    receipt = result.get("receipt")
    print(json.dumps({
        "status": result.get("status"),
        "reason": result.get("reason"),
        "memory_context": result.get("memory_context"),
        "spine_integrity_ok": result.get("canonical_spine_verified"),
        "receipt_sha256": receipt.get("sha256") if isinstance(receipt, dict) else None,
        "answer_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest()
        if isinstance(output, str) else None,
        "answer": output if args.print_answer else None,
        "model_calls_permitted": args.approve_model,
        "model_amplification_demonstrated": False,
        "files_saved": False,
        "cpu_only": True,
    }, sort_keys=True, ensure_ascii=False))
    return 0 if result.get("status") == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
