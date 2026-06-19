import pytest

from hex_cortex.memory.cortex_gateway import CORTEX_GATEWAY_FILENAME
from hex_cortex.memory.cortex_gateway import CortexAdapter
from hex_cortex.memory.cortex_gateway import build_cortex_adapter_registry
from hex_cortex.memory.cortex_gateway import list_cortex_adapters
from hex_cortex.memory.cortex_gateway import run_cortex_adapter_gateway
from hex_cortex.memory.cortex_gateway import summarize_cortex_gateway
from hex_cortex.memory.cortex_policy import CortexMode


def test_adapter_registry_is_schema_only() -> None:
    adapter = _adapter(handler=lambda request: {"status": "ok"})
    registry = build_cortex_adapter_registry(adapter)

    rows = list_cortex_adapters(registry)

    assert len(rows) == 1
    assert rows[0]["name"] == "local.output"
    assert rows[0]["handler_exposed"] is False
    assert rows[0]["timeout_seconds"] == 8.0


def test_adapter_registry_rejects_duplicates_and_invalid_timeout() -> None:
    adapter = _adapter(handler=lambda request: {"status": "ok"})
    with pytest.raises(ValueError, match="duplicate adapter"):
        build_cortex_adapter_registry(adapter, adapter)
    with pytest.raises(ValueError, match="timeout_seconds"):
        build_cortex_adapter_registry(
            _adapter(
                handler=lambda request: {"status": "ok"},
                timeout_seconds=0.0,
            )
        )


def test_gateway_dry_run_never_calls_adapter(tmp_path) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return {"status": "ok"}

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=build_cortex_adapter_registry(
            _adapter(handler=handler)
        ),
        request={"task": "write"},
        execution_mode="dry_run",
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is True
    assert record["execution_performed"] is False
    assert record["execution_completed"] is False
    assert record["result_summary"]["status"] == "not_run"
    assert record["next_action"] == "execute_registered_adapter"
    assert calls == []


def test_gateway_manual_execution_requires_approval(tmp_path) -> None:
    registry = build_cortex_adapter_registry(
        _adapter(handler=lambda request: {"status": "ok"})
    )

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=registry,
        request={"task": "write"},
        execution_mode="execute",
        policy_mode=CortexMode.MANUAL,
        operator_approved=False,
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is False
    assert "manual_execution_requires_operator" in record["blockers"]
    assert record["execution_performed"] is False


def test_gateway_executes_registered_adapter_with_approval(tmp_path) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return {
            "status": "ok",
            "summary": "written",
            "external_effect_performed": True,
        }

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=build_cortex_adapter_registry(
            _adapter(handler=handler)
        ),
        request={"task": "write"},
        execution_mode="execute",
        policy_mode=CortexMode.MANUAL,
        operator_approved=True,
        idempotency_key="write-once",
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is True
    assert record["execution_performed"] is True
    assert record["execution_completed"] is True
    assert record["external_effect_performed"] is True
    assert record["result_summary"]["summary_length"] == 7
    assert record["raw_result_persisted"] is False
    assert calls == [{"task": "write"}]


def test_gateway_auto_safe_requires_trusted_capable_adapter(tmp_path) -> None:
    registry = build_cortex_adapter_registry(
        _adapter(
            handler=lambda request: {"status": "ok"},
            auto_safe_capable=False,
        )
    )

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=registry,
        request={"task": "write"},
        execution_mode="execute",
        policy_mode=CortexMode.AUTO_SAFE,
        trusted_plan=False,
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is False
    assert "auto_safe_requires_trusted_plan" in record["blockers"]
    assert "adapter_not_auto_safe_capable" in record["blockers"]


def test_gateway_enforces_network_and_process_permissions(tmp_path) -> None:
    adapter = CortexAdapter(
        name="remote.asset",
        lane="asset",
        handler=lambda request: {"status": "ok"},
        description="remote asset adapter",
        network_capable=True,
        local_process_capable=True,
        auto_safe_capable=True,
    )

    blocked = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(lane="asset"),
        adapter_receipt={
            "media_receipt_allowed": True,
            "media_receipt_hash": "media-hash",
        },
        adapter_name="remote.asset",
        adapter_registry=build_cortex_adapter_registry(adapter),
        request={"task": "render"},
        execution_mode="execute",
        policy_mode=CortexMode.AUTO_SAFE,
        trusted_plan=True,
    )["gateway_records"][0]

    assert blocked["gateway_allowed"] is False
    assert "network_permission_required" in blocked["blockers"]
    assert "local_process_permission_required" in blocked["blockers"]


def test_gateway_blocks_lane_mismatch(tmp_path) -> None:
    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(lane="tool"),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=build_cortex_adapter_registry(
            _adapter(handler=lambda request: {"status": "ok"})
        ),
        request={"task": "write"},
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is False
    assert "adapter_lane_mismatch" in record["blockers"]


def test_gateway_redacts_secret_values_and_is_idempotent(tmp_path) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return {"status": "ok", "summary": "done"}

    kwargs = {
        "route_record": _route(),
        "adapter_receipt": _receipt(),
        "adapter_name": "local.output",
        "adapter_registry": build_cortex_adapter_registry(
            _adapter(handler=handler)
        ),
        "request": {"task": "write"},
        "execution_mode": "execute",
        "policy_mode": CortexMode.MANUAL,
        "operator_approved": True,
        "secret_refs": {"API_TOKEN": "super-secret"},
        "idempotency_key": "same-effect",
    }

    first = run_cortex_adapter_gateway(tmp_path, **kwargs)
    second = run_cortex_adapter_gateway(tmp_path, **kwargs)

    first_record = first["gateway_records"][0]
    second_record = second["gateway_records"][0]
    assert first["gateway_count"] == 1
    assert second["gateway_count"] == 1
    assert first_record["gateway_hash"] == second_record["gateway_hash"]
    assert first_record["secret_ref_names"] == ["API_TOKEN"]
    assert first_record["secret_values_persisted"] is False
    assert "super-secret" not in str(first_record)
    assert calls == [{"task": "write"}]


def test_gateway_captures_adapter_exception(tmp_path) -> None:
    def handler(request):
        raise RuntimeError("boom")

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record=_route(),
        adapter_receipt=_receipt(),
        adapter_name="local.output",
        adapter_registry=build_cortex_adapter_registry(
            _adapter(handler=handler)
        ),
        request={"task": "write"},
        execution_mode="execute",
        policy_mode=CortexMode.MANUAL,
        operator_approved=True,
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is True
    assert record["execution_performed"] is True
    assert record["execution_completed"] is False
    assert record["result_summary"]["error_type"] == "RuntimeError"
    assert record["next_action"] == "repair_adapter_execution"

    summary = summarize_cortex_gateway(tmp_path / CORTEX_GATEWAY_FILENAME)
    assert summary["latest_execution_completed"] is False


def _adapter(
    *,
    handler,
    timeout_seconds: float = 8.0,
    auto_safe_capable: bool = True,
) -> CortexAdapter:
    return CortexAdapter(
        name="local.output",
        lane="local_output",
        handler=handler,
        description="local output adapter",
        auto_safe_capable=auto_safe_capable,
        timeout_seconds=timeout_seconds,
    )


def _route(*, lane: str = "local_output") -> dict[str, object]:
    return {
        "route_allowed": True,
        "route_hash": "route-hash",
        "lane": lane,
    }


def _receipt() -> dict[str, object]:
    return {
        "lane_allowed": True,
        "lane_receipt_hash": "lane-receipt-hash",
    }
