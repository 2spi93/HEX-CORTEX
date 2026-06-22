from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan


def test_low_confidence_strategy_requires_human_when_only_alias_brains_exist(
    tmp_path: Path,
) -> None:
    ledger = tmp_path / "brains.jsonl"
    for brain_id, score in (
        ("windows-coding-primary", 0.8),
        ("windows-coder-7b-benchmark", 0.75),
    ):
        append_brain_phenotype(
            ledger,
            brain_id=brain_id,
            model_id="qwen2.5-coder:7b",
            model_family="qwen-coder",
            runtime_id="windows.ollama",
            node_id="windows",
            provider_scope="local",
            domain_scores={"code_generation": score, "general": score},
            reliability_score=0.9,
            latency_ms=300.0,
            normalized_cost=0.0,
            baseline_hash="a" * 64,
        )

    plan = build_cognitive_loop_plan(
        ledger,
        {"vram_total_mb": 12288.0, "vram_used_mb": 1000.0},
        task_domain="code_generation",
        context_sensitivity="private",
        difficulty="high",
        risk="medium",
        cost_pressure=0.8,
    )

    assert plan["status"] == "ready"
    assert plan["escalation_brain_id"] is None
    assert plan["verification_gap"] is True
    assert plan["independent_critic_available"] is False
    assert plan["require_human_validation"] is True
    assert plan["next_action"] == "execute_primary_then_human_review"
    assert plan["warnings"] == [
        "independent_model_unavailable_human_review_required"
    ]
