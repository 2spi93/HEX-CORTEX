from __future__ import annotations

from pathlib import Path

from hex_cortex.memory import cortex_operational_intelligence_tools as intelligence_tools
from hex_cortex.memory import cortex_operational_rpc_tools as operational_tools
from hex_cortex.memory.cortex_operational_rpc import handle_cortex_operational_rpc_message
from hex_cortex.memory.cortex_operational_rpc_tools import call_cortex_operational_rpc_tool
from hex_cortex.memory.cortex_operational_rpc_tools import list_cortex_operational_rpc_tools
from hex_cortex.memory.cortex_rpc import CortexRpcSession
from hex_cortex.memory.cortex_rpc import PROTOCOL_VERSION


def test_operational_rpc_catalog_extends_legacy_tools() -> None:
    rows = list_cortex_operational_rpc_tools()

    assert len(rows) == 14
    assert {row["name"] for row in rows} >= {
        "hex_cortex_wiring",
        "hex_cortex_operational_audit",
        "hex_cortex_cognitive_genome",
        "hex_cortex_cognitive_loop",
        "hex_cortex_repo_intelligence",
    }
    assert all(row["annotations"]["readOnlyHint"] is True for row in rows)
    assert all(row["annotations"]["destructiveHint"] is False for row in rows)


def test_wiring_uses_canonical_snapshot_when_facts_are_omitted(monkeypatch) -> None:
    monkeypatch.setattr(
        operational_tools,
        "build_operational_audit",
        lambda *args, **kwargs: _snapshot(),
    )

    payload, is_error = call_cortex_operational_rpc_tool("hex_cortex_wiring", {})

    assert is_error is False
    assert payload["operational_ready"] is True
    assert payload["truth_source"] == "hex_cortex_operational_truth_v1"
    assert payload["runtime_facts"]["local_model_runtime_available"] is True
    assert payload["operational_snapshot"]["readiness"]["runtime_ready"] is True


def test_wiring_preserves_explicit_manual_facts() -> None:
    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_wiring",
        {"runtime_facts": {"local_model_runtime_available": True}},
    )

    assert is_error is False
    assert payload["runtime_facts"] == {"local_model_runtime_available": True}
    assert "truth_source" not in payload


def test_operational_audit_tool_returns_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(
        operational_tools,
        "build_operational_audit",
        lambda *args, **kwargs: _snapshot(),
    )

    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_operational_audit",
        {"network": True, "include_research": False},
    )

    assert is_error is False
    assert payload["audit_type"] == "hex_cortex_operational_truth_v1"
    assert payload["runtime_ready"] is True


def test_cognitive_genome_tool_audits_repository_contract() -> None:
    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_cognitive_genome",
        {"action": "audit", "project_root": "."},
    )

    assert is_error is False
    assert payload["genome_ready"] is True
    assert payload["base_model_immutable"] is True


def test_cognitive_genome_tool_builds_profile_council() -> None:
    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_cognitive_genome",
        {
            "action": "council",
            "failure_class": "planning_error",
            "novelty": 0.8,
            "uncertainty": 0.9,
            "mutation_requested": True,
        },
    )

    assert is_error is False
    assert "scientist" in payload["selected_profiles"]
    assert "constitutional_judge" in payload["selected_profiles"]
    assert payload["majority_vote_allowed"] is False


def test_cognitive_loop_tool_is_read_only_plan(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    captured: dict[str, object] = {}

    def fake_plan(ledger: Path, snapshot: dict[str, object], **kwargs):
        captured["ledger"] = ledger
        captured["snapshot"] = snapshot
        captured.update(kwargs)
        return {
            "status": "ready",
            "strategy": "small_single",
            "model_call_performed": False,
            "blockers": [],
        }

    monkeypatch.setattr(intelligence_tools, "build_cognitive_loop_plan", fake_plan)
    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_cognitive_loop",
        {
            "gpu_snapshot": {"vram_total_mb": 12288, "vram_used_mb": 1000},
            "task_domain": "code_generation",
            "context_sensitivity": "private",
            "difficulty": "medium",
        },
    )

    assert is_error is False
    assert payload["status"] == "ready"
    assert payload["model_call_performed"] is False
    assert captured["snapshot"] == {"vram_total_mb": 12288, "vram_used_mb": 1000}
    assert captured["task_domain"] == "code_generation"
    assert str(captured["ledger"]).startswith(str(tmp_path))


def test_cognitive_loop_tool_rejects_path_escape(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)

    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_cognitive_loop",
        {
            "ledger_path": "../outside.jsonl",
            "gpu_snapshot": {"vram_total_mb": 12288, "vram_used_mb": 1000},
            "task_domain": "coding",
            "context_sensitivity": "private",
        },
    )

    assert is_error is True
    assert payload["blockers"] == ["cognitive_loop_arguments_invalid"]


def test_repo_intelligence_tool_queries_ast_without_source_bodies(
    monkeypatch,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    package = tmp_path / "pkg"
    tests = tmp_path / "tests"
    package.mkdir()
    tests.mkdir()
    (package / "core.py").write_text(
        'def add(a, b):\n    """Add values."""\n    return a + b\n',
        encoding="utf-8",
    )
    (tests / "test_core.py").write_text(
        "from pkg.core import add\n\ndef test_add():\n    assert add(1, 2) == 3\n",
        encoding="utf-8",
    )

    symbol_payload, symbol_error = call_cortex_operational_rpc_tool(
        "hex_cortex_repo_intelligence",
        {"action": "find_symbol", "symbol": "add"},
    )
    tests_payload, tests_error = call_cortex_operational_rpc_tool(
        "hex_cortex_repo_intelligence",
        {"action": "find_tests", "symbol": "add"},
    )
    contract_payload, contract_error = call_cortex_operational_rpc_tool(
        "hex_cortex_repo_intelligence",
        {"action": "module_contract", "module": "pkg/core.py"},
    )

    assert symbol_error is False
    assert symbol_payload["result_count"] == 1
    assert symbol_payload["source_bodies_returned"] is False
    assert tests_error is False
    assert tests_payload["results"] == ["tests/test_core.py"]
    assert contract_error is False
    assert contract_payload["public_functions"][0]["signature"] == "add(a, b)"
    assert "return a + b" not in str(contract_payload)


def test_repo_intelligence_rejects_project_escape(monkeypatch, tmp_path: Path) -> None:
    work = tmp_path / "work"
    work.mkdir()
    monkeypatch.chdir(work)

    payload, is_error = call_cortex_operational_rpc_tool(
        "hex_cortex_repo_intelligence",
        {"project_root": "..", "action": "summary"},
    )

    assert is_error is True
    assert payload["blockers"] == ["repo_intelligence_arguments_invalid"]


def test_operational_rpc_initializes_and_lists_tools() -> None:
    session = CortexRpcSession()
    initialized = handle_cortex_operational_rpc_message(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "test", "version": "1"},
            },
        },
        session=session,
    )
    listing = handle_cortex_operational_rpc_message(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        session=session,
    )

    assert initialized["result"]["serverInfo"]["version"] == "1.2.0"
    assert len(listing["result"]["tools"]) == 14


def _snapshot() -> dict[str, object]:
    facts = {"local_model_runtime_available": True}
    wiring = {
        "audit_type": "cortex_wiring_audit",
        "architecture_ready": True,
        "operational_ready": True,
        "runtime_facts": facts,
        "runtime_blockers": [],
    }
    return {
        "audit_type": "hex_cortex_operational_truth_v1",
        "audit_hash": "a" * 64,
        "code_ready": True,
        "runtime_ready": True,
        "models_ready": True,
        "research_ready": False,
        "media_ready": True,
        "world_model_ready": True,
        "policy_v2_ready": False,
        "self_correction_ready": False,
        "remote_api_ready": False,
        "cognitive_genome_ready": True,
        "server_ready": False,
        "security_ready": False,
        "branch_ready": False,
        "operational_ready": False,
        "runtime_facts": facts,
        "category_blockers": {},
        "wiring": wiring,
        "network_call_performed": True,
        "next_action": "run_searxng_live_citation_audit",
    }
