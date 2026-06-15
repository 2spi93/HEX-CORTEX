"""Command-line interface for HEX-CORTEX."""

from __future__ import annotations

import argparse
import json
import sys

from hex_cortex.core.cortex_pipeline import CortexPipeline, CortexPipelineResult
from hex_cortex.core.schemas import Task


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
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    return parser


def summarize_result(result: CortexPipelineResult) -> dict[str, object]:
    """Convert a pipeline result into stable CLI JSON."""

    decision = result.routing_decision
    return {
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
    result = CortexPipeline().run(task)
    payload = summarize_result(result)
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
