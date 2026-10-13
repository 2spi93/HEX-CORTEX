"""CLI: real mask predictions to existing deterministic cognitive circuit."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from hex_cortex.memory.cortex_visual_cognitive_circuit_v43 import (
    run_visual_cognitive_circuit_v43,
)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="V43 visual evidence -> router/workspace/clock/spine")
    p.add_argument("--project-root", default=".")
    p.add_argument("--inspection-run", default="latest")
    p.add_argument("--approve-read", action="store_true")
    p.add_argument("--approve-execution", action="store_true")
    p.add_argument("--persist-circuit", action="store_true")
    p.add_argument("--approve-write", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if a.dry_run:
        print(json.dumps({
            "status": "dry_run", "files_read": False, "files_written": False,
            "cognitive_circuit_executed": False, "model_called": False,
        }, sort_keys=True))
        return 0
    try:
        result = run_visual_cognitive_circuit_v43(
            project_root=Path(a.project_root),
            inspection_run=a.inspection_run,
            approved_read=a.approve_read,
            approved_execution=a.approve_execution,
            persist_circuit=a.persist_circuit,
            approved_write=a.approve_write,
        )
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        message = str(exc)
        result = {
            "status": "blocked",
            "reason": message if message.startswith(("v39_", "v41_", "v42_", "v43_"))
            else "v43_runtime_verification_failed",
            "files_written": False, "model_called": False,
        }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] in {
        "visual_cognitive_circuit_verified_in_memory",
        "visual_cognitive_circuit_events_persisted",
        "cognitive_circuit_task_already_recorded",
    } else 2


if __name__ == "__main__":
    raise SystemExit(main())
