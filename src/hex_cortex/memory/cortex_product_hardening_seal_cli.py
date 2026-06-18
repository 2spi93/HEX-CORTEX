from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_product_hardening_seal import CORTEX_PRODUCT_HARDENING_SEAL_FILENAME
from hex_cortex.memory.cortex_product_hardening_seal import build_cortex_product_hardening_seal
from hex_cortex.memory.cortex_product_hardening_seal import summarize_cortex_product_hardening_seals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-product-hardening-seal")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_product_hardening_seals(args.profile / CORTEX_PRODUCT_HARDENING_SEAL_FILENAME)
    else:
        payload = build_cortex_product_hardening_seal(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
