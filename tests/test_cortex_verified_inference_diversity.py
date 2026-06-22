from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_verified_inference_plan import build_verified_inference_plan


def _register(
    ledger: Path,
    *,
    brain_id: str,
    model_id: str,
    coding: float,
) -> None:
    append_brain_phenotype(
        ledger,
        brain_id=brain_id,
        model_id=model_id,
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": coding, "general": coding},
        reliability_score=0.95,
        latency_ms=500.0,
        normalized_cost=0.0,
        baseline_hash="a" * 64,
    )


def test_aliases_of_same_model_do_not_form_fake_escalation(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(
        ledger,
        brain_id="windows-coding-primary",
        model_id="qwen2.5-coder:7b",
        coding=0.90,
    )
    _register(
        ledger,
        brain_id="windows-coder-7b-fast-benchmark",
        model_id="qwen2.5-coder:7b",
        coding=0.80,
    )

    plan = build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )

    assert plan["primary_brain_id"] == "windows-coding-primary"
    assert plan["escalation_brain_id"] is None
    assert plan["escalation_diversity"] == "no_independent_model_available"


def test_distinct_model_remains_available_for_real_escalation(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="primary", model_id="qwen2.5-coder:7b", coding=0.90)
    _register(ledger, brain_id="alias", model_id="qwen2.5-coder:7b", coding=0.85)
    _register(ledger, brain_id="independent", model_id="gemma-3:12b", coding=0.75)

    plan = build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )

    assert plan["primary_brain_id"] == "primary"
    assert plan["escalation_brain_id"] == "independent"
    assert plan["escalation_diversity"] == "distinct_model_hash"
