from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_evidence_reconciliation import reconcile_evidence_receipts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hexcortex-evidence")
    parser.add_argument("--state-root", default=".hex-cortex")
    parser.add_argument("--output")
    parser.add_argument("--max-files", type=int, default=4096)
    parser.add_argument("--max-bytes", type=int, default=2 * 1024 * 1024)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    payload = reconcile_evidence_receipts(
        state_root=Path(args.state_root),
        output_path=Path(args.output) if args.output else None,
        max_files=args.max_files,
        max_bytes=args.max_bytes,
    )
    print(json.dumps(payload, sort_keys=True, indent=2))
    return 0 if payload.get("status") == "reconciled" else 2


if __name__ == "__main__":
    raise SystemExit(main())
