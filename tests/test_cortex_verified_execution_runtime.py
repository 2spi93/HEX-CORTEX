import json
from pathlib import Path

from hex_cortex.memory.cortex_cognitive_brain_registry import append_brain_phenotype
from hex_cortex.memory.cortex_cognitive_loop_plan import build_cognitive_loop_plan
from hex_cortex.memory.cortex_verified_execution_runtime import execute_verified_local_loop


def _snapshot() -> dict[str, object]:
    return {
        "vram_total_mb": 12288.0,
        "vram_used_mb": 1000.0,
        "temperature_c": 45.0,
        "gpu_utilization_pct": 2.0,
        "loaded_model_count": 0,
        "big_model_loaded": False,
        "queue_depth": 0,
        "recent_latency_ms": 0.0,
        "recent_oom_count": 0,
        "in_cooldown": False,
        "interactive_task_active": False,
    }


def _ledger(tmp_path: Path) -> Path:
    ledger = tmp_path / "brains.jsonl"
    append_brain_phenotype(
        ledger,
        brain_id="windows-coding-primary",
        model_id="qwen2.5-coder:7b",
        model_family="qwen-coder",
        runtime_id="windows.ollama",
        node_id="windows",
        provider_scope="local",
        domain_scores={"code_generation": 0.8, "general": 0.75},
        reliability_score=0.9,
        latency_ms=300.0,
        normalized_cost=0.0,
        baseline_hash="a" * 64,
    )
    return ledger


def _plan(ledger: Path) -> dict[str, object]:
    return build_cognitive_loop_plan(
        ledger,
        _snapshot(),
        task_domain="code_generation",
        context_sensitivity="private",
        difficulty="high",
        risk="medium",
        cost_pressure=0.8,
    )


def test_primary_sampling_stops_at_human_review_without_independent_critic(
    tmp_path: Path,
) -> None:
    ledger = _ledger(tmp_path)
    plan = _plan(ledger)
    calls: list[dict[str, object]] = []
    receipt_path = tmp_path / "execution.jsonl"

    def transport(method, url, headers, payload, timeout):
        del method, url, headers, timeout
        calls.append(payload)
        return {
            "message": {
                "role": "assistant",
                "content": "Use the parser contract and add a focused regression test.",
            },
            "done": True,
        }

    result = execute_verified_local_loop(
        plan,
        ledger=ledger,
        gpu_snapshot=_snapshot(),
        model="qwen2.5-coder:7b",
        instruction="Return a concise implementation plan.",
        task_prompt="Repair the parser without changing public behavior.",
        operator_approved=True,
        confirmation="EXECUTE_VERIFIED_LOCAL_LOOP",
        transport=transport,
        receipt_path=receipt_path,
    )

    assert result["status"] == "needs_human_review"
    assert result["sample_count_completed"] == 3
    assert result["verification_action"] == "human_review"
    assert result["repository_mutation_performed"] is False
    assert result["shell_command_performed"] is False
    assert result["volatile_consensus_answer"].startswith("Use the parser")
    assert len(calls) == 3
    assert calls[-1]["keep_alive"] == "0"

    persisted = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert "volatile_consensus_answer" not in persisted
    assert "Use the parser" not in json.dumps(persisted)
    assert persisted["raw_consensus_answer_persisted"] is False


def test_execution_requires_exact_phrase_and_performs_no_call(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)
    calls = []

    result = execute_verified_local_loop(
        _plan(ledger),
        ledger=ledger,
        gpu_snapshot=_snapshot(),
        model="qwen2.5-coder:7b",
        instruction="Plan.",
        task_prompt="Task.",
        operator_approved=True,
        confirmation="wrong phrase",
        transport=lambda *args: calls.append(args) or {},
    )

    assert result["status"] == "blocked"
    assert result["model_call_performed"] is False
    assert "confirmation_phrase_invalid" in result["blockers"]
    assert calls == []


def test_execution_rejects_model_alias_not_matching_primary(tmp_path: Path) -> None:
    ledger = _ledger(tmp_path)

    result = execute_verified_local_loop(
        _plan(ledger),
        ledger=ledger,
        gpu_snapshot=_snapshot(),
        model="different-model:7b",
        instruction="Plan.",
        task_prompt="Task.",
        operator_approved=True,
        confirmation="EXECUTE_VERIFIED_LOCAL_LOOP",
    )

    assert result["status"] == "blocked"
    assert "model_does_not_match_primary_brain" in result["blockers"]
