from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_gateway import CortexAdapter
from hex_cortex.memory.cortex_gateway import build_cortex_adapter_registry
from hex_cortex.memory.cortex_xlink import build_cortex_xlink


def test_exec_call_accepts_serialized_policy_mode(tmp_path) -> None:
    adapter = CortexAdapter(
        name="local.output",
        lane="local_output",
        handler=lambda request: {"status": "ok"},
        description="local output",
    )
    payload = run_cortex_units(
        build_cortex_xlink(),
        [
            {
                "name": "exec.call",
                "kwargs": {
                    "profile": tmp_path,
                    "route_record": {
                        "route_allowed": True,
                        "route_hash": "route-hash",
                        "lane": "local_output",
                    },
                    "adapter_receipt": {
                        "lane_allowed": True,
                        "lane_receipt_hash": "receipt-hash",
                    },
                    "adapter_name": "local.output",
                    "adapter_registry": build_cortex_adapter_registry(adapter),
                    "request": {"task": "write"},
                    "execution_mode": "dry_run",
                    "policy_mode": "manual",
                },
            }
        ],
    )

    assert payload["bus_allowed"] is True
    record = payload["results"][0]["output"]["gateway_records"][0]
    assert record["policy_mode"] == "manual"
    assert record["execution_performed"] is False


def test_exec_call_rejects_unknown_serialized_mode(tmp_path) -> None:
    payload = run_cortex_units(
        build_cortex_xlink(),
        [
            {
                "name": "exec.call",
                "kwargs": {
                    "profile": tmp_path,
                    "route_record": {},
                    "adapter_receipt": {},
                    "adapter_name": "missing",
                    "adapter_registry": {},
                    "request": {},
                    "policy_mode": "unknown",
                },
            }
        ],
    )

    assert payload["bus_allowed"] is False
    assert payload["results"][0]["status"] == "failed"
    assert payload["results"][0]["error_type"] == "ValueError"
