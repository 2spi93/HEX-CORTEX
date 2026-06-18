import json

from hex_cortex.memory.cortex_local_runtime_contract import (
    CORTEX_LOCAL_MODEL_BACKEND_PROBE_CONTRACT_FILENAME,
)
from hex_cortex.memory.cortex_local_runtime_contract import (
    build_cortex_local_model_backend_probe_contract,
)
from hex_cortex.memory.cortex_local_runtime_contract import (
    summarize_cortex_local_model_backend_probe_contracts,
)


def test_local_runtime_contract_imports() -> None:
    assert (
        CORTEX_LOCAL_MODEL_BACKEND_PROBE_CONTRACT_FILENAME
        == "cortex-local-model-backend-probe-contract.jsonl"
    )


def test_local_runtime_contract_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-local-model-backend-config-dry-run.jsonl", _dry_run_row())

    payload = build_cortex_local_model_backend_probe_contract(
        profile,
        expected_backend="ollama",
    )

    record = payload["probe_contract_records"][0]
    assert record["probe_contract_allowed"] is True
    assert record["probe_contract_decision"] == "local_model_backend_probe_contract_ready"
    assert record["selected_backend"] == "ollama"
    assert record["selected_model"] == "qwen2.5-coder:7b-instruct"
    assert record["runtime_binding"] == "none_probe_contract_only"
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["local_probe_performed"] is False
    assert record["repo_mutation_performed"] is False
    assert record["shell_execution_performed"] is False
    assert record["probe_contract"]["prompt_allowed"] is False
    assert record["probe_contract"]["completion_allowed"] is False
    assert record["next_action"] == "prepare_local_model_backend_probe_dry_run"

    summary = summarize_cortex_local_model_backend_probe_contracts(
        profile / CORTEX_LOCAL_MODEL_BACKEND_PROBE_CONTRACT_FILENAME
    )
    assert summary["latest_probe_contract_allowed"] is True
    assert summary["latest_selected_backend"] == "ollama"


def test_local_runtime_contract_blocks_non_local_base_url(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    row = _dry_run_row()
    row["validated_config"]["base_url"] = "https://example.invalid/v1"
    _write_jsonl(profile / "cortex-local-model-backend-config-dry-run.jsonl", row)

    payload = build_cortex_local_model_backend_probe_contract(profile)

    record = payload["probe_contract_records"][0]
    assert record["probe_contract_allowed"] is False
    assert "base_url_not_localhost" in record["blockers"]


def _dry_run_row() -> dict[str, object]:
    return {
        "config_dry_run_allowed": True,
        "config_dry_run_hash": "config-dry-run-hash",
        "validated_config_hash": "validated-config-hash",
        "runtime_binding": "none_config_dry_run_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "local_probe_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "next_action": "prepare_local_model_backend_probe_contract",
        "validated_config": {
            "backend_kind": "ollama",
            "model_name": "qwen2.5-coder:7b-instruct",
            "base_url": "http://127.0.0.1:11434",
            "model_path": None,
            "context_window": 4096,
            "max_output_tokens": 768,
            "temperature": 0.2,
            "timeout_seconds": 8.0,
            "localhost_only": True,
            "repo_mutation_allowed": False,
            "shell_execution_allowed": False,
            "network_required": True,
        },
    }


def _write_jsonl(path, row) -> None:
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
