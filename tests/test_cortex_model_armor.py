"""Tests for the model armor plan builder."""

from __future__ import annotations

import pytest

from hex_cortex.memory.cortex_model_armor import (
    CODING_PROTOCOLS,
    build_model_armor_plan,
    list_coding_protocols,
    propose_protocol_skill_candidates,
)


def test_tiny_model_gets_maximal_discipline_and_smallest_steps() -> None:
    plan = build_model_armor_plan(parameter_scale="tiny", context_window_tokens=8_000)

    assert plan["armor_type"] == "cortex_model_armor_plan_v1"
    assert plan["discipline"] == "maximal"
    assert plan["step_budget"]["max_files_per_step"] == 1
    assert plan["loop_contract"]["restate_task_before_acting"] is True
    assert plan["verification_contract"]["adversarial_self_review"] is True
    assert plan["context_policy"]["compression_required"] is True
    assert "context_compression" in plan["prompt_scaffold_sections"]
    assert plan["model_call_performed"] is False


def test_large_model_gets_light_discipline_but_same_safety() -> None:
    plan = build_model_armor_plan(
        parameter_scale="large",
        context_window_tokens=200_000,
        supports_tool_calls=True,
        supports_json_schema=True,
    )

    assert plan["discipline"] == "light"
    assert plan["loop_contract"]["restate_task_before_acting"] is False
    assert plan["output_format"] == "json_schema"
    assert "context_compression" not in plan["prompt_scaffold_sections"]
    # Safety and verification never scale down.
    assert plan["verification_contract"]["claim_requires_execution"] is True
    assert plan["safety_contract"]["base_model_guardrails_untouched"] is True
    assert plan["reflection_contract"]["skill_proposals_are_candidates_only"] is True


def test_loop_phases_are_always_the_full_cycle() -> None:
    for scale in ("tiny", "small", "medium", "large"):
        plan = build_model_armor_plan(parameter_scale=scale, context_window_tokens=32_000)
        assert plan["loop_contract"]["phases"] == [
            "understand",
            "plan",
            "act",
            "verify",
            "reflect",
        ]
        assert plan["mandatory_protocols"] == [
            str(protocol["protocol_id"]) for protocol in CODING_PROTOCOLS
        ]


def test_high_risk_reuses_adaptive_compute_escalation() -> None:
    plan = build_model_armor_plan(
        parameter_scale="small",
        context_window_tokens=32_000,
        task_risk="critical",
        large_model_available=True,
    )

    strategy = plan["compute_strategy"]
    assert strategy["strategy"] == "large_model_reinforced_human"
    assert strategy["require_human_validation"] is True


def test_invalid_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        build_model_armor_plan(parameter_scale="huge", context_window_tokens=8_000)
    with pytest.raises(ValueError):
        build_model_armor_plan(parameter_scale="tiny", context_window_tokens=0)
    with pytest.raises(ValueError):
        build_model_armor_plan(
            parameter_scale="tiny", context_window_tokens=8_000, task_risk="extreme"
        )


def test_protocol_library_is_copied_not_shared() -> None:
    protocols = list_coding_protocols()
    assert len(protocols) == len(CODING_PROTOCOLS)

    protocols[0]["steps"].append("mutated")
    assert "mutated" not in CODING_PROTOCOLS[0]["steps"]

    ids = [protocol["protocol_id"] for protocol in protocols]
    assert len(ids) == len(set(ids))


def test_skill_candidates_respect_promotion_governance() -> None:
    candidates = propose_protocol_skill_candidates()
    assert len(candidates) == len(CODING_PROTOCOLS)

    for candidate in candidates:
        assert candidate["status"] == "candidate"
        assert candidate["requires_operator_approval"] is True
        assert candidate["source_rule_ids"]
        assert candidate["workflow_steps"]
