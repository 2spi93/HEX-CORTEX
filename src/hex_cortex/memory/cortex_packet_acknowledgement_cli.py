from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_packet_acknowledgement import CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME
from hex_cortex.memory.cortex_packet_acknowledgement import REQUIRED_PACKET_ACK
from hex_cortex.memory.cortex_packet_acknowledgement import build_cortex_packet_acknowledgement
from hex_cortex.memory.cortex_packet_acknowledgement import summarize_cortex_packet_acknowledgements


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-packet-acknowledgement")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--ack", default=None)
    parser.add_argument("--show-required", action="store_true")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.show_required:
        payload = {"required_ack": REQUIRED_PACKET_ACK}
    elif args.summary:
        payload = summarize_cortex_packet_acknowledgements(args.profile / CORTEX_PACKET_ACKNOWLEDGEMENT_FILENAME)
    else:
        payload = build_cortex_packet_acknowledgement(args.profile, ack=args.ack)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
