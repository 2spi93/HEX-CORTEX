import json

from hex_cortex.memory.cortex_local_model_backend_config_plan import (
    CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME,
)
from hex_cortex.memory.cortex_local_model_backend_config_plan import (
    build_cortex_local_model_backend_config_plan,
)
from hex_cortex.memory.cortex_local_model_backend_config_plan import (
    summarize_cortex_local_model_backend_config_plans,
)


def test_local_model_backend_config_plan_imports() -> None:
    assert CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME == "cortex-local-model-backend-config-plan.jsonl"


def test_local_model_backend_config_plan_ready(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    _write_jsonl(
        profile / "cortex-local-model-advice.jsonl",
        {
            "advice_allowed": True,
            "next_action": "prepare_local_model_backend_config_plan",
            "model_call_performed": False,
            "repo_mutation_performed": False,
            "record_hash": "advice-hash",
            "advice_hash": "payload-hash",
        },
    )
    _write_jsonl(
        profile / "cortex-local-model-backend-adapter-contract.jsonl",
        {
            "contract_allowed": True,
            "default_backend": "mock",
            "supported_initial_backends": ["mock", "ollama", "llama_cpp", "local_openai_compatible_api"],
            "contract_hash": "contract-hash",
        },
    )

    payload = build_cortex_local_model_backend_config_plan(
        profile,
        preferred_backend="ollama",
        model_name="qwen2.5-coder:7b-instruct",
    )

    record = payload["config_plan_records"][0]
    assert record["config_plan_allowed"] is True
    assert record["config_plan_decision"] == "local_model_backend_config_plan_ready"
    assert record["selected_backend"] == "ollama"
    assert record["model_call_performed"] is False
    assert record["network_call_performed"] is False
    assert record["repo_mutation_performed"] is False
    assert record["next_action"] == "prepare_local_model_backend_config_dry_run"

    summary = summarize_cortex_local_model_backend_config_plans(
        profile / CORTEX_LOCAL_MODEL_BACKEND_CONFIG_PLAN_FILENAME
    )
    assert summary["latest_config_plan_allowed"] is True
    assert summary["latest_selected_backend"] == "ollama"


def test_local_model_backend_config_plan_blocks_unknown_backend(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()

    payload = build_cortex_local_model_backend_config_plan(profile, preferred_backend="remote_cloud")

    record = payload["config_plan_records"][0]
    assert record["config_plan_allowed"] is False
    assert "unsupported_preferred_backend" in record["blockers"]


def _write_jsonl(path, row) -> None:
    path.write_text(json.dumps(row, sort_keys=True) + "\n", encoding="utf-8")
