"""Command-line interface for HEX-CORTEX."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.core.cortex_pipeline import CortexPipeline, CortexPipelineResult
from hex_cortex.core.schemas import Task
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore
from hex_cortex.memory.schemas import MemoryRecord
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def build_parser() -> argparse.ArgumentParser:
    """Build the HEX-CORTEX CLI parser."""

    parser = argparse.ArgumentParser(
        prog="hex-cortex",
        description="Run one local HEX-CORTEX pipeline pass.",
    )
    parser.add_argument("content", help="Task content to send into HEX-CORTEX.")
    parser.add_argument(
        "--domain",
        action="append",
        default=[],
        dest="domains",
        help="Domain hint. Can be passed multiple times.",
    )
    parser.add_argument("--novelty", type=float, default=0.5)
    parser.add_argument("--risk", type=float, default=0.5)
    parser.add_argument("--uncertainty", type=float, default=0.5)
    parser.add_argument("--latency-budget-ms", type=int, default=2_000)
    parser.add_argument(
        "--spine-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL path used to load and persist canonical spine events.",
    )
    parser.add_argument(
        "--memory-jsonl",
        type=Path,
        default=None,
        help="Optional JSONL path used to append consolidated memory records.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def summarize_result(
    result: CortexPipelineResult,
    *,
    persisted_event_count: int | None = None,
    persisted_memory_count: int | None = None,
) -> dict[str, object]:
    """Convert a pipeline result into stable CLI JSON."""

    decision = result.routing_decision
    payload: dict[str, object] = {
        "task_id": result.task_id,
        "mode": decision.mode.value,
        "selected_cells": decision.selected_cells,
        "retrieval_method": result.context_packet.method.value,
        "retrieval_result_count": len(result.context_packet.results),
        "matched_skill_count": len(result.matched_skills),
        "replay_status": result.replay_report.status.value,
        "pruning_decisions": len(result.pruning_report.decisions),
        "clock_completed": result.clock_completed,
    }
    if persisted_event_count is not None:
        payload["persisted_event_count"] = persisted_event_count
    if persisted_memory_count is not None:
        payload["persisted_memory_count"] = persisted_memory_count
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return a process-style exit code."""

    args = build_parser().parse_args(argv)
    task = Task(
        content=args.content,
        domain_hints=args.domains,
        novelty=args.novelty,
        risk=args.risk,
        uncertainty=args.uncertainty,
        latency_budget_ms=args.latency_budget_ms,
    )

    spine = _load_spine(args.spine_jsonl)
    result = CortexPipeline(spine=spine).run(task)
    persisted_event_count = _save_spine(args.spine_jsonl, spine)
    persisted_memory_count = _save_memory(
        args.memory_jsonl,
        result.replay_report.memory,
    )
    payload = summarize_result(
        result,
        persisted_event_count=persisted_event_count,
        persisted_memory_count=persisted_memory_count,
    )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _load_spine(path: Path | None) -> CanonicalSpine:
    if path is None:
        return CanonicalSpine()
    return CanonicalSpineJsonlStore(path).load()


def _save_spine(path: Path | None, spine: CanonicalSpine) -> int | None:
    if path is None:
        return None
    return CanonicalSpineJsonlStore(path).save(spine)


def _save_memory(path: Path | None, memory: MemoryRecord | None) -> int | None:
    if path is None:
        return None
    if memory is None:
        return len(LocalMemoryJsonlStore(path).load())
    return LocalMemoryJsonlStore(path).append(memory)


if __name__ == "__main__":
    raise SystemExit(main())
