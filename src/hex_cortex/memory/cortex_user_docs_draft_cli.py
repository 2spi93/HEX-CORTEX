from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.cortex_user_docs_draft import CORTEX_USER_DOCS_DRAFT_FILENAME
from hex_cortex.memory.cortex_user_docs_draft import build_cortex_user_docs_draft
from hex_cortex.memory.cortex_user_docs_draft import summarize_cortex_user_docs_drafts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="cortex-user-docs-draft")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_cortex_user_docs_drafts(args.profile / CORTEX_USER_DOCS_DRAFT_FILENAME)
    else:
        payload = build_cortex_user_docs_draft(args.profile, output_path=args.output_path)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
