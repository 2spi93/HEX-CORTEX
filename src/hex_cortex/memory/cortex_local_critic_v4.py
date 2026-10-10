"""Local Critic V4: independent static and opt-in isolated runtime verdicts.

The critic cannot grant repository write permission, certify a model, or
promote an evaluation to the routing bandit. Distinguish correctness claims
from whether a container was actually run.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable

from hex_cortex.memory.cortex_local_docker_sandbox import verify_repair_in_local_docker
from hex_cortex.memory.cortex_repo_repair_probe_v3 import RepairCase, score_repair


def review_repair_candidate(
    case: RepairCase,
    candidate: str,
    *,
    approve_docker: bool = False,
    seed: int = 20261009,
    docker_runner: Callable | None = None,
) -> dict[str, object]:
    """Return a privacy-safe two-rail verdict; approval never becomes persistent."""
    static = score_repair(case, candidate, seed=seed)
    digest = hashlib.sha256(candidate.encode("utf-8")).hexdigest() if isinstance(candidate, str) else ""
    base = {
        "report_type": "hex_cortex_local_critic_v4",
        "task_id": case.case_id,
        "candidate_sha256": digest,
        "static_passed": static["passed"],
        "static_cases_passed": static["correct_cases"],
        "static_total_cases": static["total_cases"],
        "sandbox_requested": approve_docker,
        "sandbox_executed": False,
        "sandbox_passed": None,
        "trusted": False,
        "allowed_to_modify_checkout": False,
        "routing_prior_authorized": False,
        "model_source_persisted": False,
        "verdict": "static_rejected",
    }
    if not static["passed"]:
        return base
    if not approve_docker:
        return {**base, "verdict": "static_passed_runtime_not_verified"}
    kwargs = {"approved": True, "seed": seed}
    if docker_runner is not None:
        kwargs["runner"] = docker_runner
    isolated = verify_repair_in_local_docker(case, candidate, **kwargs)
    verdict = "isolated_tests_passed" if isolated["passed"] else "isolated_tests_not_verified"
    return {
        **base,
        "sandbox_executed": isolated["executed"],
        "sandbox_passed": isolated["passed"] if isolated["executed"] else None,
        "sandbox_reason": isolated["reason"],
        "verdict": verdict,
        "trusted": False,  # even passing synthetic tests cannot certify.
    }
