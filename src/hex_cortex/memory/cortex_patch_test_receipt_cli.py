from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_patch_test_receipt import CORTEX_PATCH_TEST_RECEIPT_FILENAME
from hex_cortex.memory.cortex_patch_test_receipt import build_cortex_patch_test_receipt
from hex_cortex.memory.cortex_patch_test_receipt import summarize_cortex_patch_test_receipts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-patch-test-receipt")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--status", choices=["passed", "failed"], default="passed")
    parser.add_argument("--pytest-summary", default="pytest passed")
    parser.add_argument("--passed-count", type=int, default=0)
    parser.add_argument("--source-artifact-hash")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_patch_test_receipts(args.profile / CORTEX_PATCH_TEST_RECEIPT_FILENAME)
    else:
        payload = build_cortex_patch_test_receipt(
            args.profile,
            test_status=args.status,
            pytest_summary=args.pytest_summary,
            passed_count=args.passed_count,
            source_artifact_hash=args.source_artifact_hash,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
