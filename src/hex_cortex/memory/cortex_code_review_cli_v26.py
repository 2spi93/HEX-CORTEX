"""Operator-gated local AST read and optional CPU Qwen structured code review."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_code_review_bridge_v26 import review_local_code
from hex_cortex.memory.cortex_local_ollama_brain import LocalOllamaBrain
from hex_cortex.memory.cortex_structured_code_plan import code_plan_json_schema


def main(argv: Sequence[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Read-only local code inspection and advisory.")
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--file", type=Path, required=True)
    p.add_argument("--model", default="qwen2.5-coder:7b")
    p.add_argument("--timeout", type=float, default=120)
    p.add_argument("--max-tokens", type=int, default=1536)
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-model", action="store_true")
    p.add_argument("--approve-share-source", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if args.dry_run:
        print(json.dumps({"status": "configuration_only", "files_read": False,
                          "files_written": False, "model_calls": 0,
                          "gpu_requested": False}))
        return 0
    if args.approve_share_source and not args.approve_model:
        p.error("--approve-share-source requires --approve-model")
    try:
        brain = (
            LocalOllamaBrain(
                endpoint="http://127.0.0.1:11434",
                timeout_seconds=args.timeout,
                max_predict_tokens=args.max_tokens, num_gpu=0,
                response_format=code_plan_json_schema(),
            )
            if args.approve_model else None
        )
        result = review_local_code(
            project_root=args.project_root, file_path=args.file,
            model_id=args.model, brain=brain,
            approve_read=args.approve_read,
            approve_model=args.approve_model,
            approve_share_source=args.approve_share_source,
        )
    except (OSError, ValueError, PermissionError, UnicodeError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] in {"static_inspection", "reviewed"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
