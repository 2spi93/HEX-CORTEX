"""Gateway effects are reserved durably and fail closed on uncertain outcomes."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from hex_cortex.memory import cortex_gateway as gateway
from hex_cortex.memory.cortex_gateway import (
    CORTEX_GATEWAY_FILENAME,
    CortexAdapter,
    build_cortex_adapter_registry,
    run_cortex_adapter_gateway,
    summarize_cortex_gateway,
)
from hex_cortex.memory.cortex_policy import CortexMode


def _kwargs(handler, *, timeout_seconds: float = 1.0):
    adapter = CortexAdapter(
        name="operator.action", lane="local_output",
        handler=handler, description="explicitly approved local mock",
        timeout_seconds=timeout_seconds,
    )
    return {
        "route_record": {"route_allowed": True, "route_hash": "r", "lane": "local_output"},
        "adapter_receipt": {"lane_allowed": True, "lane_receipt_hash": "a"},
        "adapter_name": "operator.action",
        "adapter_registry": build_cortex_adapter_registry(adapter),
        "request": {"action": "read_only_simulation"},
        "execution_mode": "execute",
        "policy_mode": CortexMode.MANUAL,
        "operator_approved": True,
        "idempotency_key": "stable-operation",
    }


def test_handler_sees_durable_inflight_receipt_first(tmp_path: Path) -> None:
    observed = []
    def mock_handler(request):
        rows = gateway._load(tmp_path / CORTEX_GATEWAY_FILENAME)
        observed.append(rows[-1])
        return {"status": "ok", "summary": "done"}

    result = run_cortex_adapter_gateway(tmp_path, **_kwargs(mock_handler))
    assert len(observed) == 1
    assert observed[0]["gateway_status"] == "in_flight"
    assert observed[0]["execution_completed"] is False
    assert "reconcile_unknown_external_effect_before_retry" == observed[0]["next_action"]
    assert result["gateway_count"] == 1
    assert result["gateway_records"][0]["execution_completed"] is True
    assert len(gateway._load(tmp_path / CORTEX_GATEWAY_FILENAME)) == 1


def test_interrupted_handler_is_not_retried_after_crash(tmp_path: Path) -> None:
    calls = []
    def interrupted(request):
        calls.append("called")
        raise KeyboardInterrupt("simulate fatal process exit")

    kwargs = _kwargs(interrupted)
    with pytest.raises(KeyboardInterrupt):
        run_cortex_adapter_gateway(tmp_path, **kwargs)
    previous = gateway._load(tmp_path / CORTEX_GATEWAY_FILENAME)
    assert len(previous) == 1
    assert previous[0]["gateway_status"] == "in_flight"
    assert not (tmp_path / (CORTEX_GATEWAY_FILENAME + ".write-lock")).exists()

    def must_not_call(request):
        calls.append("RERUN")
        raise AssertionError("must not retry uncertain effect")
    kwargs["adapter_registry"] = build_cortex_adapter_registry(
        CortexAdapter(
            name="operator.action", lane="local_output",
            description="mock", handler=must_not_call,
        )
    )
    second = run_cortex_adapter_gateway(tmp_path, **kwargs)
    assert second["gateway_count"] == 1
    assert second["gateway_records"][0]["gateway_status"] == "in_flight"
    assert second["gateway_records"][0]["execution_completed"] is False
    assert calls == ["called"]


def test_over_budget_handler_cannot_be_reported_as_success(tmp_path: Path) -> None:
    def slow(request):
        time.sleep(0.025)
        return {"status": "ok", "summary": "delayed"}
    result = run_cortex_adapter_gateway(
        tmp_path, **_kwargs(slow, timeout_seconds=0.005)
    )
    row = result["gateway_records"][0]
    assert row["gateway_allowed"] is True
    assert row["execution_performed"] is True
    assert row["execution_completed"] is False
    assert "adapter_time_budget_exceeded" in row["blockers"]
    assert row["next_action"] == "repair_adapter_execution"


def test_intent_write_failure_prevents_adapter_call(tmp_path: Path, monkeypatch) -> None:
    calls = []
    def handler(request):
        calls.append("side-effect")
        return {"status": "ok"}

    def write_fails(path, lines):
        raise OSError("simulated disk failure")

    monkeypatch.setattr(gateway, "atomic_jsonl_snapshot", write_fails)
    with pytest.raises(OSError, match="simulated disk failure"):
        run_cortex_adapter_gateway(tmp_path, **_kwargs(handler))
    assert calls == []
    assert not (tmp_path / (CORTEX_GATEWAY_FILENAME + ".write-lock")).exists()


def test_preexisting_writer_lock_denies_execution(tmp_path: Path) -> None:
    lock = tmp_path / (CORTEX_GATEWAY_FILENAME + ".write-lock")
    lock.mkdir()
    calls = []
    with pytest.raises(ValueError, match="writer_already_active"):
        run_cortex_adapter_gateway(
            tmp_path, **_kwargs(lambda _: calls.append("unsafe"))
        )
    assert calls == []
    assert lock.exists()


def test_gateway_summary_handles_inflight_after_restart(tmp_path: Path) -> None:
    record = {
        "gateway_hash": "hash",
        "gateway_status": "in_flight",
        "execution_performed": False,
        "execution_completed": False,
        "next_action": "reconcile_unknown_external_effect_before_retry",
    }
    path = tmp_path / CORTEX_GATEWAY_FILENAME
    with gateway.exclusive_jsonl_writer(path):
        gateway.atomic_jsonl_snapshot(path, [json.dumps(record)])
    report = summarize_cortex_gateway(path)
    assert report["latest_execution_completed"] is False
    assert report["latest_next_action"] == "reconcile_unknown_external_effect_before_retry"
