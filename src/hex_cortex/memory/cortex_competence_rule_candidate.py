"""Competence-rule candidate builder — residuals into proposed competence.

The residual topology already clusters repeated failures and flags those that
are consolidation-ready (enough recurrences, across distinct contexts and
models, every correction verified, with a causal intervention). Its declared
next action is ``build_skill_candidate``. This module is that step: it turns a
consolidation-ready cluster into a *candidate* competence rule.

Per the safety posture it never installs anything — it emits a proposal receipt
that requires operator approval (autonomy ladder step 5: skill proposal from
evidence; install is a separate human-approved step). The canonical example:
recurring exact-arithmetic errors consolidate into "never accept the LLM's
mental arithmetic on exact-arithmetic tasks; generate and execute a
deterministic program instead".
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_RECEIPT_TYPE = "cortex_competence_rule_candidate_v1"
_REQUIRED_KEYS = (
    "residual_signature",
    "failure_class",
    "domain",
    "occurrence_count",
    "distinct_context_count",
    "distinct_model_count",
    "verified_correction_count",
    "causal_intervention_count",
    "dominant_corrective_intervention",
    "skill_consolidation_ready",
)


def build_competence_rule_candidate(
    cluster: dict[str, object],
    *,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Propose (never install) a competence rule from a residual cluster."""
    if not isinstance(cluster, dict):
        raise ValueError("cluster must be a dict")
    for key in _REQUIRED_KEYS:
        if key not in cluster:
            raise ValueError(f"cluster missing required field: {key}")

    ready = cluster["skill_consolidation_ready"] is True
    intervention = cluster["dominant_corrective_intervention"]
    has_intervention = isinstance(intervention, str) and intervention.strip()

    blockers: list[str] = []
    if not ready:
        blockers.append("cluster_not_consolidation_ready")
    if not has_intervention:
        blockers.append("no_dominant_corrective_intervention")

    failure_class = str(cluster["failure_class"])
    domain = str(cluster["domain"])
    proposed = bool(not blockers)

    receipt = {
        "record_type": _RECEIPT_TYPE,
        "candidate_id": f"crulecand_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "candidate_proposed" if proposed else "insufficient_evidence",
        "source_residual_signature": str(cluster["residual_signature"]),
        "trigger": {"failure_class": failure_class, "domain": domain},
        "prescribed_intervention": str(intervention) if proposed else None,
        "evidence": {
            "occurrence_count": int(cluster["occurrence_count"]),
            "distinct_context_count": int(cluster["distinct_context_count"]),
            "distinct_model_count": int(cluster["distinct_model_count"]),
            "verified_correction_count": int(cluster["verified_correction_count"]),
            "causal_intervention_count": int(cluster["causal_intervention_count"]),
        },
        "requires_operator_approval": True,
        "installed": False,
        "autonomy_ladder_step": 5,
        "raw_reasoning_persisted": False,
        "blockers": blockers,
        "next_action": "operator_review_competence_rule" if proposed else "collect_verified_residuals",
    }
    receipt["candidate_hash"] = _stable_hash(receipt)
    if receipt_path is not None:
        _append_jsonl(receipt_path, receipt)
    return receipt


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
