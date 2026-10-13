"""CPU-only operator interface: routed scientific cell plus real Ollama Brain."""
from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cortex_verified_science_circuit_cli import _EXAMPLES
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget, Capability, LocalHarness, Session, Task,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_science_brain_bridge import run_science_guided_brain

_QUESTIONS = {
    "mathematics": "Give the exact rational result.",
    "physics": "Give the force from the idealized classical formula and its SI unit.",
    "chemistry": "Give the idealized balanced equation coefficients, not a synthesis plan.",
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gated science + Qwen via real Harness, local CPU only."
    )
    parser.add_argument("--domain", required=True, choices=list(_EXAMPLES))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--example", action="store_true")
    source.add_argument("--request")
    parser.add_argument("--question")
    parser.add_argument("--model", required=True)
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--approve-science", action="store_true")
    parser.add_argument("--approve-model", action="store_true")
    parser.add_argument("--show-answer", action="store_true")
    parser.add_argument("--strict-answer", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "domain": args.domain, "provider": "ollama_local",
            "num_gpu": 0, "model_calls_performed": 0,
            "files_read": False, "files_written": False,
            "science_calculation_performed": False,
        }, sort_keys=True))
        return 0
    if not args.approve_science or not args.approve_model:
        print(json.dumps({
            "status": "blocked", "reason": "independent_science_and_model_approval_required",
            "model_calls": 0,
        }))
        return 2

    try:
        root = args.project_root.resolve(strict=True)
        brain = LocalOllamaBrain(
            endpoint=args.endpoint, timeout_seconds=args.timeout,
            max_predict_tokens=args.max_tokens, num_gpu=0,
        )
        harness = LocalHarness(
            session=Session("science-brain", root),
            grants=frozenset({Capability.CALL_MODEL}),
            budget=Budget(max_model_calls=1, max_tool_calls=0),
        )
        result = run_science_guided_brain(
            harness=harness,
            task=Task("science-brain-local", args.domain, args.question or _QUESTIONS[args.domain]),
            scientific_request=_EXAMPLES[args.domain] if args.example else args.request,
            domain=args.domain,
            model_id=args.model,
            brain=brain,
            approve_science=True,
            approve_model=True,
            max_latency_ms=round(args.timeout * 1_000),
            strict_answer=args.strict_answer,
        )
    except (ValueError, TypeError, OSError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    answer = result.pop("answer", None)
    result["answer_sha256"] = (
        hashlib.sha256(answer.encode("utf-8")).hexdigest() if isinstance(answer, str) else None
    )
    result["answer"] = answer if args.show_answer else None
    result["gpu_used"] = False
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
