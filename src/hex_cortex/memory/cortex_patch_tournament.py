"""Patch tournament — rank candidate patches by external verifier truth.

Real power comes from independent verifiable truth, not from "thinking longer".
A coding rail should generate several candidate patches and let external
verifiers decide between them: compile, tests, lint, types, adversarial review,
regression count. This module is the pure scoring + selection core. It does not
run anything — the runtime (autonomy step 4+) runs the verifiers and passes the
collected outcomes here, exactly as the self-consistency layer aggregates
already-sampled answers.

A patch is only *eligible* if it passes a hard correctness gate: every test
green, zero regressions, not refuted by adversarial review. Among eligible
patches, quality and compactness break ties. If none is eligible the tournament
fails closed — propose nothing, regenerate or escalate. Receipts store a patch
id and a diff hash, never the raw diff (operator code stays out of the ledger).
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_RECEIPT_TYPE = "cortex_patch_tournament_v1"


def rank_patch_candidates(
    candidates: list[dict[str, object]],
    *,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Score candidate patches and pick the best eligible one (fail-closed)."""
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates must be a non-empty list")

    scored = [_score(_validate(candidate)) for candidate in candidates]
    # Eligible first, then by quality score, then smaller diff, then id.
    scored.sort(
        key=lambda c: (
            not c["eligible"],
            -float(c["score"]),
            int(c["diff_size_lines"]),
            str(c["patch_id"]),
        )
    )
    winner = scored[0] if scored[0]["eligible"] else None
    status = "ready" if winner else "blocked"
    blockers = [] if winner else ["no_patch_passed_correctness_gate"]

    receipt = {
        "record_type": _RECEIPT_TYPE,
        "event_id": f"patchtourney_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "candidate_count": len(scored),
        "eligible_count": sum(1 for c in scored if c["eligible"]),
        "winner_patch_id": winner["patch_id"] if winner else None,
        "winner_score": winner["score"] if winner else None,
        "ranked": [
            {
                "patch_id": c["patch_id"],
                "diff_hash": c["diff_hash"],
                "eligible": c["eligible"],
                "score": c["score"],
                "failed_gates": c["failed_gates"],
            }
            for c in scored
        ],
        "raw_diff_persisted": False,
        "blockers": blockers,
        "next_action": "propose_patch_to_operator" if winner else "regenerate_or_escalate",
    }
    receipt["event_hash"] = _stable_hash(receipt)
    if receipt_path is not None:
        _append_jsonl(receipt_path, receipt)
    return receipt


def _validate(candidate: dict[str, object]) -> dict[str, object]:
    if not isinstance(candidate, dict):
        raise ValueError("each candidate must be a dict")
    patch_id = candidate.get("patch_id")
    if not isinstance(patch_id, str) or not patch_id.strip():
        raise ValueError("candidate patch_id must be a non-empty string")
    tests_total = _nonneg_int(candidate, "tests_total")
    tests_passed = _nonneg_int(candidate, "tests_passed")
    if tests_passed > tests_total:
        raise ValueError("tests_passed cannot exceed tests_total")
    return {
        "patch_id": patch_id,
        "tests_total": tests_total,
        "tests_passed": tests_passed,
        "regressions": _nonneg_int(candidate, "regressions", default=0),
        "lint_clean": bool(candidate.get("lint_clean", False)),
        "types_clean": bool(candidate.get("types_clean", False)),
        "adversarial_refuted": bool(candidate.get("adversarial_refuted", False)),
        "diff_size_lines": _nonneg_int(candidate, "diff_size_lines", default=0),
        "diff_hash": _diff_hash(candidate),
    }


def _score(candidate: dict[str, object]) -> dict[str, object]:
    tests_total = int(candidate["tests_total"])
    tests_passed = int(candidate["tests_passed"])
    regressions = int(candidate["regressions"])
    pass_ratio = tests_passed / tests_total if tests_total > 0 else 0.0

    failed_gates: list[str] = []
    if tests_total == 0 or tests_passed < tests_total:
        failed_gates.append("tests_not_all_green")
    if regressions > 0:
        failed_gates.append("introduces_regressions")
    if candidate["adversarial_refuted"]:
        failed_gates.append("adversarial_refuted")
    eligible = not failed_gates

    compactness = 1.0 / (1.0 + int(candidate["diff_size_lines"]) / 100.0)
    quality = (
        0.60 * pass_ratio
        + 0.15 * (1.0 if candidate["lint_clean"] else 0.0)
        + 0.15 * (1.0 if candidate["types_clean"] else 0.0)
        + 0.10 * compactness
    )
    candidate["eligible"] = eligible
    candidate["failed_gates"] = failed_gates
    candidate["score"] = round(quality, 6)
    return candidate


def _diff_hash(candidate: dict[str, object]) -> str:
    raw = candidate.get("diff")
    if isinstance(raw, str) and raw:
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
    provided = candidate.get("diff_hash")
    return str(provided) if isinstance(provided, str) and provided else ""


def _nonneg_int(source: dict[str, object], key: str, *, default: int | None = None) -> int:
    if key not in source:
        if default is None:
            raise ValueError(f"candidate missing required field: {key}")
        return default
    value = source[key]
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"candidate field {key} must be a non-negative integer")
    return value


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
