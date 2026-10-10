"""No-model architecture readiness regression tests."""

from __future__ import annotations

import json

from hex_cortex.memory.cortex_offline_readiness_v5 import main, offline_readiness


def test_offline_readiness_needs_no_llm_benchmark_or_network(monkeypatch, capsys):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = offline_readiness()
    assert report["status"] == "passed"
    assert all(report["checks"].values())
    assert report["local_model_required"] is False
    assert report["benchmark_executed"] is False
    assert report["remote_provider_called"] is False
    assert report["api_credentials_required"] is False
    assert report["checkout_modified"] is False
    assert report["production_ready"] is False
    assert main(["--pretty"]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["check_type"] == "hex_cortex_offline_architecture_smoke_v5"
