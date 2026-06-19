import hashlib
from pathlib import Path

from hex_cortex.memory.cortex_hermes_executor_adapter import build_hermes_executor_plan
from hex_cortex.memory.cortex_hermes_executor_adapter import verify_hermes_result
from hex_cortex.memory.cortex_server_federation_audit import build_signed_task_envelope


def _envelope(key: bytes) -> dict[str, object]:
    return build_signed_task_envelope(
        issuer="hex-cortex",
        target="hermes.server",
        capability="code.plan",
        payload_ref="profile://task-1.json",
        payload_hash=hashlib.sha256(b"task").hexdigest(),
        signing_key=key,
    )


def test_hermes_executor_plan_preserves_memory_separation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    worktrees = tmp_path / "worktrees"
    key = b"test-key"

    plan = build_hermes_executor_plan(
        envelope=_envelope(key),
        signing_key=key,
        repository_root=repo,
        worktree_root=worktrees,
        hermes_version="0.16.0",
        transport="mcp",
    )

    assert plan["status"] == "ready"
    assert plan["memory_policy"] == "separate_no_merge"
    assert plan["raw_memory_exchange_allowed"] is False
    assert plan["execution_performed"] is False


def test_write_capability_requires_operator_approval(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    key = b"test-key"
    envelope = build_signed_task_envelope(
        issuer="hex-cortex",
        target="hermes.server",
        capability="code.propose_patch",
        payload_ref="profile://task-2.json",
        payload_hash=hashlib.sha256(b"task-2").hexdigest(),
        signing_key=key,
    )

    plan = build_hermes_executor_plan(
        envelope=envelope,
        signing_key=key,
        repository_root=repo,
        worktree_root=tmp_path / "worktrees",
        hermes_version="0.16.0",
        operator_approved=False,
    )

    assert plan["status"] == "blocked"
    assert "operator_approval_required" in plan["blockers"]


def test_hermes_result_verification_rejects_memory_violation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    key = b"test-key"
    envelope = _envelope(key)
    plan = build_hermes_executor_plan(
        envelope=envelope,
        signing_key=key,
        repository_root=repo,
        worktree_root=tmp_path / "worktrees",
        hermes_version="0.16.0",
    )

    receipt = verify_hermes_result(
        plan=plan,
        result={
            "envelope_id": envelope["envelope_id"],
            "status": "completed",
            "memory_policy": "merged",
            "raw_memory_persisted": True,
            "raw_secret_persisted": False,
        },
    )

    assert receipt["status"] == "blocked"
    assert receipt["merge_allowed"] is False
    assert "hermes_memory_policy_violation" in receipt["blockers"]
