"""Small entrypoint for planning memory confidence confirmations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence import MemoryConfidencePlanner
from hex_cortex.memory.jsonl_store import LocalMemoryJsonlStore


def build_parser() -> argparse.ArgumentParser:
    """Build the memory confidence plan parser."""

    parser = argparse.ArgumentParser(
        prog="memory-confidence-plan",
        description="Plan non-mutating memory confidence confirmations.",
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    return parser


def plan_memory_confidence_profile(profile: Path, *, limit: int) -> dict[str, object]:
    """Plan memory confidence confirmations for one profile."""

    memory_path = profile / "memory.jsonl"
    memories = LocalMemoryJsonlStore(memory_path).load()
    plan = MemoryConfidencePlanner().plan(memories, limit=limit)
    return {
        "plan_type": "memory_confidence_profile",
        "profile_path": str(profile),
        "memory_path": str(memory_path),
        "limit": limit,
        "total_memory_count": plan.total_memory_count,
        "candidate_count": plan.candidate_count,
        "candidates": [
            candidate.model_dump(mode="json") for candidate in plan.candidates
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """Run the memory confidence planner."""

    args = build_parser().parse_args(argv)
    payload = plan_memory_confidence_profile(args.profile, limit=args.limit)
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
