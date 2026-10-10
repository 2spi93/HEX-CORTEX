"""Operator-controlled local scientific source audit (no web, no model)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.core.cortex_scientific_knowledge_v16 import (
    EvidenceQuery,
    review_scientific_knowledge,
)
from hex_cortex.core.cortex_scientific_local_sources_v17 import (
    LocalEvidenceRefusal,
    LocalScientificEvidenceVerifier,
    load_local_scientific_manifest,
)
from hex_cortex.core.universal_capabilities_v12 import KnowledgeDomain


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-knowledge")
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--sources-dir", required=True, type=Path)
    parser.add_argument("--claim-id", required=True)
    parser.add_argument("--domain", choices=[value.value for value in KnowledgeDomain],
                        required=True)
    parser.add_argument("--unit", required=True)
    parser.add_argument(
        "--approve-read", action="store_true",
        help="Explicitly authorize read-only access to the selected local science files",
    )
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    if not args.approve_read:
        result = {"status": "blocked", "reason": "local_evidence_read_approval_required",
                  "files_read": False, "model_used": False}
        print(json.dumps(result, sort_keys=True, indent=2 if args.pretty else None))
        return 2
    try:
        query = EvidenceQuery(
            claim_id=args.claim_id, domain=KnowledgeDomain(args.domain),
            result_unit=args.unit,
        )
        records = load_local_scientific_manifest(args.manifest, approved=True)
    except LocalEvidenceRefusal as exc:
        result = {"status": "blocked", "reason": str(exc),
                  "model_used": False, "physical_action_authorized": False}
    except ValueError:
        result = {"status": "blocked", "reason": "local_evidence_query_invalid",
                  "model_used": False, "physical_action_authorized": False}
    else:
        verifier = LocalScientificEvidenceVerifier(
            args.sources_dir, operator_approved=True,
        )
        result = review_scientific_knowledge(
            query, records, operator_approved=True,
            verify_source=verifier.verify_source,
        )
    print(json.dumps(result, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if result.get("status") == "consistent_evidence_not_certified" else 2


if __name__ == "__main__":
    raise SystemExit(main())
