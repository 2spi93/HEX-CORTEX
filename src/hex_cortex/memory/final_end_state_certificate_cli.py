"""CLI for final end-state certificates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.final_end_state_certificate import FINAL_END_STATE_CERTIFICATE_FILENAME
from hex_cortex.memory.final_end_state_certificate import build_final_end_state_certificate
from hex_cortex.memory.final_end_state_certificate import summarize_final_end_state_certificates


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="final-end-state-certificate")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        path = args.profile / FINAL_END_STATE_CERTIFICATE_FILENAME
        payload = summarize_final_end_state_certificates(path)
    else:
        payload = build_final_end_state_certificate(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
