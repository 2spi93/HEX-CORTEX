"""CPU-only V25 experimental skill transfer; no autonomous skill activation."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_procedural_skill_evidence_v25 import record_skill_trial
from hex_cortex.memory.cortex_procedural_transfer_v25 import (
    evaluate_procedural_transfer,
)

_SUITES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "multiply_decomposition": (
        ("127*413", "23*51", "-37*84"),
        ("127*419", "1379*2843", "6173*7919", "-429*317"),
    ),
    "fraction_reduction": (
        ("49/14", "-36/48", "128/96"),
        ("224/56", "-77/44", "1309/187", "315/280"),
    ),
    "addition_compensation": (
        ("127+413", "-125+72", "99+98"),
        ("1379+2843", "-517+728", "6173+7919", "9998+657"),
    ),
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Real Harness comparison of three bounded procedural method skills."
    )
    parser.add_argument("--skill", required=True, choices=list(_SUITES))
    parser.add_argument("--model", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-tokens", type=int, default=72)
    parser.add_argument("--cases", type=int, default=4)
    parser.add_argument(
        "--order", choices=["baseline-first", "skill-first"],
        default="baseline-first",
    )
    parser.add_argument("--approve-model-calls", action="store_true")
    parser.add_argument("--approve-procedure", action="store_true")
    parser.add_argument("--show-answers", action="store_true")
    parser.add_argument("--save-evidence", action="store_true")
    parser.add_argument("--approve-save-evidence", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1 <= args.cases <= 4:
        parser.error("--cases must be from 1 to 4")
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "skill": args.skill,
            "model": args.model, "num_gpu": 0,
            "max_model_calls": args.cases * 2,
            "model_calls_performed": 0, "files_written": False,
            "legacy_skill_activation_performed": False,
            "training_examples": 3,
            "test_examples": args.cases,
        }, sort_keys=True))
        return 0
    if args.save_evidence != args.approve_save_evidence:
        parser.error("--save-evidence and --approve-save-evidence must be supplied together")
    if not (args.approve_model_calls and args.approve_procedure):
        print(json.dumps({"status": "blocked", "model_calls": 0,
                          "reason": "two_explicit_approvals_required"}))
        return 2
    try:
        train, test = _SUITES[args.skill]
        brain = LocalOllamaBrain(
            endpoint=args.endpoint,
            timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens,
            num_gpu=0,
        )
        report = evaluate_procedural_transfer(
            skill_id=args.skill,
            training_expressions=train,
            evaluation_expressions=test[:args.cases],
            model_id=args.model,
            brain=brain,
            project_root=args.project_root,
            approve_model_calls=True,
            approve_procedure=True,
            order=args.order,
            show_answers=args.show_answers,
            max_latency_ms=round(args.timeout * 1000),
        )
    except (ValueError, TypeError, PermissionError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    if args.save_evidence and report["status"] == "procedural_transfer_observations_recorded":
        try:
            receipt = record_skill_trial(
                project_root=args.project_root, report=report, approved=True,
            )
        except (ValueError, PermissionError, OSError) as exc:
            print(json.dumps({"status": "evidence_write_blocked", "reason": str(exc),
                              "model_calls_already_completed": report["model_calls"]}))
            return 2
        report["evidence_receipt"] = receipt
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))
    return 0 if report["status"] == "procedural_transfer_observations_recorded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
