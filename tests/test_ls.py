import json

from hex_cortex.memory.ls import CORTEX_LOCAL_RUNTIME_PROBE_FILENAME
from hex_cortex.memory.ls import build_cortex_local_runtime_probe_dry_run
from hex_cortex.memory.ls import summarize_cortex_local_runtime_probe_dry_runs


def test_local_runtime_probe_dry_run_imports() -> None:
    assert CORTEX_LOCAL_RUNTIME_PROBE_FILENAME == "cortex-local-runtime-probe-dry-run.jsonl"


def test_local_runtime_probe_dry_run_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-local-model-backend-probe-contract.jsonl", _contract_row())

    payload = build_cortex_local_runtime_probe_dry_run(profile, expected_backend="ollama")

    record = payload["runtime_probe_dry_run_records"][0]
    assert record["runtime_probe_dry_run_allowed"] is True
    assert record["runtime_probe_dry_run_decision"] == "local_runtime_probe_dry_run_ready"
    assert record["selected_backend"] == "ollama"
    assert record["selected_model"] == "qwen2.5-coder:7b-instruct"
    assert record["runtime_binding"] == "none_probe_dry_run_only"
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["local_probe_performed"] is False
    assert record["repo_mutation_performed"] is False
    assert record["shell_execution_performed"] is False
    assert record["prompt_material_persisted"] is False
    assert record["raw_response_persisted"] is False
    assert record["planned_probe"]["operator_execution_required"] is True
    assert record["next_action"] == "ready_for_operator_local_probe_execution"

    summary = summarize_cortex_local_runtime_probe_dry_runs(
        profile / CORTEX_LOCAL_RUNTIME_PROBE_FILENAME
    )
    assert summary["latest_runtime_probe_dry_run_allowed"] is True
    assert summary["latest_selected_backend"] == "ollama"


def test_local_runtime_probe_dry_run_blocks_non_local_base_url(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    row = _contract_row()
    row["probe_contract"]["base_url"] = "https://example.invalid/v1"
    _write_jsonl(profile / "cortex-local-model-backend-probe-contract.jsonl", row)

    payload = build_cortex_local_runtime_probe_dry_run(profile)

    record = payload["runtime_probe_dry_run_records"][0]
    assert record["runtime_probe_dry_run_allowed"] is False
    assert "base_url_not_localhost" in record["blockers"]


def _contract_row() -> dict[str, object]:
    return {
        "probe_contract_allowed": True,
        "contract_hash": "probe-contract-hash",
        "runtime_binding": "none_probe_contract_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "local_probe_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "next_action": "prepare_local_model_backend_probe_dry_run",
        "probe_contract": {
            "backend_kind": "ollama",
            "model_name": "qwen2.5-coder:7b-instruct",
            "base_url": "http://127.0.0.1:11434",
            "model_path": None,
            "probe_mode": "metadata_or_health_only",
            "allowed_probe_surface": "localhost_http_only",
            "max_probe_timeout_seconds": 8.0,
            "prompt_allowed": False,
            "completion_allowed": False,
            "repo_mutation_allowed": False,
            "shell_execution_allowed": False,
            "persist_raw_response": False,
        },
    }


def _write_jsonl(path, row) -> None:
    path.write_text(json.dumps(rG&÷rÂ6÷'Eö¶W—3ÕG'VR’²%Æâ"ÂVæ6öF–æsÒ'WFbÓ‚"