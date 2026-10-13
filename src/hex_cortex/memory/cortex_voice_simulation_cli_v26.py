"""Bounded operator-supplied voice transcript -> virtual object, CPU-only."""
from __future__ import annotations

import argparse
import json
from collections.abc import Sequence

from hex_cortex.memory.cortex_voice_to_simulation_v26 import (
    handle_operator_voice_transcript,
)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Simulate a virtual object from exact allowlisted voice transcripts."
    )
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--device-id", default="virtual_cart")
    parser.add_argument("--approve-transcript", action="store_true")
    parser.add_argument("--approve-simulation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "microphone_accessed": False,
            "files_written": False, "physical_action_executed": False,
        }))
        return 0
    try:
        result = handle_operator_voice_transcript(
            transcript=args.transcript, device_id=args.device_id,
            approved_transcript=args.approve_transcript,
            approved_simulation=args.approve_simulation,
        )
    except (ValueError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "simulation_only" else 2


if __name__ == "__main__":
    raise SystemExit(main())
