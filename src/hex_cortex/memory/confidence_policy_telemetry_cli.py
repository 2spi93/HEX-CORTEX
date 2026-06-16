"""CLI entrypoint for dry-run confidence policy telemetry."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_policy_telemetry import (
    record_memory_confidence_policy_telemetry_profile,
    summarize_memory_confidence_policy_telemetry,
)


def main(argv: list[str] | None = None) -> int:
    """Record or summarize dry-run policy telemetry."""

    parser = argparse.ArgumentParser(prog="memory-confidence-policy-telemetry")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--max-total-positive-delta", type=float, default=0.1)
    parser.add_argument("--max-total-negative-delta", type=float, default=0.05)
    parser.add_argument("--max-total-operations", type=int, default=5)
    parser.add_argument("--confirmation-delta", type=float, default=0.05)
    parser.add_argument("--saturation-threshold", type=float, default=0.7)
    parser.add_argument("--min-priority-score", type=float, default=0.0)
    parser.add_argument("--recovery-amount", type=float, default=0.02)
    parser.add_argument("--recovery-ceiling", type=float, default=0.7)
    parser.add_argument("--stale-after-days", type=int, default=30)
    parser.add_argument("--decay-amount", type=float, default=0.05)
    parser.add_argument("--minimum-confidence", type=float, default=0.3)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_memory_confidence_policy_telemetry(
            args.profile / "memory-confidence-policy-telemetry.jsonl",
        )
    else:
        payload = record_memory_confidence_policy_telemetry_profile(
            args.profile,
            limit=args.limit,
            max_total_positive_delta=args.max_total_positive_delta,
            max_total_negative_delta=args.max_total_negative_delta,
            max_total_operations=args.max_total_operations,
            confirmation_delta=args.confirmation_delta,
            saturation_threshold=args.saturation_threshold,
            min_priority_score=args.min_priority_score,
            recovery_amount=args.recovery_amount,
            recovery_ceiling=args.recovery_ceiling,
            stale_after_days=args.stale_after_days,
            decay_amount=args.decay_amount,
            minimum_confidence=args.minimum_confidence,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
