from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan


def _ledger(tmp_path: Path) -> Path:
    ledger = tmp_path / "brains.jsonl"
    append_brain_phenotype(
        ledger,
        brain_id="coder-7b",
        model_id="m-coder",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.85, "research": 0.6, "general": 0.6},
        reliability_score=0.9,
        latency_ms=1000.0,
        normalized_cost=0.05,
        baseline_hash="a" * 64,
    )
    append_brain_phenotype(
        ledger,
        brain_id="generalist-14b",
        model_id="m-gen",
        model_family="general",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": 0.7, "research": 0.92, "general": 0.9},
        reliability_score=0.9,
        latency_ms=1800.0,
        normalized_cost=0.08,
        baseline_hash="b" * 64,
    )
    return ledger


def _snap(**over: object) -> dict[str, object]:
    base = {
        "vram_total_mb": 12288.0,
        "vram_used_mb": 470.0,
        "temperature_c": 55.0,
        "loaded_model_count": 0,
        "big_model_loaded": False,
        "queue_depth": 0,
        "recent_oom_count": 0,
        "in_cooldown": False,
        "interactive_task_active": False,
    }
    base.update(over)
    return base


def test_ready_plan_composes_all_three_layers(tmp_path: Path) -> None:
    plan = build_cognitive_loop_plan(
        _ledger(tmp_path),
        _snap(),
        task_domain="coding",
        context_sensitivity="private",
        difficulty="medium",
        risk="low",
    )
    assert plan["status"] == "ready"
    assert plan["primary_brain_id"] == "coder-7b"
    assert plan["escalation_brain_id"] == "generalist-14b"
    assert plan["use_self_consistency"] is True  # medium difficulty
    assert "strategy" in plan["components"]
    assert "gpu_decision" in plan["components"]
    assert len(plan["plan_hash"]) == 64


def test_critical_vram_blocks_the_loop(tmp_path: Path) -> None:
    plan = build_cognitive_loop_plan(
        _ledger(tmp_path),
        _snap(vram_used_mb=11800.0),
        task_domain="coding",
        context_sensitivity="private",
    )
    assert plan["status"] == "blocked"
    assert any("gpu" in b for b in plan["blockers"])
    assert plan["next_action"] == "retry_after_cooldown_or_escalate"


def test_exact_arithmetic_forces_deterministic_tool(tmp_path: Path) -> None:
    plan = build_cognitive_loop_plan(
        _ledger(tmp_path),
        _snap(),
        task_domain="arithmetic_reasoning",
        context_sensitivity="private",
        difficulty="low",
        prior_confidence=0.95,
    )
    assert plan["exact_arithmetic_domain"] is True
    assert plan["use_deterministic_tool"] is True


def test_high_risk_requires_human_and_large_tier(tmp_path: Path) -> None:
    plan = build_cognitive_loop_plan(
        _ledger(tmp_path),
        _snap(),
        task_domain="coding",
        context_sensitivity="private",
        risk="high",
    )
    assert plan["require_human_validation"] is True
    # No remote brain registered -> large tier unavailable -> governor grants small.
    assert plan["granted_tier"] == "small"


def test_no_eligible_brain_blocks(tmp_path: Path) -> None:
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    plan = build_cognitive_loop_plan(
        empty,
        _snap(),
        task_domain="coding",
        context_sensitivity="private",
    )
    assert plan["status"] == "blocked"
    assert plan["primary_brain_id"] is None
