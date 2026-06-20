import json
from pathlib import Path

from hex_cortex.memory.cortex_remote_api_smoke_cli import run_remote_api_smoke


def test_remote_smoke_persists_only_sanitized_receipt(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret-not-persisted")

    def transport(method, url, headers, payload, timeout_seconds):
        assert method == "POST"
        assert url == "https://api.openai.com/v1/responses"
        assert headers["Authorization"] == "Bearer test-secret-not-persisted"
        assert payload["max_output_tokens"] == 32
        assert timeout_seconds == 12.0
        return {"output_text": "HEX-CORTEX-REMOTE-SMOKE-OK"}

    output = tmp_path / "remote-api-smoke.json"
    evidence = tmp_path / "00-canonical-evidence.jsonl"
    payload = run_remote_api_smoke(
        model="test-model",
        api_key_ref="env:OPENAI_API_KEY",
        output_path=output,
        evidence_jsonl=evidence,
        timeout_seconds=12.0,
        operator_approved=True,
        transport=transport,
    )

    assert payload["status"] == "completed"
    assert payload["smoke_contract_passed"] is True
    assert payload["raw_secret_persisted"] is False
    assert payload["raw_response_persisted"] is False
    assert "volatile_result_text" not in payload
    persisted = output.read_text(encoding="utf-8")
    assert "test-secret-not-persisted" not in persisted
    assert "HEX-CORTEX-REMOTE-SMOKE-OK" not in persisted
    canonical = json.loads(evidence.read_text(encoding="utf-8").strip())
    assert canonical["receipt_type"] == "coding_model_execution_v1"
    assert canonical["provider_id"] == "remote_api"
    assert canonical["status"] == "completed"


def test_remote_smoke_fails_closed_without_approval(tmp_path: Path) -> None:
    payload = run_remote_api_smoke(
        model="test-model",
        api_key_ref="env:OPENAI_API_KEY",
        output_path=tmp_path / "remote.json",
        evidence_jsonl=tmp_path / "evidence.jsonl",
        operator_approved=False,
    )

    assert payload["status"] == "blocked"
    assert "operator_approval_required" in payload["blockers"]
    assert payload["model_call_performed"] is False
    assert payload["canonical_evidence_append"] is None


def test_remote_smoke_rejects_non_exact_result(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def transport(method, url, headers, payload, timeout_seconds):
        return {"output_text": "Almost correct"}

    payload = run_remote_api_smoke(
        model="test-model",
        api_key_ref="env:OPENAI_API_KEY",
        output_path=tmp_path / "remote.json",
        evidence_jsonl=tmp_path / "evidence.jsonl",
        operator_approved=True,
        transport=transport,
    )

    assert payload["status"] == "completed"
    assert payload["smoke_contract_passed"] is False
    assert "smoke_contract_mismatch" in payload["blockers"]
    assert payload["canonical_evidence_append"] is None
