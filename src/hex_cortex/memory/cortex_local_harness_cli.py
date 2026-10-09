"""Local read-only Harness V2 operator CLI."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import Task, build_readonly_harness


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-harness")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--session", default="local")
    parser.add_argument("--task-id", default="inspect-local-checkout")
    parser.add_argument("--approve-read", action="store_true")
    args = parser.parse_args(argv)
    try:
        harness = build_readonly_harness(args.project_root, session_id=args.session)
        result = harness.execute(
            Task(args.task_id, "repo_read", "Inspect the local checkout", "repo_manifest"),
            approved=args.approve_read,
        )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "complete" else 2


if __name__ == "__main__":
    raise SystemExit(main())
