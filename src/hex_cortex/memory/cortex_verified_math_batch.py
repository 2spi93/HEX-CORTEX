"""Bounded CPU-oriented multi-pair experiment over existing ExactMathCell and Harness.

No model is called without explicit user authorization for the *whole* batch.
The cases are public, non-held-out engineering checks: not independent science.
"""
from __future__ import annotations

from collections.abc import Callable
from fractions import Fraction
from math import comb
from pathlib import Path

from hex_cortex.memory.cortex_local_harness_v2 import Task
from hex_cortex.memory.cortex_verified_math_pair import run_verified_math_pair

# Fixed public suite: never label this set held-out or contamination-free.
PUBLIC_MATH_CASES: tuple[tuple[str, str], ...] = (
    ("multiplication", "127*413"),
    ("fraction", "(17*19)/7"),
    ("long_multiplication", "1379*2843"),
    ("combined", "(47*83)-(29*41)"),
    ("integer_division", "(2916/9)+137"),
    ("power", "19**4"),
    ("negative", "(-137*53)+909"),
    ("nested", "((101*103)-(37*41))/3"),
    ("large", "6173*7919"),
    ("rational", "(97/13)+(47/11)"),
)


def _exact_p(better: int, worse: int) -> str | None:
    n = better + worse
    if n == 0:
        return None
    tail = min(2**n, 2 * sum(comb(n, k) for k in range(min(better, worse) + 1)))
    return str(Fraction(tail, 2**n))


def run_verified_math_batch(
    *,
    project_root: Path,
    model_id: str,
    brain: Callable[[str, Task], str],
    max_pairs: int = 3,
    approve_math: bool = False,
    approve_all_model_calls: bool = False,
    reveal_outputs: bool = False,
    max_latency_ms: int = 120_000,
) -> dict[str, object]:
    """Alternating-arm trials, bounded by 10 cases and 20 model calls."""
    if not 1 <= max_pairs <= len(PUBLIC_MATH_CASES):
        raise ValueError("pair_count_out_of_bounds")
    if not model_id.strip():
        raise ValueError("model_id_required")
    if not (approve_math and approve_all_model_calls):
        return {
            "status": "blocked",
            "reason": "batch_math_and_model_approvals_required",
            "model_calls": 0,
            "cases": [],
            "causal_effect_certified": False,
        }

    cases: list[dict[str, object]] = []
    counts = {"baseline": 0, "cortex": 0}
    latencies = {"baseline": 0, "cortex": 0}
    improvement = 0
    regression = 0
    for number, (category, expression) in enumerate(PUBLIC_MATH_CASES[:max_pairs]):
        order = "baseline-first" if number % 2 == 0 else "cortex-first"
        pair = run_verified_math_pair(
            project_root=project_root,
            expression=expression,
            model_id=model_id,
            brain=brain,
            order=order,
            approve_math=True,
            approve_two_model_calls=True,
            max_latency_ms=max_latency_ms,
            reveal_outputs=reveal_outputs,
        )
        if pair["status"] != "paired_observations_recorded":
            return {
                "status": "incomplete",
                "reason": "paired_run_incomplete",
                "requested_pairs": max_pairs,
                "completed_pairs": len(cases),
                "model_calls_attempted": 2 * len(cases) + int(pair.get("model_calls", 0)),
                "cases": cases,
                "causal_effect_certified": False,
            }
        baseline = pair["baseline"]
        cortex = pair["cortex"]
        counts["baseline"] += int(baseline["correct"])
        counts["cortex"] += int(cortex["correct"])
        latencies["baseline"] += int(baseline["latency_ms"])
        latencies["cortex"] += int(cortex["latency_ms"])
        improvement += int(bool(cortex["correct"]) and not baseline["correct"])
        regression += int(bool(baseline["correct"]) and not cortex["correct"])
        cases.append({
            "category": category,
            "expression_sha256": pair["expression_sha256"],
            "arm_order": pair["arm_order"],
            "expected_result": pair["verified_result"] if reveal_outputs else None,
            "baseline": baseline,
            "cortex": cortex,
        })

    return {
        "status": "exploratory_pairs_recorded",
        "experiment_type": "public_suite_exact_calculator_assistance",
        "model_id": model_id,
        "sample_size": len(cases),
        "model_calls_attempted": 2 * len(cases),
        "correct": counts,
        "accuracy": {arm: round(value / len(cases), 6) for arm, value in counts.items()},
        "delta_accuracy": round(
            (counts["cortex"] - counts["baseline"]) / len(cases), 6
        ),
        "cortex_only_correct": improvement,
        "baseline_only_correct": regression,
        "mcnemar_exact_two_sided_p_descriptive_only": _exact_p(improvement, regression),
        "total_latency_ms": latencies,
        "cases": cases,
        "arm_orders_balanced": max_pairs % 2 == 0,
        "held_out_independently_attested": False,
        "model_revision_independently_attested": False,
        "independent_provider_attestation": False,
        "causal_effect_certified": False,
        "general_intelligence_certified": False,
        "memory_uplift_evaluated": False,
        "files_written": False,
        "gpu_required": False,
    }
