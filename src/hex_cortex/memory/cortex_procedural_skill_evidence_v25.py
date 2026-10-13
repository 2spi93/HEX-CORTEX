"""Governed evidence sidecar for existing HEX-CORTEX skill library workflow.

This is NOT a competing active skill registry: it is a compact, optional,
append-only review trail. A score or model receipt is NOT external attestation.
An operator's explicit revocation is fail-closed for subsequent proposals.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_durable_jsonl_v7 import (
    atomic_jsonl_snapshot,
    exclusive_jsonl_writer,
)
from hex_cortex.memory.verified_learning_loop import VerifiedLearningLoop

EVIDENCE_FILENAME = "cortex-procedural-transfer-evidence-v25.jsonl"
_FORMAT = "hex_cortex_procedural_skill_evidence_v25"
_ALLOWED = {"multiply_decomposition", "fraction_reduction", "addition_compensation"}


def _source(report: dict[str, object]) -> tuple[str, str, str]:
    if report.get("status") != "procedural_transfer_observations_recorded":
        raise ValueError("skill_evidence_not_completed")
    skill_id = report.get("skill_id")
    model_id = report.get("model_id")
    cases = report.get("cases")
    if skill_id not in _ALLOWED or not isinstance(model_id, str) or not model_id.strip():
        raise ValueError("skill_evidence_bad_identity")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 8:
        raise ValueError("skill_evidence_bad_cases")
    if (
        report.get("evaluated_unseen_expressions") != len(cases)
        or report.get("model_calls") != len(cases) * 2
        or report.get("oracle_answer_given_to_brain") is not False
        or report.get("legacy_skill_activation_performed") is not False
    ):
        raise ValueError("skill_evidence_unverified_contract")
    scores = report.get("scores")
    if not isinstance(scores, dict) or set(scores) != {"baseline", "skill"}:
        raise ValueError("skill_evidence_invalid_scores")
    reconstructed = {"baseline": 0, "skill": 0}
    fingerprints: list[str] = []
    for row in cases:
        if not isinstance(row, dict) or not isinstance(row.get("arms"), dict):
            raise ValueError("skill_evidence_invalid_case")
        if set(row["arms"]) != {"baseline", "skill"}:
            raise ValueError("skill_evidence_invalid_arms")
        digest = row.get("expression_sha256")
        if not isinstance(digest, str) or len(digest) != 64:
            raise ValueError("skill_evidence_invalid_digest")
        fingerprints.append(digest)
        for arm in ("baseline", "skill"):
            arm_row = row["arms"][arm]
            if (
                not isinstance(arm_row, dict)
                or type(arm_row.get("correct")) is not bool
                or not isinstance(arm_row.get("receipt_sha256"), str)
                or len(arm_row["receipt_sha256"]) != 64
            ):
                raise ValueError("skill_evidence_invalid_arm")
            reconstructed[arm] += int(arm_row["correct"])
    if (
        scores != reconstructed
        or len(set(fingerprints)) != len(fingerprints)
        or type(report.get("skill_only_regressions")) is not int
        or type(report.get("skill_only_improvements")) is not int
        or type(report.get("candidate_for_manual_review")) is not bool
    ):
        raise ValueError("skill_evidence_inconsistent_scores")
    return skill_id, model_id, hashlib.sha256(
        json.dumps(
            {"model_id": model_id, "skill_id": skill_id, "cases": [
                {
                    "expression_sha256": row["expression_sha256"],
                    "baseline_receipt": row["arms"]["baseline"]["receipt_sha256"],
                    "skill_receipt": row["arms"]["skill"]["receipt_sha256"],
                    "baseline_correct": row["arms"]["baseline"]["correct"],
                    "skill_correct": row["arms"]["skill"]["correct"],
                } for row in cases
            ]},
            sort_keys=True, separators=(",", ":"),
        ).encode()
    ).hexdigest()


def _target(root: Path) -> Path:
    return VerifiedLearningLoop._target(Path(root), Path(EVIDENCE_FILENAME))


def _read(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    if path.stat().st_size > 1_000_000:
        raise ValueError("skill_evidence_oversize")
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                raise ValueError("skill_evidence_empty_line")
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError("skill_evidence_invalid_json") from exc
            if not isinstance(row, dict) or row.get("format") != _FORMAT:
                raise ValueError("skill_evidence_unrecognized_record")
            records.append(row)
    return records


def assess_skill_evidence(
    *, project_root: Path, skill_id: str,
) -> dict[str, object]:
    """Latest operator revocation dominates and must not auto-clear."""
    if skill_id not in _ALLOWED:
        raise ValueError("skill_evidence_bad_identity")
    records = [r for r in _read(_target(project_root)) if r.get("skill_id") == skill_id]
    if any(row.get("status") == "revoked" for row in records):
        return {"skill_id": skill_id, "status": "revoked", "may_activate": False,
                "receipts": len(records)}
    if any(row.get("status") == "quarantined" for row in records):
        return {"skill_id": skill_id, "status": "quarantined", "may_activate": False,
                "receipts": len(records)}
    if any(row.get("status") == "candidate_for_manual_review" for row in records):
        return {"skill_id": skill_id, "status": "candidate_for_manual_review",
                "may_activate": False, "receipts": len(records)}
    return {"skill_id": skill_id, "status": "collect_more_evidence",
            "may_activate": False, "receipts": len(records)}


def record_skill_trial(
    *, project_root: Path, report: dict[str, object],
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        raise PermissionError("skill_evidence_requires_explicit_approval")
    skill_id, model_id, digest = _source(report)
    path = _target(project_root)
    with exclusive_jsonl_writer(path):
        existing = _read(path)
        if any(r.get("skill_id") == skill_id and r.get("status") == "revoked"
               for r in existing):
            raise PermissionError("skill_revoked_manual_review_required")
        if any(r.get("source_digest") == digest for r in existing):
            return {"status": "duplicate", "skill_id": skill_id, "files_written": False}
        if report["skill_only_regressions"] > 0:
            status = "quarantined"
        elif report["candidate_for_manual_review"]:
            status = "candidate_for_manual_review"
        else:
            status = "collect_more_evidence"
        record = {
            "format": _FORMAT,
            "skill_id": skill_id, "model_id": model_id,
            "source_digest": digest, "status": status,
            "cases": report["evaluated_unseen_expressions"],
            "scores": report["scores"],
            "regressions": report["skill_only_regressions"],
            "improvements": report["skill_only_improvements"],
            "independently_attested": False,
            "automatically_active": False,
        }
        if len(existing) >= 128:
            raise ValueError("skill_evidence_max_records_reached")
        atomic_jsonl_snapshot(
            path, [json.dumps(row, sort_keys=True, separators=(",", ":"))
                   for row in [*existing, record]],
        )
    return {"status": status, "skill_id": skill_id,
            "files_written": True, "automatically_active": False}


def revoke_skill(
    *, project_root: Path, skill_id: str, reason: str,
    approved: bool = False,
) -> dict[str, object]:
    if not approved:
        raise PermissionError("skill_revocation_requires_explicit_approval")
    if skill_id not in _ALLOWED or not reason.strip() or len(reason) > 256:
        raise ValueError("skill_revocation_invalid")
    path = _target(project_root)
    with exclusive_jsonl_writer(path):
        existing = _read(path)
        if any(r.get("skill_id") == skill_id and r.get("status") == "revoked"
               for r in existing):
            return {"status": "revoked", "files_written": False}
        if len(existing) >= 128:
            raise ValueError("skill_evidence_max_records_reached")
        record = {
            "format": _FORMAT, "skill_id": skill_id, "status": "revoked",
            "reason_sha256": hashlib.sha256(reason.encode()).hexdigest(),
            "automatically_active": False,
        }
        atomic_jsonl_snapshot(
            path, [json.dumps(row, sort_keys=True, separators=(",", ":"))
                   for row in [*existing, record]],
        )
    return {"status": "revoked", "files_written": True,
            "automatically_active": False}
