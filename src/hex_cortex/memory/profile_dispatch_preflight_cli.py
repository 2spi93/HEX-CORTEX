"""CLI for inspecting profile dispatch preflight status."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.profile_dispatch_safety import inspect_profile_dispatch_safety
from hex_cortex.memory.profile_next_action import inspect_profile_next_action


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-dispatch-preflight")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--policy-limit", type=int, default=6)
    parser.add_argument("--policy-stability-window", type=int, default=3)
    parser.add_argument("--minimum-ready-score", type=float, default=1.0)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    next_payload = inspect_profile_next_action(
        args.profile,
        policy_limit=args.policy_limit,
        policy_stability_window=args.policy_stability_window,
        minimum_ready_score=args.minimum_ready_score,
    )
    safety_payload = inspect_profile_dispatch_safety(args.profile, next_payload)
    payload = {
        "inspect_type": "profile_dispatch_preflight",
        "profile_path": str(args.profile),
        "status": next_payload["status"],
        "decision": next_payload["decision"],
        "next_action": next_payload["next_action"],
        "safety_status": safety_payload["safety_status"],
        "allowed": safety_payload["allowed"],
        "safety_reasons": safety_payload["safety_reasons"],
    }
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
