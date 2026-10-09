"""Local operator CLI: read-only repo diagnostic or approved local LLM run."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    Task,
    build_readonly_harness,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-harness")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--session", default="local")
    parser.add_argument("--task-id", default="inspect-local-checkout")
    parser.add_argument("--approve-read", action="store_true")
    parser.add_argument("--approve-model", action="store_true")
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--instruction", default="Inspect local checkout")
    parser.add_argument("--domain", default="coding")
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-tokens", type=int, default=768)
    args = parser.parse_args(argv)

    try:
        harness = build_readonly_harness(args.project_root, session_id=args.session)
        if args.model:
            harness.grants = frozenset(
                {Capability.READ_REPO, Capability.CALL_MODEL}
            ) if args.approve_model else frozenset({Capability.READ_REPO})
            harness.budget = Budget(max_model_calls=1, max_tool_calls=0)
            brain = LocalOllamaBrain(
                endpoint=args.endpoint, timeout_seconds=args.timeout,
                max_predict_tokens=args.max_tokens,
            )
            result = harness.execute(
                Task(args.task_id, args.domain, args.instruction),
                models=args.model, brain=brain, approved=args.approve_model,
            )
        else:
            result = harness.execute(
                Task(
                    args.task_id, "repo_read", args.instruction, "repo_manifest"
                ),
                approved=args.approve_read,
            )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
