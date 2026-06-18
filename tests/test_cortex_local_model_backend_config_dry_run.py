import json

from hex_cortex.memory.cortex_local_model_backend_config_dry_run import (
    CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME,
)
from hex_cortex.memory.cortex_local_model_backend_config_dry_run import (
    build_cortex_local_model_backend_config_dry_run,
)
from hex_cortex.memory.cortex_local_model_backend_config_dry_run import (
    summarize_cortex_local_model_backend_config_dry_runs,
)


def test_local_model_backend_config_dry_run_imports() -> None:
    assert (
        CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME
        == "cortex-local-model-backend-config-dry-run.jsonl"
    )


def test_local_model_backend_config_dry_run_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(profile / "cortex-local-model-backend-config-plan.jsonl", _plan_row())

    payload = build_cortex_local_model_backend_config_dry_run(
        profile,
        expected_backend="ollama",
    )

    record = payload["config_dry_run_records"][0]
    assert record["config_dry_run_allowed"] is True
    assert record["config_dry_run_decision"] == "local_model_backend_config_dry_run_ready"
    assert record["selected_backend"] == "ollama"
    assert record["selected_model"] == "qwen2.5-coder:7b-instruct"
    assert record["runtime_binding"] == "none_config_dry_run_only"
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["local_probe_performed"] is False
    assert record["repo_mutation_performed"] is False
    assert record["shell_execution_performed"] is False
    assert record["next_action"] == "prepare_local_model_backend_probe_contract"

    summary = summarize_cortex_local_model_backend_config_dry_runs(
        profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_DRY_RUN_FILENAME
    )
    assert summary["latest_config_dry_run_allowed"] is True
    assert summary["latest_selected_backend"] == "ollama"


def test_local_model_backend_config_dry_run_blocks_remote_base_url(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    row = _plan_row()
    row["config_preview"]["base_url"] = "https://example.invalid/v1"
    _write_jsonl(profile / "cortex-local-model-backend-config-plan.jsonl", row)

    payload = build_cortex_local_model_backend_config_dry_run(profile)

    record = payload["config_dry_run_records"][0]
    assert record["config_dry_run_allowed"] is False
    assert "base_url_localhost_only" in record["blockers"]


def _plan_row() -> dict[str, object]:
    return {
        "config_plan_allowed": True,
        "config_plan_hash": "config-plan-hash",
        "runtime_binding": "none_config_plan_only",
        "model_call_performed": False,
        "network_call_performed": False,
        "repo_mutation_performed": False,
        "shell_execution_performed": False,
        "next_action": "prepare_local_model_backend_config_dry_run",
        "config_preview": {
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
