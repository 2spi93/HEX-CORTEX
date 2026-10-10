"""V21: fair, paired, provider-agnostic model amplification evidence.

No model calls, network, arbitrary execution, real hardware or fake uplift.
This module scores operator-supplied paired model outputs using fixed,
read-only oracles. Synthetic fixtures can test scorer wiring but never
be labeled as measured model amplification.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from enum import StrEnum
from fractions import Fraction
from math import comb
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from hex_cortex.core.cortex_exact_math_v13 import calculate_exact

MAX_PAIRS = 512


class ScoreMode(StrEnum):
    RATIONAL = "rational"
    EXACT_TEXT = "exact_text"
    ABSTAIN = "abstain"


class ScienceEvalItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str = Field(min_length=2, max_length=96)
    domain: Literal["mathematics", "physics", "chemistry", "cross_domain"]
    task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    expected: str = Field(min_length=1, max_length=256)
    score_mode: ScoreMode
    split: Literal["held_out"] = "held_out"

    @model_validator(mode="after")
    def valid_expected(self) -> ScienceEvalItem:
        if self.score_mode == ScoreMode.RATIONAL:
            if _fraction(self.expected) is None:
                raise ValueError("bench_expected_not_rational")
        if self.score_mode == ScoreMode.ABSTAIN and self.expected != "indeterminate":
            raise ValueError("bench_expected_abstention_invalid")
        return self


class ModelObservation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    task_id: str = Field(min_length=2, max_length=96)
    arm: Literal["baseline", "cortex"]
    provider: str = Field(min_length=2, max_length=64)
    model_id: str = Field(min_length=2, max_length=128)
    model_revision: str = Field(min_length=1, max_length=128)
    task_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    settings_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    response: str = Field(max_length=4096)
    latency_ms: int = Field(ge=0, le=86_400_000)
    billed_input_tokens: int = Field(ge=0, le=10_000_000)
    billed_output_tokens: int = Field(ge=0, le=10_000_000)
    billed_cost_microusd: int = Field(ge=0, le=100_000_000_000)
    capture_kind: Literal["synthetic_fixture", "operator_supplied"]
    receipt_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class PairedEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    protocol_version: Literal["hex_cortex_v21_paired_science_v1"]
    dataset_id: str = Field(min_length=2, max_length=128)
    dataset_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    items: list[ScienceEvalItem] = Field(min_length=1, max_length=MAX_PAIRS)
    observations: list[ModelObservation] = Field(min_length=2, max_length=MAX_PAIRS * 2)

    @model_validator(mode="after")
    def assert_paired_fairness(self) -> PairedEvaluation:
        if len({i.task_id for i in self.items}) != len(self.items):
            raise ValueError("bench_duplicate_task")
        expected = {(i.task_id, arm) for i in self.items for arm in ("baseline", "cortex")}
        actual = {(r.task_id, r.arm) for r in self.observations}
        if len(actual) != len(self.observations) or expected != actual:
            raise ValueError("bench_missing_or_duplicate_arm")
        indexed = {(r.task_id, r.arm): r for r in self.observations}
        for item in self.items:
            baseline = indexed[(item.task_id, "baseline")]
            cortex = indexed[(item.task_id, "cortex")]
            if baseline.task_sha256 != item.task_sha256 or cortex.task_sha256 != item.task_sha256:
                raise ValueError("bench_task_input_hash_mismatch")
            if (
                baseline.provider, baseline.model_id, baseline.model_revision,
                baseline.settings_sha256, baseline.capture_kind,
            ) != (
                cortex.provider, cortex.model_id, cortex.model_revision,
                cortex.settings_sha256, cortex.capture_kind,
            ):
                raise ValueError("bench_model_configuration_mismatch")
        # Dataset fingerprint is an operator assertion; hashes cannot
        # independently prove a held-out split or the provenance of calls.
        return self


def _fraction(value: str) -> Fraction | None:
    result = calculate_exact(value, approved=True)
    if result.get("status") != "verified_exact_arithmetic":
        return None
    return Fraction(int(result["numerator"]), int(result["denominator"]))


def _correct(item: ScienceEvalItem, answer: str) -> bool:
    if item.score_mode == ScoreMode.RATIONAL:
        a = _fraction(answer)
        return a is not None and a == _fraction(item.expected)
    if item.score_mode == ScoreMode.ABSTAIN:
        return answer.strip().lower() == "indeterminate"
    return answer.strip() == item.expected


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    ).hexdigest()


def _mcnemar_two_sided(better: int, worse: int) -> str | None:
    """Exact conditional binomial p-value on discordant matched pairs.

    This is a descriptive evidence aid, NOT experimental randomization,
    a proof of causality or a guarantee of independence.
    """
    n = better + worse
    if not n:
        return None
    tail = 2 * sum(comb(n, k) for k in range(min(better, worse) + 1))
    numerator = min(tail, 2**n)
    return str(Fraction(numerator, 2**n))


def evaluate_paired_model_amplification(
    evaluation: PairedEvaluation,
    *,
    operator_approved: bool = False,
) -> dict[str, object]:
    """Score all paired outputs without generating any model response."""
    if not operator_approved:
        return {
            "status": "blocked",
            "reason": "bench_operator_approval_required",
            "model_called": False,
            "input_read": False,
            "physical_action_authorized": False,
        }
    lookup = {(r.task_id, r.arm): r for r in evaluation.observations}
    domain_stats: dict[str, Counter[str]] = {}
    totals: Counter[str] = Counter()
    total_latency = {"baseline": 0, "cortex": 0}
    total_cost = {"baseline": 0, "cortex": 0}
    total_tokens = {"baseline": 0, "cortex": 0}
    for item in evaluation.items:
        a, b = (lookup[(item.task_id, arm)] for arm in ("baseline", "cortex"))
        a_ok = _correct(item, a.response)
        b_ok = _correct(item, b.response)
        counts = domain_stats.setdefault(item.domain, Counter())
        counts["pairs"] += 1
        counts["baseline_correct"] += int(a_ok)
        counts["cortex_correct"] += int(b_ok)
        totals["pairs"] += 1
        totals["baseline_correct"] += int(a_ok)
        totals["cortex_correct"] += int(b_ok)
        totals["cortex_only_correct"] += int(b_ok and not a_ok)
        totals["baseline_only_correct"] += int(a_ok and not b_ok)
        for arm, record in (("baseline", a), ("cortex", b)):
            total_latency[arm] += record.latency_ms
            total_cost[arm] += record.billed_cost_microusd
            total_tokens[arm] += record.billed_input_tokens + record.billed_output_tokens

    synthetic = any(r.capture_kind == "synthetic_fixture" for r in evaluation.observations)
    measured = not synthetic
    report = {
        "report_type": "hex_cortex_paired_science_evaluation_v21",
        "status": "scored",
        "dataset_id": evaluation.dataset_id,
        "dataset_sha256": evaluation.dataset_sha256,
        "dataset_held_out_independently_attested": False,
        "model_outputs_captured_by_this_command": False,
        "model_called": False,
        "capture_mode": "synthetic_fixture" if synthetic else "operator_supplied_unattested",
        "real_model_amplification_measured": measured,
        "real_model_calls_independently_attested": False,
        "evidence_is_external_and_unverified": measured,
        "sample_size": totals["pairs"],
        "baseline_correct": totals["baseline_correct"],
        "cortex_correct": totals["cortex_correct"],
        "cortex_only_correct": totals["cortex_only_correct"],
        "baseline_only_correct": totals["baseline_only_correct"],
        "delta_correct": totals["cortex_correct"] - totals["baseline_correct"],
        "baseline_accuracy": str(Fraction(totals["baseline_correct"], totals["pairs"])),
        "cortex_accuracy": str(Fraction(totals["cortex_correct"], totals["pairs"])),
        "delta_accuracy": str(
            Fraction(totals["cortex_correct"] - totals["baseline_correct"], totals["pairs"])
        ),
        "mcnemar_exact_two_sided_p": _mcnemar_two_sided(
            totals["cortex_only_correct"], totals["baseline_only_correct"],
        ),
        "totals": {
            arm: {
                "latency_ms": total_latency[arm],
                "tokens": total_tokens[arm],
                "cost_microusd": total_cost[arm],
            } for arm in ("baseline", "cortex")
        },
        "domains": {
            domain: dict(sorted(counts.items()))
            for domain, counts in sorted(domain_stats.items())
        },
        "causal_effect_certified": False,
        "general_intelligence_certified": False,
        "physical_action_authorized": False,
        "provider_access_required": False,
        "checkout_modified": False,
    }
    # Do not surface synthetic-fake positive gains as a 'measured model gain'.
    if synthetic:
        report["real_model_amplification_measured"] = False
    report["report_sha256"] = _digest(report)
    return report
