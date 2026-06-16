"""CLI entrypoint for memory confidence policy autosaturation marker."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.confidence_policy_autosaturation import (
    load_memory_confidence_policy_stability_marker,
    run_memory_confidence_policy_autosaturation_profile,
)


def main(argv: list[str] | None = None) -> int:
    """Preview, write, or inspect the confidence policy stability marker."""

    parser = argparse.ArgumentParser(prog="memory-confidence-policy-autosaturation")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--stability-window", type=int, default=3)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--inspect-marker", action="store_true")
    parser.add_argument("--keep-stale-marker", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.inspect_marker:
        payload = load_memory_confidence_policy_stability_marker(args.profile)
    else:
        payload = run_memory_confidence_policy_autosaturation_profile(
            args.profile,
            stability_window=args.stability_window,
            dry_run=not args.apply,
            clear_stale_marker=not args.keep_stale_marker,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
