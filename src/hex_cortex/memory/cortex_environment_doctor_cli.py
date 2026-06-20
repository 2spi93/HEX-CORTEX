from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_environment_doctor import build_environment_doctor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-doctor")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--expected-branch", default="screen-lab-policy-v2")
    parser.add_argument("--collect-tests", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = build_environment_doctor(
        Path(args.project_root),
        expected_branch=args.expected_branch,
        collect_tests=args.collect_tests,
    )
    print(
        json.dumps(
            payload,
            sort_keys=True,
            indent=2 if args.pretty else None,
            separators=None if args.pretty else (",", ":"),
        )
    )
    return 0 if payload.get("status") == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
