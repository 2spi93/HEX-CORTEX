"""CLI for skill registry review documents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.skill_registry_review_document import (
    SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME,
    build_skill_registry_review_document,
    summarize_skill_registry_review_documents,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-registry-review")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--summary", action="store_true")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if args.summary:
        payload = summarize_skill_registry_review_documents(
            args.profile / SKILL_REGISTRY_REVIEW_DOCUMENT_FILENAME
        )
    else:
        payload = build_skill_registry_review_document(args.profile)
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
