"""CLI bridging real GPU metrics to the governor decision.

The PowerShell guard gathers sensors (Ollama /api/ps written to a JSON file,
the dedicated-VRAM counter, utilization) and calls this. We assemble the
snapshot, run the pure governor, and print the decision. The exit code lets the
guard act without parsing: 0 admit/downgrade, 3 queue, 4 defer, 5 reject — and
``recommend_unload_idle`` tells it whether to reclaim VRAM before a crash.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_gpu_governor import decide_gpu_admission
from hex_cortex.memory.cortex_gpu_probe import build_snapshot_from_sources

_EXIT_BY_ACTION = {"admit": 0, "downgrade": 0, "queue": 3, "defer": 4, "reject": 5}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-gpu-probe")
    parser.add_argument("--ollama-ps", default=None, help="path to a saved /api/ps JSON response")
    parser.add_argument("--total-mb", type=float, default=12288.0)
    parser.add_argument("--dedicated-mb", type=float, default=None, help="measured dedicated VRAM usage")
    parser.add_argument("--gpu-util", type=float, default=0.0)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--queue-depth", type=int, default=0)
    parser.add_argument("--oom-count", type=int, default=0)
    parser.add_argument("--in-cooldown", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--tier", choices=("small", "large"), default="small")
    parser.add_argument("--is-benchmark", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        ollama_ps = _load_ps(args.ollama_ps)
        snapshot = build_snapshot_from_sources(
            ollama_ps,
            vram_total_mb=args.total_mb,
            dedicated_usage_mb=args.dedicated_mb,
            gpu_utilization_pct=args.gpu_util,
            temperature_c=args.temperature,
            queue_depth=args.queue_depth,
            recent_oom_count=args.oom_count,
            in_cooldown=args.in_cooldown,
            interactive_task_active=args.interactive,
        )
        decision = decide_gpu_admission(snapshot, {"tier": args.tier, "is_benchmark": args.is_benchmark})
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__, "blockers": [str(exc)]}, indent=2))
        return 2
    payload = {"snapshot": snapshot, "decision": decision}
    print(json.dumps(payload, sort_keys=True, indent=2))
    return _EXIT_BY_ACTION.get(str(decision["action"]), 1)


def _load_ps(path: str | None) -> dict[str, object]:
    if not path:
        return {"models": []}
    # utf-8-sig tolerates the BOM that Windows PowerShell's Out-File writes.
    payload = json.loads(Path(path).resolve().read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("ollama-ps file must contain a JSON object")
    return payload


if __name__ == "__main__":
    raise SystemExit(main())
