"""Model auto-benchmark — measure every model before trusting it.

Routing decisions must rest on measured capability, not model-card marketing.
This module defines a deterministic benchmark suite whose answers are
verifiable without any judge model (exact values, contained tokens, JSON
fields), and scores a model's responses into a per-domain fingerprint record
the bandit router can use as a prior.

Pure and cold: the suite is data, the scorer is arithmetic. A runtime sends
the prompts to a model and brings the responses back here for scoring.
"""

from __future__ import annotations

import json
import re

_SUITE_TYPE = "cortex_benchmark_suite_v1"
_REPORT_TYPE = "cortex_benchmark_report_v1"

BENCHMARK_TASKS: tuple[dict[str, object], ...] = (
    {
        "task_id": "code_trace_len",
        "domain": "coding",
        "prompt": "What does this Python print? print(len('hexcortex')) Answer with the number only.",
        "check": {"kind": "numeric", "expected": 9.0},
    },
    {
        "task_id": "code_trace_slice",
        "domain": "coding",
        "prompt": "What does this Python print? print('cortex'[::-1]) Answer with the output only.",
        "check": {"kind": "contains", "expected": "xetroc"},
    },
    {
        "task_id": "code_trace_sort",
        "domain": "coding",
        "prompt": "What does this Python print? print(sorted([3, 1, 2])[0] + max(4, 7)) Answer with the number only.",
        "check": {"kind": "numeric", "expected": 8.0},
    },
    {
        "task_id": "code_bug_line",
        "domain": "coding",
        "prompt": (
            "Line 1: def mean(xs):\n"
            "Line 2:     total = sum(xs)\n"
            "Line 3:     return total / len(xs) + 1\n"
            "One line makes mean() wrong. Answer with the line number only."
        ),
        "check": {"kind": "numeric", "expected": 3.0},
    },
    {
        "task_id": "math_product",
        "domain": "math",
        "prompt": "Compute 17 * 23. Answer with the number only.",
        "check": {"kind": "numeric", "expected": 391.0},
    },
    {
        "task_id": "math_gcd",
        "domain": "math",
        "prompt": "What is the greatest common divisor of 48 and 36? Answer with the number only.",
        "check": {"kind": "numeric", "expected": 12.0},
    },
    {
        "task_id": "math_percent",
        "domain": "math",
        "prompt": "What is 15% of 240? Answer with the number only.",
        "check": {"kind": "numeric", "expected": 36.0},
    },
    {
        "task_id": "french_plural",
        "domain": "french",
        "prompt": "Quel est le pluriel du mot français « cheval » ? Réponds avec le mot seul.",
        "check": {"kind": "contains", "expected": "chevaux"},
    },
    {
        "task_id": "french_grammar",
        "domain": "french",
        "prompt": "Complète correctement : « Les receipts que j'ai ______ » (verbe écrire). Réponds avec le participe seul.",
        "check": {"kind": "contains", "expected": "écrits"},
    },
    {
        "task_id": "json_answer_int",
        "domain": "json_compliance",
        "prompt": 'Answer strictly with JSON of the form {"answer": <integer>}: what is 2 + 2?',
        "check": {"kind": "json_field_numeric", "field": "answer", "expected": 4.0},
    },
    {
        "task_id": "json_answer_list",
        "domain": "json_compliance",
        "prompt": 'Answer strictly with JSON of the form {"primes": [<integers>]}: list the prime numbers below 10 in ascending order.',
        "check": {"kind": "json_field_equals", "field": "primes", "expected": [2, 3, 5, 7]},
    },
    {
        "task_id": "instruction_exact_word",
        "domain": "instruction",
        "prompt": "Reply with exactly the single word OUI and nothing else.",
        "check": {"kind": "exact", "expected": "OUI"},
    },
    {
        "task_id": "instruction_no_extra",
        "domain": "instruction",
        "prompt": "Reply with exactly: DONE-42",
        "check": {"kind": "exact", "expected": "DONE-42"},
    },
)

_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def build_benchmark_suite() -> dict[str, object]:
    """Return the suite a runtime should send to the model under test."""

    return {
        "suite_type": _SUITE_TYPE,
        "task_count": len(BENCHMARK_TASKS),
        "domains": sorted({str(task["domain"]) for task in BENCHMARK_TASKS}),
        "tasks": [
            {"task_id": task["task_id"], "domain": task["domain"], "prompt": task["prompt"]}
            for task in BENCHMARK_TASKS
        ],
        "scoring": "deterministic_local_checks",
        "recommended_options": {"temperature": 0.0},
        "model_call_performed": False,
        "next_action": "collect_responses_then_score",
    }


def _extract_last_number(text: str) -> float | None:
    matches = _NUMBER_RE.findall(text)
    if not matches:
        return None
    return float(matches[-1].replace(",", "."))


def _extract_json(text: str) -> dict[str, object] | None:
    stripped = text.strip()
    candidates = [stripped]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start != -1 and end > start:
        candidates.append(stripped[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    return None


def _check_response(check: dict[str, object], response: str) -> bool:
    kind = check["kind"]
    if kind == "exact":
        return response.strip() == check["expected"]
    if kind == "contains":
        return str(check["expected"]).lower() in response.lower()
    if kind == "numeric":
        return _extract_last_number(response) == check["expected"]
    if kind == "json_field_numeric":
        parsed = _extract_json(response)
        if parsed is None:
            return False
        value = parsed.get(str(check["field"]))
        return isinstance(value, (int, float)) and float(value) == check["expected"]
    if kind == "json_field_equals":
        parsed = _extract_json(response)
        if parsed is None:
            return False
        return parsed.get(str(check["field"])) == check["expected"]
    raise ValueError(f"unknown check kind: {kind}")


def score_benchmark_responses(
    *,
    model_id: str,
    responses: dict[str, str],
) -> dict[str, object]:
    """Score collected responses into a per-domain capability fingerprint.

    Unanswered tasks count as failures: a model that cannot answer is a model
    that cannot be trusted with the domain.
    """

    if not model_id.strip():
        raise ValueError("model_id must not be empty")
    known_ids = {str(task["task_id"]) for task in BENCHMARK_TASKS}
    unknown = sorted(set(responses) - known_ids)
    if unknown:
        raise ValueError(f"unknown task ids: {', '.join(unknown)}")

    per_task = []
    domain_totals: dict[str, list[int]] = {}
    for task in BENCHMARK_TASKS:
        task_id = str(task["task_id"])
        domain = str(task["domain"])
        response = responses.get(task_id)
        passed = response is not None and _check_response(dict(task["check"]), str(response))
        per_task.append({"task_id": task_id, "domain": domain, "passed": passed, "answered": response is not None})
        domain_totals.setdefault(domain, [0, 0])
        domain_totals[domain][0] += 1 if passed else 0
        domain_totals[domain][1] += 1

    domain_scores = {
        domain: round(passed_count / total, 10)
        for domain, (passed_count, total) in sorted(domain_totals.items())
    }
    overall = round(sum(row["passed"] for row in per_task) / len(per_task), 10)

    return {
        "report_type": _REPORT_TYPE,
        "model_id": model_id,
        "task_results": per_task,
        "domain_scores": domain_scores,
        "overall_score": overall,
        "answered_count": sum(1 for row in per_task if row["answered"]),
        "task_count": len(per_task),
        "usable_as_routing_prior": True,
        "model_call_performed": False,
        "next_action": "register_fingerprint_and_seed_router_prior",
    }
