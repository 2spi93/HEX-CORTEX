from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_v13_release_report import CORTEX_V13_RELEASE_REPORT_FILENAME
from hex_cortex.memory.cortex_v13_release_report import build_cortex_v13_release_report
from hex_cortex.memory.cortex_v13_release_report import summarize_cortex_v13_release_reports


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-v13-release-report")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--pytest-summary", default="479 passed")
    parser.add_argument("--tag-name", default="hex-cortex-v1.3-interactive-cockpit")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_v13_release_reports(args.profile / CORTEX_V13_RELEASE_REPORT_FILENAME)
    else:
        payload = build_cortex_v13_release_report(
            args.profile,
            output_path=args.output_path,
            pytest_summary=args.pytest_summary,
            tag_name=args.tag_name,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
