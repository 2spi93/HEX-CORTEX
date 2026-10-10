"""Model-free architecture readiness smoke: zero API calls, zero benchmarks.

The checks verify wiring and fail-closed contracts, NOT production readiness.
Only the OS temporary directory is used; no project files are modified.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from collections.abc import Sequence
from pathlib import Path

from hex_cortex.memory.cortex_cloud_brain_v5 import CloudBrain
from hex_cortex.memory.cortex_local_cognitive_cycle import run_clocked_local_task
from hex_cortex.memory.cortex_local_harness_v2 import (
    Budget,
    Capability,
    LocalHarness,
    Session,
    Task,
    build_readonly_harness,
)


def offline_readiness() -> dict[str, object]:
    checks: dict[str, bool] = {}
    with tempfile.TemporaryDirectory(prefix="hex-cortex-offline-") as folder:
        root = Path(folder)
        (root / "README.md").write_text("model-free smoke only", encoding="utf-8")
        harness = build_readonly_harness(root, session_id="offline-readiness")
        denied = run_clocked_local_task(
            harness,
            Task("read-denied", "repo_read", "Do not read", "repo_manifest"),
            approved=False,
        )
        checks["unapproved_tool_denied"] = (
            denied["status"] == "blocked" and denied["reason"] == "tool_not_authorized"
        )
        approved = run_clocked_local_task(
            harness,
            Task("read-approved", "repo_read", "Inventory only", "repo_manifest"),
            approved=True,
        )
        checks["approved_read_only_manifest"] = (
            approved["status"] == "complete"
            and approved["tool_result"] == {
                "project_id": "HEX-CORTEX", "manifest": ["README.md"]
            }
        )
        checks["canonical_spine_integrity"] = harness.verify_replay()
        model_harness = LocalHarness(
            Session("model-free", root),
            grants=frozenset({Capability.CALL_MODEL}),
            budget=Budget(max_model_calls=1, max_tool_calls=0),
        )
        calls: list[str] = []

        def fake_brain(model: str, task: Task) -> str:
            calls.append(model)
            return "simulated answer"

        decision = run_clocked_local_task(
            model_harness, Task("mock", "coding", "Simulated input"),
            models=["fake-provider"], brain=fake_brain, approved=True,
        )
        checks["provider_independent_clock"] = (
            decision["status"] == "complete"
            and decision["canonical_spine_verified"] is True
            and calls == ["fake-provider"]
        )
        checks["redacted_receipts"] = (
            "Simulated input" not in json.dumps(model_harness.receipts)
            and "simulated answer" not in json.dumps(model_harness.receipts)
            and model_harness.verify_replay()
        )
    # Constructors only; neither provider is contacted or authenticated.
    checks["cloud_adapter_interfaces"] = (
        CloudBrain("openai").api_key_variable == "OPENAI_API_KEY"
        and CloudBrain("anthropic").api_key_variable == "ANTHROPIC_API_KEY"
    )
    return {
        "check_type": "hex_cortex_offline_architecture_smoke_v5",
        "status": "passed" if all(checks.values()) else "failed",
        "checks": checks,
        "local_model_required": False,
        "benchmark_executed": False,
        "remote_provider_called": False,
        "api_credentials_required": False,
        "checkout_modified": False,
        "production_ready": False,
        "reason_production_not_certified": (
            "offline wiring and unit tests cannot certify remote provider access "
            "or end-to-end autonomous project execution"
        ),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="hexcortex-readiness")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)
    report = offline_readiness()
    print(json.dumps(report, sort_keys=True, indent=2 if args.pretty else None))
    return 0 if report["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
