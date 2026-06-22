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


def _ledger(root: Path) -> Path:
    ledger = root / "brains.jsonl"
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


def test_structured_execution_uses_ast_context_and_field_consensus(tmp_path: Path) -> None:
    module = tmp_path / "src" / "hex_cortex" / "memory"
    tests = tmp_path / "tests"
    module.mkdir(parents=True)
    tests.mkdir()
    rel = "src/hex_cortex/memory/cortex_verified_execution_runtime.py"
    (tmp_path / rel).write_text(
        "def execute_verified_local_loop():\n    return 'ok'\n",
        encoding="utf-8",
    )
    (tests / "test_runtime.py").write_text(
        "from hex_cortex.memory.cortex_verified_execution_runtime import "
        "execute_verified_local_loop\n\n"
        "def test_loop():\n    assert execute_verified_local_loop() == 'ok'\n",
        encoding="utf-8",
    )
    ledger = _ledger(tmp_path)
    plan = build_cognitive_loop_plan(
        ledger,
        _snapshot(),
        task_domain="code_generation",
        context_sensitivity="private",
        difficulty="high",
        risk="medium",
        cost_pressure=0.8,
    )
    calls: list[dict[str, object]] = []
    summaries = iter(("Ground execution.", "Use real paths.", "Vote on fields."))

    def transport(method, url, headers, payload, timeout):
        del method, url, headers, timeout
        calls.append(payload)
        content = json.dumps(
            {
                "summary": next(summaries),
                "focus_areas": [
                    "repository_context",
                    "consensus_quality",
                    "phase_separation",
                ],
                "candidate_files": [rel],
                "proposed_changes": [
                    {
                        "area": "repository_context",
                        "file": rel,
                        "objective": "ground the local plan",
                        "change": "inject bounded AST metadata",
                        "confidence": 0.9,
                    }
                ],
                "tests": ["run focused runtime tests"],
                "risks": ["context ranking may be narrow"],
                "unknowns": [],
            }
        )
        return {"message": {"role": "assistant", "content": content}, "done": True}

    receipt_path = tmp_path / "receipt.jsonl"
    result = execute_verified_local_loop(
        plan,
        ledger=ledger,
        gpu_snapshot=_snapshot(),
        model="qwen2.5-coder:7b",
        instruction="Return a grounded code plan.",
        task_prompt="Improve verified execution runtime and consensus.",
        repo_root=tmp_path,
        auto_repo_context=True,
        structured_code_plan=True,
        operator_approved=True,
        confirmation="EXECUTE_VERIFIED_LOCAL_LOOP",
        transport=transport,
        receipt_path=receipt_path,
    )

    assert result["status"] == "needs_human_review"
    assert result["structured_code_plan"] is True
    assert result["repo_context_module_count"] >= 1
    assert result["grounding_ratio"] == 1.0
    assert result["invalid_path_count"] == 0
    assert result["consensus_status"] == "consensus"
    assert result["consensus"]["support_count"] == 3
    assert result["consensus"]["consensus_plan"]["candidate_files"] == [rel]
    assert all("format" in call for call in calls)
    assert rel in calls[0]["messages"][1]["content"]
    assert "return 'ok'" not in calls[0]["messages"][1]["content"]
    assert calls[-1]["keep_alive"] == "0"

    persisted = json.loads(receipt_path.read_text(encoding="utf-8").splitlines()[0])
    assert persisted["raw_repo_context_persisted"] is False
    assert rel not in json.dumps(persisted)
    assert persisted["repo_context_hash"] is not None
