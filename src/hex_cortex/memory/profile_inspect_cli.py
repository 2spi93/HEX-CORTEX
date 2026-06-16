"""Extended profile inspection entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.cli import inspect_profile
from hex_cortex.memory.confidence_audit_summary import summarize_memory_confidence_audit
from hex_cortex.memory.profile_confidence_plan import profile_memory_confidence_plan


def build_parser() -> argparse.ArgumentParser:
    """Build the extended profile inspection parser."""

    parser = argparse.ArgumentParser(
        prog="profile-inspect-plus",
        description="Inspect a profile with memory confidence candidates.",
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument("--limit", type=int, default=3)
    parser.add_argument("--saturation-threshold", type=float, default=0.7)
    parser.add_argument("--pretty", action="store_true")
    return parser


def inspect_profile_plus(
    profile: Path,
    *,
    limit: int = 3,
    saturation_threshold: float = 0.7,
) -> dict[str, object]:
    """Inspect a profile and include memory confidence planning."""

    payload = inspect_profile(profile)
    payload["memory_confidence_plan"] = profile_memory_confidence_plan(
        profile,
        limit=limit,
        saturation_threshold=saturation_threshold,
    )
    payload["memory_confidence_audit_summary"] = summarize_memory_confidence_audit(
        profile / "memory-confidence-audit.jsonl",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run extended profile inspection."""

    args = build_parser().parse_args(argv)
    payload = inspect_profile_plus(
        args.profile,
        limit=args.limit,
        saturation_threshold=args.saturation_threshold,
    )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
