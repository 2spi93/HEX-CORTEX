"""Local operator CLI: read-only repo diagnostic or approved local LLM run."""

from __future__ import annotations

import argparse
import json
import platform
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    Task,
    build_readonly_harness,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_benchmark_v2 import load_experimental_priors


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
    parser.add_argument("--fingerprint-registry", type=Path)
    parser.add_argument("--hardware", default=platform.node() or "unknown-local-host")
    parser.add_argument("--model-digest", action="append", default=[])
    parser.add_argument("--allow-unmeasured", action="store_true")
    parser.add_argument("--spine-output", type=Path)
    parser.add_argument("--approve-save-receipt", action="store_true")
    args = parser.parse_args(argv)

    try:
        harness = build_readonly_harness(args.project_root, session_id=args.session)
        if args.model:
            digests = {}
            for entry in args.model_digest:
                if "=" not in entry:
                    raise ValueError("--model-digest requires model=sha256:...")
                model_id, digest = entry.split("=", 1)
                if not model_id or not digest:
                    raise ValueError("model digest mapping must not be empty")
                digests[model_id] = digest
            if args.fingerprint_registry:
                harness.priors = load_experimental_priors(
                    args.fingerprint_registry, domain=args.domain,
                    hardware_id=args.hardware, model_digests=digests,
                )
            if (
                len(args.model) > 1
                and not args.allow_unmeasured
                and any(model not in harness.priors for model in args.model)
            ):
                raise ValueError("measured fingerprints required for all routing candidates")
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
    if args.spine_output is not None:
        try:
            result["canonical_spine_event_count"] = harness.save_spine(
                args.spine_output, approved=args.approve_save_receipt,
            )
        except (PermissionError, ValueError, OSError) as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
