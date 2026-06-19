import json

from hex_cortex.memory.cortex_gateway import build_cortex_adapter_registry
from hex_cortex.memory.cortex_gateway import run_cortex_adapter_gateway
from hex_cortex.memory.cortex_ollama_link import build_cortex_ollama_adapter
from hex_cortex.memory.cortex_policy import CortexMode


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(
            {"response": '{"status":"ok","summary":"ready"}'}
        ).encode("utf-8")


def test_ollama_adapter_runs_through_gateway(monkeypatch, tmp_path) -> None:
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request.full_url, timeout))
        return _Response()

    monkeypatch.setattr("hex_cortex.memory.cortex_r.urlopen", fake_urlopen)
    adapter = build_cortex_ollama_adapter()

    payload = run_cortex_adapter_gateway(
        tmp_path,
        route_record={
            "route_allowed": True,
            "route_hash": "route-hash",
            "lane": "tool",
        },
        adapter_receipt={
            "lane_allowed": True,
            "lane_receipt_hash": "receipt-hash",
        },
        adapter_name="local.ollama",
        adapter_registry=build_cortex_adapter_registry(adapter),
        request={"model": "qwen2.5-coder:7b-instruct"},
        execution_mode="execute",
        policy_mode=CortexMode.AUTO_SAFE,
        trusted_plan=True,
        network_allowed=True,
        idempotency_key="ollama-probe",
    )

    record = payload["gateway_records"][0]
    assert record["gateway_allowed"] is True
    assert record["execution_performed"] is True
    assert record["execution_completed"] is True
    assert record["result_summary"]["status"] == "ok"
    assert record["result_summary"]["summary_length"] == 5
    assert calls == [("http://127.0.0.1:11434/api/generate", 8.0)]
