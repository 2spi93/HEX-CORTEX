from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_ci_artifact_export import CORTEX_CI_ARTIFACT_EXPORT_FILENAME
from hex_cortex.memory.cortex_ci_artifact_export import build_cortex_ci_artifact_export
from hex_cortex.memory.cortex_ci_artifact_export import summarize_cortex_ci_artifact_export


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-ci-artifact-export")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    output_path = None
    if args.output_dir is not None:
        output_path = args.output_dir / CORTEX_CI_ARTIFACT_EXPORT_FILENAME
    if args.summary:
        payload = summarize_cortex_ci_artifact_export(output_path)
    else:
        payload = build_cortex_ci_artifact_export(args.profile, output_dir=args.output_dir)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
