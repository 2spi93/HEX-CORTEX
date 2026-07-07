"""Model armor — a cognitive exoskeleton for any base model, especially small ones.

HEX-CORTEX is model-interchangeable. What makes a small model strong is not the
model: it is the discipline wrapped around it. This module emits a deterministic
*armor plan* for a given model profile. The plan encodes proven senior-engineer
working protocols (baseline first, read before edit, smallest-cause fix,
empirical verification, post-error reflection) and scales the scaffolding
inversely to model capability: the smaller the model, the more explicit the
armor.

The armor never weakens safety: verification, reflection and escalation are
mandatory at every scale, and nothing here removes or bypasses a base model's
own guardrails. Pure and cold — it emits a plan, runs nothing, calls no model.
"""

from __future__ import annotations

from hex_cortex.memory.cortex_adaptive_compute_policy import select_compute_strategy

_ARMOR_TYPE = "cortex_model_armor_plan_v1"
_PROTOCOL_TYPE = "cortex_coding_protocol_v1"
_SCALES = ("tiny", "small", "medium", "large")
_LEVELS = {"low", "medium", "high", "critical"}

# Discipline is inversely proportional to capability.
_DISCIPLINE_BY_SCALE = {
    "tiny": "maximal",
    "small": "strict",
    "medium": "standard",
    "large": "light",
}
_STEP_BUDGET_BY_SCALE = {
    "tiny": {"max_files_per_step": 1, "max_diff_lines_per_step": 40, "max_plan_steps": 3},
    "small": {"max_files_per_step": 2, "max_diff_lines_per_step": 80, "max_plan_steps": 5},
    "medium": {"max_files_per_step": 4, "max_diff_lines_per_step": 200, "max_plan_steps": 8},
    "large": {"max_files_per_step": 8, "max_diff_lines_per_step": 400, "max_plan_steps": 12},
}
_DIFFICULTY_BY_SCALE = {"tiny": "high", "small": "high", "medium": "medium", "large": "low"}

# Senior-engineer working protocols, encoded as reusable skill material.
CODING_PROTOCOLS: tuple[dict[str, object], ...] = (
    {
        "protocol_id": "protocol_baseline_first",
        "name": "Baseline before change",
        "trigger_tags": ["coding", "debugging", "refactoring"],
        "steps": [
            "Run the full test suite and linter before touching anything.",
            "Record the baseline result; it is the only honest reference point.",
            "If the baseline is already red, fix or report that first.",
        ],
    },
    {
        "protocol_id": "protocol_read_before_edit",
        "name": "Read before edit",
        "trigger_tags": ["coding", "refactoring"],
        "steps": [
            "Read every file you intend to modify, plus its tests and callers.",
            "Match the surrounding conventions: naming, idiom, comment density.",
            "Never edit code you have not read in this session.",
        ],
    },
    {
        "protocol_id": "protocol_plan_before_code",
        "name": "Plan before code",
        "trigger_tags": ["coding", "planning"],
        "steps": [
            "Restate the task in one sentence before acting.",
            "List the files to change and why, before changing any.",
            "Prefer the smallest plan that fully solves the task.",
        ],
    },
    {
        "protocol_id": "protocol_smallest_cause_fix",
        "name": "Smallest-cause fix",
        "trigger_tags": ["debugging"],
        "steps": [
            "Reproduce the failure and read the actual error output.",
            "Trace to the smallest relevant cause; never paper over a symptom.",
            "Fix that cause only, then rerun targeted tests, then the full suite.",
        ],
    },
    {
        "protocol_id": "protocol_empirical_verification",
        "name": "Empirical verification",
        "trigger_tags": ["coding", "verification"],
        "steps": [
            "Never claim behavior you have not executed and observed.",
            "When unsure how a library behaves, write a tiny probe and run it.",
            "Report failures verbatim; a red test is information, not shame.",
        ],
    },
    {
        "protocol_id": "protocol_atomic_commits",
        "name": "Atomic commits",
        "trigger_tags": ["coding", "git"],
        "steps": [
            "One logical concern per commit, with why the change exists.",
            "Keep the tree green at every commit.",
            "Work branch-first; never mutate outside the current branch.",
        ],
    },
    {
        "protocol_id": "protocol_post_error_reflection",
        "name": "Post-error reflection",
        "trigger_tags": ["reflection", "learning"],
        "steps": [
            "Classify each failure against the error ontology (knowledge_gap, logic_error, planning_error, context_loss, tool_misuse, hallucination, ambiguity_failure, capability_limit, uncertainty_failure, causal_misattribution).",
            "Extract one reusable lesson: what failed, what worked, what to block next time.",
            "Propose a candidate skill or preset when a pattern repeats; never self-install it.",
        ],
    },
    {
        "protocol_id": "protocol_adversarial_self_review",
        "name": "Adversarial self-review",
        "trigger_tags": ["review", "verification"],
        "steps": [
            "After producing a change, switch roles and try to refute it.",
            "Hunt for the failure scenario: which input or state breaks this?",
            "Only keep claims that survive your own refutation attempt.",
        ],
    },
)


def list_coding_protocols() -> list[dict[str, object]]:
    """Return the protocol library as immutable-by-copy records."""

    return [
        {"protocol_type": _PROTOCOL_TYPE, **protocol, "steps": list(protocol["steps"])}
        for protocol in CODING_PROTOCOLS
    ]


def propose_protocol_skill_candidates() -> list[dict[str, object]]:
    """Shape every protocol as a CANDIDATE skill proposal.

    Governance: proposals only. Installation and activation stay behind the
    human promotion gate; nothing here mutates the skill library.
    """

    candidates = []
    for protocol in CODING_PROTOCOLS:
        candidates.append(
            {
                "proposal_type": "skill_candidate_proposal_v1",
                "name": str(protocol["name"]),
                "description": "Coding protocol distilled from proven agentic engineering practice.",
                "trigger_tags": list(protocol["trigger_tags"]),
                "workflow_steps": list(protocol["steps"]),
                "status": "candidate",
                "source_rule_ids": [str(protocol["protocol_id"])],
                "requires_operator_approval": True,
            }
        )
    return candidates


def build_model_armor_plan(
    *,
    parameter_scale: str,
    context_window_tokens: int,
    supports_tool_calls: bool = False,
    supports_json_schema: bool = False,
    task_risk: str = "medium",
    python_available: bool = True,
    large_model_available: bool = False,
) -> dict[str, object]:
    """Build the cognitive armor plan for one base model profile.

    The plan is advice for a runtime: prompt scaffold sections, step budgets,
    mandatory protocols, verification and escalation contracts, plus a compute
    strategy reused from the adaptive compute policy.
    """

    if parameter_scale not in _SCALES:
        raise ValueError("parameter_scale must be tiny/small/medium/large")
    if context_window_tokens <= 0:
        raise ValueError("context_window_tokens must be positive")
    if task_risk not in _LEVELS:
        raise ValueError("task_risk must be low/medium/high/critical")

    discipline = _DISCIPLINE_BY_SCALE[parameter_scale]
    step_budget = dict(_STEP_BUDGET_BY_SCALE[parameter_scale])
    tight_context = context_window_tokens < 16_000

    scaffold_sections = [
        "role_and_constraints",
        "task_restatement",
        "repository_context",
        "plan_contract",
        "action_contract",
        "verification_contract",
        "reflection_contract",
        "output_format",
    ]
    if tight_context:
        scaffold_sections.insert(2, "context_compression")

    mandatory_protocols = [str(protocol["protocol_id"]) for protocol in CODING_PROTOCOLS]
    if discipline in {"maximal", "strict"}:
        # Small models must restate and self-review; big ones merely should.
        loop_contract = {
            "phases": ["understand", "plan", "act", "verify", "reflect"],
            "restate_task_before_acting": True,
            "one_concern_per_step": True,
            "self_review_before_output": True,
        }
    else:
        loop_contract = {
            "phases": ["understand", "plan", "act", "verify", "reflect"],
            "restate_task_before_acting": False,
            "one_concern_per_step": False,
            "self_review_before_output": True,
        }

    output_format = "json_schema" if supports_json_schema else "fenced_json"
    compute_strategy = select_compute_strategy(
        difficulty=_DIFFICULTY_BY_SCALE[parameter_scale],
        risk=task_risk,
        python_available=python_available,
        large_model_available=large_model_available,
    )

    reasons = [f"scale_{parameter_scale}_gets_{discipline}_discipline"]
    if tight_context:
        reasons.append("tight_context_requires_compression_and_retrieval_first")
    if not supports_tool_calls:
        reasons.append("no_tool_calls_requires_explicit_textual_action_contract")

    return {
        "armor_type": _ARMOR_TYPE,
        "parameter_scale": parameter_scale,
        "discipline": discipline,
        "loop_contract": loop_contract,
        "step_budget": step_budget,
        "prompt_scaffold_sections": scaffold_sections,
        "mandatory_protocols": mandatory_protocols,
        "output_format": output_format,
        "tool_calls_available": supports_tool_calls,
        "context_policy": {
            "context_window_tokens": context_window_tokens,
            "compression_required": tight_context,
            "retrieval_first": True,
            "max_snippet_lines": 40 if tight_context else 120,
        },
        "verification_contract": {
            "deterministic_checks_required": ["pytest", "lint"],
            "claim_requires_execution": True,
            "adversarial_self_review": discipline in {"maximal", "strict"},
        },
        "escalation_contract": {
            "escalate_after_failed_verifications": 2,
            "escalate_when_risk_at_least": "high",
            "escalation_target": "larger_model_or_operator",
        },
        "reflection_contract": {
            "classify_errors_against_ontology": True,
            "extract_lesson_after_task": True,
            "skill_proposals_are_candidates_only": True,
        },
        "safety_contract": {
            "base_model_guardrails_untouched": True,
            "no_secret_access": True,
            "branch_first_mutation_only": True,
        },
        "compute_strategy": compute_strategy,
        "model_call_performed": False,
        "reasons": reasons,
        "next_action": "assemble_prompt_scaffold",
    }
