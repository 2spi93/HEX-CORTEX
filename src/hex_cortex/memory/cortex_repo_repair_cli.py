"""Opt-in local CLI for the offline repository-repair probe.

The only transport supported is a localhost Ollama model behind LocalHarness,
CognitiveClock and explicit approval. Offline supplied candidate JSON avoids
model calls. Only aggregate redacted scores are printed or stored.
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
)
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_repo_repair_probe_v3 import (
    CASES,
    render_task_prompt,
    score_repository_benchmark,
    suite_manifest,
)


def run_local_repair_probe(
    *, model_id: str, model_digest: str, quantization: str, hardware_id: str,
    offline_responses: dict[str, str] | None = None,
    approved: bool = False,
    project_root: Path | None = None,
    brain: LocalOllamaBrain | None = None,
    seed: int = 20261009,
) -> dict[str, object]:
    """Run each case through one fresh, separately budgeted local session."""
    if offline_responses is not None:
        responses = offline_responses
        model_calls = 0
    else:
        if not approved:
            raise PermissionError("explicit model call approval required")
        if brain is None:
            brain = LocalOllamaBrain()
        root = (project_root or Path.cwd()).resolve()
        responses = {}
        model_calls = 0
        for case in CASES:
            harness = LocalHarness(
                session=Session(f"repo-probe-{case.case_id}", root),
                grants=frozenset({Capability.CALL_MODEL}),
                budget=Budget(max_model_calls=1, max_tool_calls=0, max_response_chars=16_000),
            )
            result = run_clocked_local_task(
                harness,
                Task(case.case_id, "coding", render_task_prompt(case)),
                models=[model_id],
                brain=brain,
                approved=True,
            )
            # Count only a call actually attempted (not denied/preflight-failed).
            receipt = result.get("receipt")
            if isinstance(receipt, dict):
                model_calls += int(receipt.get("model_calls_used", 0))
            if result.get("status") == "complete" and isinstance(result.get("output"), str):
                responses[case.case_id] = result["output"]
    report = score_repository_benchmark(
        responses,
        model_id=model_id, model_digest=model_digest,
        quantization=quantization, hardware_id=hardware_id, seed=seed,
    )
    report["model_calls_attempted"] = model_calls
    report["localhost_model_requested"] = offline_responses is None
    return report


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-repo-eval")
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--digest", required=True)
    parser.add_argument("--quantization", required=True)
    parser.add_argument("--hardware", default=platform.node() or "unknown-local-host")
    parser.add_argument("--responses", type=Path, help="offline JSON map: task_id -> JSON candidate")
    parser.add_argument("--approve-model", action="store_true")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--max-tokens", type=int, default=1200)
    parser.add_argument("--seed", type=int, default=20261009)
    parser.add_argument("--show-tasks", action="store_true")
    args = parser.parse_args(argv)
    if args.show_tasks:
        print(json.dumps(suite_manifest(), ensure_ascii=False, sort_keys=True))
        return 0
    try:
        if args.responses is None and not args.approve_model:
            raise PermissionError("live Ollama calls require --approve-model")
        supplied = None
        if args.responses is not None:
            supplied = json.loads(args.responses.read_text(encoding="utf-8"))
            if not isinstance(supplied, dict):
                raise ValueError("offline responses must be a JSON object")
        brain = None
        if supplied is None:
            brain = LocalOllamaBrain(
                endpoint=args.endpoint, timeout_seconds=args.timeout,
                max_predict_tokens=args.max_tokens,
            )
        report = run_local_repair_probe(
            model_id=args.model_id, model_digest=args.digest,
            quantization=args.quantization, hardware_id=args.hardware,
            offline_responses=supplied, approved=args.approve_model,
            project_root=args.project_root, brain=brain, seed=args.seed,
        )
    except (ValueError, PermissionError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}), file=sys.stderr)
        return 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
