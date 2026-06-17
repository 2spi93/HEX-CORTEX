"""One-shot profile status CLI."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from hex_cortex.memory.construction_freeze_stamp import (
    CONSTRUCTION_FREEZE_STAMP_FILENAME,
    summarize_construction_freeze_stamps,
)
from hex_cortex.memory.construction_status_report import (
    CONSTRUCTION_STATUS_REPORT_FILENAME,
    summarize_construction_status_reports,
)
from hex_cortex.memory.invariant_scanner import scan_profile_invariants
from hex_cortex.memory.manual_review_note import (
    MANUAL_REVIEW_NOTE_FILENAME,
    summarize_manual_review_notes,
)
from hex_cortex.memory.review_export_pack import (
    REVIEW_EXPORT_PACK_FILENAME,
    summarize_review_export_packs,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="profile-full-status")
    parser.add_argument("profile", type=Path)
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    profile = args.profile
    invariant_payload = scan_profile_invariants(profile)
    payload = {
        "profile_path": str(profile),
        "pack": summarize_review_export_packs(profile / REVIEW_EXPORT_PACK_FILENAME),
        "status": summarize_construction_status_reports(
            profile / CONSTRUCTION_STATUS_REPORT_FILENAME
        ),
        "freeze": summarize_construction_freeze_stamps(
            profile / CONSTRUCTION_FREEZE_STAMP_FILENAME
        ),
        "manual_review": summarize_manual_review_notes(
            profile / MANUAL_REVIEW_NOTE_FILENAME
        ),
        "invariants": invariant_payload["scan_record"],
    }
    json.dump(payload, sys.stdout, indent=2 if args.pretty else None, sort_keys=True)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
