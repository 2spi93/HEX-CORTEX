"""Self-consistency verification layer for cognitive brain outputs.

This is the "decuple reasoning" lever: instead of trusting a single sampled
answer from a model, the caller samples a brain N times (or asks N independent
skeptics to refute a claim) and feeds the results here. This module is the
*pure aggregation engine* over those samples — it performs no model call,
no network, and no shell execution. Sampling lives in the caller (autonomy
ladder step 4+); the math and the fail-closed consensus logic live here.

Confidence is reported as the lower bound of the 95% Wilson score interval on
the winning proportion. This matches the risk-aware brain router, which already
selects on a lower confidence bound rather than a raw point estimate: a wide,
small-sample agreement is correctly discounted.

Safety: receipts never persist raw prompts or raw model responses. Only
canonical-cluster *hashes* and counts are written, mirroring the brain
registry's identifier-hashing posture.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_VOTE_RECEIPT_TYPE = "cortex_self_consistency_vote_v1"
_VERIFY_RECEIPT_TYPE = "cortex_adversarial_verification_v1"
_AGGREGATION_MODES = {"text", "numeric"}
_Z_95 = 1.959963984540054  # two-sided 95% normal quantile

# Remove a thousands separator comma only when it sits between digits and is
# followed by exactly three digits (e.g. "1,000" -> "1000"). A decimal comma
# such as "3,14" is left intact so distinct values are never wrongly merged.
_THOUSANDS_COMMA = re.compile(r"(?<=\d),(?=\d{3}(?:\D|$))")
_NUMBER_TOKEN = re.compile(r"-?\d+(?:\.\d+)?")


def aggregate_self_consistency(
    answer_samples: list[str],
    *,
    mode: str = "text",
    agreement_threshold: float = 0.5,
    sample_weights: list[float] | None = None,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Majority-vote over repeated answer samples from a single brain.

    Returns the consensus answer (in-memory only) plus a fail-closed status and
    a Wilson lower-bound confidence. ``answer_samples`` are the already-extracted
    final answers, one per sampled run. With ``mode="numeric"`` light numeric
    canonicalization is applied so "1,000" and "1000" cluster together.

    When ``sample_weights`` is given (one weight per sample, e.g. the producing
    brain's robust reliability) voting is weight-based rather than one-vote-each,
    and the confidence uses the Kish *effective* sample size so that a few
    heavily-weighted samples cannot masquerade as a large agreement. Omitting it
    keeps the plain unweighted behaviour unchanged.
    """
    if not isinstance(answer_samples, list) or not answer_samples:
        raise ValueError("answer_samples must be a non-empty list")
    if not all(isinstance(item, str) for item in answer_samples):
        raise ValueError("answer_samples must all be strings")
    if mode not in _AGGREGATION_MODES:
        raise ValueError("mode must be 'text' or 'numeric'")
    if not 0.0 <= agreement_threshold <= 1.0:
        raise ValueError("agreement_threshold out of range")

    total = len(answer_samples)
    weighted = sample_weights is not None
    weights = _validate_weights(sample_weights, total) if weighted else [1.0] * total

    # Cluster by canonical form, remembering the first original sample per
    # cluster so we can return a human-usable representative answer.
    counts: dict[str, int] = {}
    cluster_weight: dict[str, float] = {}
    representatives: dict[str, str] = {}
    first_seen: dict[str, int] = {}
    for index, sample in enumerate(answer_samples):
        canonical = _canonicalize(sample, mode)
        if canonical not in counts:
            counts[canonical] = 0
            cluster_weight[canonical] = 0.0
            representatives[canonical] = sample.strip()
            first_seen[canonical] = index
        counts[canonical] += 1
        cluster_weight[canonical] += weights[index]

    # Heaviest cluster wins (by weight when weighted, else by count); ties
    # broken by earliest appearance for determinism.
    rank = cluster_weight if weighted else counts
    ordered = sorted(counts, key=lambda c: (-rank[c], first_seen[c]))
    winner_canonical = ordered[0]
    winner_count = counts[winner_canonical]
    winner_rank = rank[winner_canonical]
    runner_up_rank = rank[ordered[1]] if len(ordered) > 1 else 0.0
    is_tie = winner_rank == runner_up_rank

    total_weight = sum(weights)
    agreement_ratio = (winner_rank / total_weight) if weighted else winner_count / total
    effective_n = _effective_sample_size(weights) if weighted else float(total)
    confidence = _wilson_lower(agreement_ratio, effective_n)

    if is_tie:
        status, decision = "no_consensus", "consensus_tied"
    elif agreement_ratio >= agreement_threshold:
        status, decision = "verified", "consensus_reached"
    else:
        status, decision = "no_consensus", "consensus_below_threshold"

    cluster_summary = [
        {
            "cluster_hash": _hash_text(canonical),
            "count": counts[canonical],
            "weight": round(cluster_weight[canonical], 6),
        }
        for canonical in ordered
    ]
    receipt = {
        "record_type": _VOTE_RECEIPT_TYPE,
        "event_id": f"selfconsist_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "mode": mode,
        "weighted": weighted,
        "status": status,
        "decision": decision,
        "sample_count": total,
        "effective_sample_count": round(effective_n, 6),
        "total_weight": round(total_weight, 6),
        "cluster_count": len(counts),
        "winner_cluster_hash": _hash_text(winner_canonical),
        "winner_count": winner_count,
        "agreement_ratio": round(agreement_ratio, 6),
        "confidence_wilson_lower": round(confidence, 6),
        "agreement_threshold": agreement_threshold,
        "tie": is_tie,
        "cluster_summary": cluster_summary,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "next_action": "use_consensus_answer" if status == "verified" else "escalate_or_resample",
    }
    receipt["event_hash"] = _stable_hash(receipt)
    if receipt_path is not None:
        _append_jsonl(receipt_path, receipt)

    result = dict(receipt)
    # Representative answer is returned transiently for the caller to use; it is
    # deliberately absent from the persisted receipt above.
    result["consensus_answer"] = representatives[winner_canonical]
    return result


def aggregate_verification_votes(
    verdicts: list[dict[str, object]],
    *,
    refute_threshold: float = 0.5,
    receipt_path: Path | None = None,
) -> dict[str, object]:
    """Adversarial verification: aggregate independent skeptic verdicts.

    Each verdict is ``{"refuted": bool, "lens": str (optional)}``. A claim
    survives only when the refuting fraction stays *below* ``refute_threshold``
    (default: a simple majority refute kills it). Callers are expected to prompt
    each skeptic to default to ``refuted=True`` when uncertain, so the layer
    fails closed against plausible-but-wrong claims.
    """
    if not isinstance(verdicts, list) or not verdicts:
        raise ValueError("verdicts must be a non-empty list")
    if not 0.0 <= refute_threshold <= 1.0:
        raise ValueError("refute_threshold out of range")
    refuted_flags: list[bool] = []
    lenses: list[str] = []
    for verdict in verdicts:
        if not isinstance(verdict, dict) or "refuted" not in verdict:
            raise ValueError("each verdict must be a dict with a 'refuted' key")
        flag = verdict["refuted"]
        if not isinstance(flag, bool):
            raise ValueError("verdict 'refuted' must be a boolean")
        refuted_flags.append(flag)
        lens = verdict.get("lens")
        lenses.append(str(lens) if isinstance(lens, str) and lens.strip() else "unspecified")

    total = len(refuted_flags)
    refuted_count = sum(1 for flag in refuted_flags if flag)
    survived_count = total - refuted_count
    refuted_ratio = refuted_count / total
    survives = refuted_ratio < refute_threshold
    # Confidence that the surviving verdict is robust: Wilson lower bound on the
    # supporting proportion (survivors when it survives, refuters when it dies).
    supporting = survived_count if survives else refuted_count
    confidence = _wilson_lower_bound(supporting, total)

    receipt = {
        "record_type": _VERIFY_RECEIPT_TYPE,
        "event_id": f"adversarial_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "status": "survived" if survives else "refuted",
        "decision": "claim_survived_verification" if survives else "claim_refuted",
        "verdict_count": total,
        "refuted_count": refuted_count,
        "survived_count": survived_count,
        "refuted_ratio": round(refuted_ratio, 6),
        "refute_threshold": refute_threshold,
        "confidence_wilson_lower": round(confidence, 6),
        "lens_count": len(sorted(set(lenses))),
        "lenses": sorted(set(lenses)),
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "next_action": "accept_claim" if survives else "reject_or_revise_claim",
    }
    receipt["event_hash"] = _stable_hash(receipt)
    if receipt_path is not None:
        _append_jsonl(receipt_path, receipt)
    return receipt


def _canonicalize(answer: str, mode: str) -> str:
    text = " ".join(answer.split()).strip()
    if mode == "numeric":
        cleaned = _THOUSANDS_COMMA.sub("", text).replace("$", "").replace("%", "").strip()
        match = _NUMBER_TOKEN.search(cleaned)
        if match:
            value = float(match.group())
            return str(int(value)) if value == int(value) else repr(value)
    return text.casefold()


def _wilson_lower(phat: float, n: float, z: float = _Z_95) -> float:
    """Lower bound of the Wilson score interval for a proportion ``phat``.

    ``n`` may be a fractional (effective) sample size, so the same formula
    serves both plain counts and reliability-weighted voting.
    """
    if n <= 0.0:
        return 0.0
    denominator = 1.0 + z * z / n
    center = phat + z * z / (2.0 * n)
    margin = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n)
    return max(0.0, (center - margin) / denominator)


def _wilson_lower_bound(successes: int, total: int) -> float:
    return _wilson_lower(successes / total if total else 0.0, float(total))


def _validate_weights(weights: list[float] | None, total: int) -> list[float]:
    if not isinstance(weights, list) or len(weights) != total:
        raise ValueError("sample_weights must be a list with one weight per sample")
    if not all(isinstance(w, int | float) and not isinstance(w, bool) for w in weights):
        raise ValueError("sample_weights must all be numbers")
    converted = [float(w) for w in weights]
    if any(w < 0.0 for w in converted):
        raise ValueError("sample_weights must be non-negative")
    if sum(converted) <= 0.0:
        raise ValueError("sample_weights must not sum to zero")
    return converted


def _effective_sample_size(weights: list[float]) -> float:
    """Kish effective sample size: (sum w)^2 / sum(w^2)."""
    total = sum(weights)
    sum_sq = sum(w * w for w in weights)
    return (total * total / sum_sq) if sum_sq > 0.0 else 0.0


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")
