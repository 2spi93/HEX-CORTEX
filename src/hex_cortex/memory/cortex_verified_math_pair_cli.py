"""Offline dry-run or explicitly approved CPU-only paired math experiment."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_verified_math_pair import run_verified_math_pair


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Same local Ollama Brain with/without independently verified ExactMathCell."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--expression", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument(
        "--order", choices=["baseline-first", "cortex-first"], default="baseline-first"
    )
    parser.add_argument("--approve-math", action="store_true")
    parser.add_argument("--approve-two-calls", action="store_true")
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "provider": "ollama_local",
            "model": args.model,
            "num_gpu": 0,
            "planned_arms": ["baseline", "cortex"] if args.order == "baseline-first" else [
                "cortex", "baseline"
            ],
            "model_calls_performed": 0,
            "math_cell_executed": False,
            "files_read": False,
            "files_written": False,
            "experiment_authorized": args.approve_math and args.approve_two_calls,
        }, sort_keys=True))
        return 0

    if not (args.approve_math and args.approve_two_calls):
        print(json.dumps({
            "status": "blocked",
            "reason": "explicit_math_and_two_model_call_approvals_required",
            "model_calls": 0,
            "files_saved": False,
        }))
        return 2
    try:
        brain = LocalOllamaBrain(
            endpoint=args.endpoint,
            timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens,
            num_gpu=0,
        )
        report = run_verified_math_pair(
            project_root=args.project_root,
            expression=args.expression,
            model_id=args.model,
            brain=brain,
            approve_math=args.approve_math,
            approve_two_model_calls=args.approve_two_calls,
            order=args.order,
            max_latency_ms=max(1, round(args.timeout * 1_000)),
            reveal_outputs=args.show_answers,
        )
    except (ValueError, PermissionError, OSError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc), "files_saved": False
        }))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "paired_observations_recorded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
