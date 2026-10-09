"""Local A2A JSONL operator entry point; reads stdin, writes stdout, no sockets."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_a2a_local import run_local_a2a_jsonl


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-a2a-local")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument(
        "--approve-read", action="store_true",
        help="explicitly allow the local read-only repository inventory tool",
    )
    args = parser.parse_args(argv)
    try:
        result = run_local_a2a_jsonl(
            sys.stdin.read(),
            root=args.project_root.resolve(),
            allow_read_repo=args.approve_read,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    sys.stdout.write(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
