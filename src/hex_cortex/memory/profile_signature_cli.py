"""CLI for registry review signature packets."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.registry_review_signature_packet import (
    REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME,
    build_registry_review_signature_packet,
    summarize_registry_review_signature_packets,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-signature")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--signer", default="operator_local")
    parser.add_argument("--signature", default="auto")
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_registry_review_signature_packets(
            args.profile / REGISTRY_REVIEW_SIGNATURE_PACKET_FILENAME
        )
    else:
        payload = build_registry_review_signature_packet(
            args.profile,
            signer=args.signer,
            requested_signature=args.signature,
        )
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
