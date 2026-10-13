"""V23 local Ollama four-arm experimental ablation; CPU-only and opt-in."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_four_arm_math_eval_v23 import run_four_arm_math_eval
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain

_ORDERS = (
    ("baseline", "memory", "calculator", "combined"),
    ("combined", "calculator", "memory", "baseline"),
    ("memory", "baseline", "combined", "calculator"),
    ("calculator", "combined", "baseline", "memory"),
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare baseline, verified memory, ExactMathCell and combined on CPU."
    )
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--training-expression", required=True)
    parser.add_argument("--evaluation-expression", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=48)
    parser.add_argument("--order-index", type=int, choices=range(4), default=0)
    parser.add_argument("--approve-model-calls", action="store_true")
    parser.add_argument("--approve-memory", action="store_true")
    parser.add_argument("--approve-calculator", action="store_true")
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    order = _ORDERS[args.order_index]
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "model": args.model,
            "num_gpu": 0,
            "arms": list(order),
            "max_model_calls": 4,
            "model_calls_performed": 0,
            "files_read": False,
            "files_written": False,
            "memory_loaded": False,
            "calculator_executed": False,
            "approved": (
                args.approve_model_calls and args.approve_memory
                and args.approve_calculator
            ),
        }, sort_keys=True))
        return 0
    if not (
        args.approve_model_calls and args.approve_memory and args.approve_calculator
    ):
        print(json.dumps({
            "status": "blocked",
            "reason": "model_memory_and_calculator_approvals_required",
            "model_calls": 0,
        }))
        return 2
    try:
        brain = LocalOllamaBrain(
            endpoint=args.endpoint,
            timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens,
            num_gpu=0,
        )
        report = run_four_arm_math_eval(
            project_root=args.project_root,
            model_id=args.model,
            training_expression=args.training_expression,
            evaluation_expression=args.evaluation_expression,
            brain=brain,
            approve_model_calls=True,
            approve_memory=True,
            approve_calculator=True,
            arm_order=order,
            max_latency_ms=round(args.timeout * 1000),
            show_answers=args.show_answers,
        )
    except (ValueError, TypeError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "four_arm_observations_recorded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
