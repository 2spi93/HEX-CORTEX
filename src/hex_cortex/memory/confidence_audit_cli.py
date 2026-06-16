"""CLI entrypoint for memory confidence audit summaries."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_audit_summary import summarize_memory_confidence_audit


def build_parser() -> argparse.ArgumentParser:
    """Build the memory confidence audit summary parser."""

    parser = argparse.ArgumentParser(
        prog="memory-confidence-audit-summary",
        description="Summarize memory confidence audit deltas.",
    )
    parser.add_argument("profile", type=Path)
    parser.add_argument("--pretty", action="store_true")
    return parser


def summarize_profile_memory_confidence_audit(profile: Path) -> dict[str, object]:
    """Summarize memory confidence audit records for one profile."""

    return summarize_memory_confidence_audit(
        profile / "memory-confidence-audit.jsonl",
    )


def main(argv: list[str] | None = None) -> int:
    """Run memory confidence audit summary."""

    args = build_parser().parse_args(argv)
    payload = summarize_profile_memory_confidence_audit(args.profile)
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
