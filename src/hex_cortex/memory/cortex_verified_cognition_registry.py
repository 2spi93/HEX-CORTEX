from __future__ import annotations

from hex_cortex.memory.cortex_adaptive_compute_policy import select_compute_strategy
from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan
from hex_cortex.memory.cortex_competence_rule_candidate import (
    build_competence_rule_candidate,
)
from hex_cortex.memory.cortex_gpu_governor import decide_gpu_admission
from hex_cortex.memory.cortex_patch_tournament import rank_patch_candidates
from hex_cortex.memory.cortex_pot_evaluator import grade_arithmetic
from hex_cortex.memory.cortex_repo_graph import build_repo_graph
from hex_cortex.memory.cortex_repo_graph import summarize_module_contract
from hex_cortex.memory.cortex_self_consistency import aggregate_self_consistency
from hex_cortex.memory.cortex_self_consistency import aggregate_verification_votes
from hex_cortex.memory.cortex_verification_policy import decide_verification_action
from hex_cortex.memory.cortex_verified_inference_plan import (
    build_verified_inference_plan,
)


def build_verified_cognition_registry() -> dict[str, CortexUnit]:
    """Canonical cold-mode organs for verified reasoning and coding work."""
    return {
        "compute.strategy": CortexUnit(
            name="compute.strategy",
            unit=select_compute_strategy,
            description="Select an adaptive test-time compute strategy from difficulty and risk.",
        ),
        "gpu.admission": CortexUnit(
            name="gpu.admission",
            unit=decide_gpu_admission,
            description="Admit, downgrade, queue, defer, or reject a model request.",
        ),
        "verification.consensus": CortexUnit(
            name="verification.consensus",
            unit=aggregate_self_consistency,
            description="Aggregate sampled answers with weighted fail-closed consensus.",
            mutates_receipt=True,
        ),
        "verification.adversarial": CortexUnit(
            name="verification.adversarial",
            unit=aggregate_verification_votes,
            description="Aggregate independent adversarial verifier verdicts.",
            mutates_receipt=True,
        ),
        "verification.next": CortexUnit(
            name="verification.next",
            unit=decide_verification_action,
            description="Accept, resample, escalate, or refuse from measured confidence.",
        ),
        "inference.plan": CortexUnit(
            name="inference.plan",
            unit=build_verified_inference_plan,
            description="Build a routed self-consistency and escalation plan.",
            mutates_receipt=True,
        ),
        "cognitive.loop.plan": CortexUnit(
            name="cognitive.loop.plan",
            unit=build_cognitive_loop_plan,
            description="Compose strategy, GPU admission, routing, and verification into one plan.",
            mutates_receipt=True,
        ),
        "repo.graph.build": CortexUnit(
            name="repo.graph.build",
            unit=build_repo_graph,
            description="Build a read-only Python repository intelligence graph.",
        ),
        "repo.module.contract": CortexUnit(
            name="repo.module.contract",
            unit=summarize_module_contract,
            description="Summarize the public contract of a module without reading full bodies.",
        ),
        "patch.tournament": CortexUnit(
            name="patch.tournament",
            unit=rank_patch_candidates,
            description="Rank patch candidates by external verifier truth and regression gates.",
            mutates_receipt=True,
        ),
        "competence.rule.candidate": CortexUnit(
            name="competence.rule.candidate",
            unit=build_competence_rule_candidate,
            description="Propose, never install, a competence rule from recurrent verified residuals.",
            mutates_receipt=True,
            requires_operator=True,
        ),
        "pot.grade": CortexUnit(
            name="pot.grade",
            unit=grade_arithmetic,
            description="Grade exact arithmetic with a deterministic AST-whitelisted evaluator.",
        ),
    }
