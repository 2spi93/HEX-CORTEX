import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_verified_inference_plan import build_verified_inference_plan


def _register(
    ledger: Path,
    *,
    brain_id: str,
    coding: float,
    general: float,
    reliability: float,
    latency: float = 1000.0,
    cost: float = 0.05,
) -> None:
    append_brain_phenotype(
        ledger,
        brain_id=brain_id,
        model_id=f"model-{brain_id}",
        model_family="coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"coding": coding, "research": general, "general": general},
        reliability_score=reliability,
        latency_ms=latency,
        normalized_cost=cost,
        baseline_hash="a" * 64,
    )


def test_plan_ready_picks_primary_and_escalation(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="coder-7b", coding=0.85, general=0.6, reliability=0.9)
    _register(ledger, brain_id="generalist-14b", coding=0.7, general=0.92, reliability=0.9)

    plan = build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )

    assert plan["status"] == "ready"
    assert plan["primary_brain_id"] == "coder-7b"
    assert plan["escalation_brain_id"] == "generalist-14b"
    assert plan["sampling_plan"]["initial_samples"] == 5
    assert plan["stages"][0] == "route_primary_brain"
    assert plan["model_call_performed"] is False
    assert len(plan["plan_hash"]) == 64


def test_single_brain_has_no_escalation(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="solo", coding=0.8, general=0.8, reliability=0.9)
    plan = build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
    )
    assert plan["status"] == "ready"
    assert plan["primary_brain_id"] == "solo"
    assert plan["escalation_brain_id"] is None


def test_plan_blocked_when_no_eligible_brain(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="weak", coding=0.1, general=0.1, reliability=0.2)
    plan = build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
        minimum_acceptable_score=0.7,
    )
    assert plan["status"] == "blocked"
    assert plan["primary_brain_id"] is None
    assert plan["next_action"] == "escalate_or_refuse_task"


def test_plan_receipt_is_written(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="solo", coding=0.8, general=0.8, reliability=0.9)
    receipt = tmp_path / "plans.jsonl"
    build_verified_inference_plan(
        ledger,
        task_domain="coding",
        context_sensitivity="private",
        maximum_latency_ms=5000.0,
        cost_pressure=0.5,
        remote_allowed=False,
        receipt_path=receipt,
    )
    row = json.loads(receipt.read_text(encoding="utf-8").splitlines()[0])
    assert row["record_type"] == "cortex_verified_inference_plan_v1"
    assert row["raw_response_persisted"] is False


def test_invalid_sampling_parameters_rejected(tmp_path: Path) -> None:
    ledger = tmp_path / "brains.jsonl"
    _register(ledger, brain_id="solo", coding=0.8, general=0.8, reliability=0.9)
    common = {
        "task_domain": "coding",
        "context_sensitivity": "private",
        "maximum_latency_ms": 5000.0,
        "cost_pressure": 0.5,
        "remote_allowed": False,
    }
    with pytest.raises(ValueError):
        build_verified_inference_plan(ledger, initial_samples=0, **common)
    with pytest.raises(ValueError):
        build_verified_inference_plan(ledger, initial_samples=8, max_samples=4, **common)
    with pytest.raises(ValueError):
        build_verified_inference_plan(ledger, target_confidence=1.5, **common)
