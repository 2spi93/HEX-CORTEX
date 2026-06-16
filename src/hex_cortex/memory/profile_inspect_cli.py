"""Extended profile inspection entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.cli import inspect_profile
from hex_cortex.memory.confidence_audit_summary import summarize_memory_confidence_audit
from hex_cortex.memory.confidence_policy import run_memory_confidence_policy_profile
from hex_cortex.memory.confidence_policy_telemetry import (
    summarize_memory_confidence_policy_telemetry,
)
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
    parser.add_argument("--policy-limit", type=int, default=5)
    parser.add_argument("--policy-max-total-positive-delta", type=float, default=0.1)
    parser.add_argument("--policy-max-total-negative-delta", type=float, default=0.05)
    parser.add_argument("--policy-max-total-operations", type=int, default=5)
    parser.add_argument("--pretty", action="store_true")
    return parser


def inspect_profile_plus(
    profile: Path,
    *,
    limit: int = 3,
    saturation_threshold: float = 0.7,
    policy_limit: int = 5,
    policy_max_total_positive_delta: float = 0.1,
    policy_max_total_negative_delta: float = 0.05,
    policy_max_total_operations: int = 5,
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
    policy_report = run_memory_confidence_policy_profile(
        profile,
        limit=policy_limit,
        max_total_positive_delta=policy_max_total_positive_delta,
        max_total_negative_delta=policy_max_total_negative_delta,
        max_total_operations=policy_max_total_operations,
        dry_run=True,
    )
    payload["memory_confidence_policy_report"] = {
        "policy_type": policy_report["policy_type"],
        "dry_run": True,
        "applied": False,
        "policy_recommended_actions": policy_report["actions"],
        "policy_skipped_actions": policy_report["skipped_actions"],
        "policy_net_delta": policy_report["net_delta"],
        "selected_action_count": policy_report["selected_action_count"],
        "skipped_action_count": policy_report["skipped_action_count"],
    }
    payload["memory_confidence_policy_telemetry"] = (
        summarize_memory_confidence_policy_telemetry(
            profile / "memory-confidence-policy-telemetry.jsonl",
        )
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    """Run extended profile inspection."""

    args = build_parser().parse_args(argv)
    payload = inspect_profile_plus(
        args.profile,
        limit=args.limit,
        saturation_threshold=args.saturation_threshold,
        policy_limit=args.policy_limit,
        policy_max_total_positive_delta=args.policy_max_total_positive_delta,
        policy_max_total_negative_delta=args.policy_max_total_negative_delta,
        policy_max_total_operations=args.policy_max_total_operations,
    )
    indent = 2 if args.pretty else None
    json.dump(payload, sys.stdout, indent=indent, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
