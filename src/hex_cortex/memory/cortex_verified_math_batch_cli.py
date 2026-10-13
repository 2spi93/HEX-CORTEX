"""Operator-gated CPU-only multi-pair local Ollama benchmark CLI."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_verified_math_batch import (
    PUBLIC_MATH_CASES,
    run_verified_math_batch,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Public multi-case calculator-assistance comparison (not held-out)."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--pairs", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument("--approve-math", action="store_true")
    parser.add_argument("--approve-all-calls", action="store_true")
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.pairs <= len(PUBLIC_MATH_CASES):
        parser.error(f"--pairs must be between 1 and {len(PUBLIC_MATH_CASES)}")
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "model": args.model,
            "num_gpu": 0,
            "pairs": args.pairs,
            "max_model_calls": 2 * args.pairs,
            "calls_performed": 0,
            "files_read": False,
            "files_written": False,
            "held_out": False,
            "approved": args.approve_math and args.approve_all_calls,
        }, sort_keys=True))
        return 0
    if not (args.approve_math and args.approve_all_calls):
        print(json.dumps({
            "status": "blocked", "reason": "batch_math_and_model_approvals_required",
            "calls_performed": 0,
        }))
        return 2
    try:
        brain = LocalOllamaBrain(
            endpoint=args.endpoint, timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens, num_gpu=0,
        )
        report = run_verified_math_batch(
            project_root=args.project_root,
            model_id=args.model,
            brain=brain,
            max_pairs=args.pairs,
            approve_math=True,
            approve_all_model_calls=True,
            reveal_outputs=args.show_answers,
            max_latency_ms=round(args.timeout * 1000),
        )
    except (ValueError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "exploratory_pairs_recorded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
