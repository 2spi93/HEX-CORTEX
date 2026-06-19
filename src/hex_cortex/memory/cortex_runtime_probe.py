from __future__ import annotations

from pathlib import Path


def probe_cortex_runtime(
    project_root: Path,
    *,
    overrides: dict[str, bool] | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    memory_root = root / "src" / "hex_cortex" / "memory"
    research_compose = root / "deploy" / "research" / "docker-compose.yml"
    server_compose = root / "deploy" / "server" / "docker-compose.yml"
    caddyfile = root / "deploy" / "server" / "Caddyfile"
    evidence = {
        "cli_entrypoint_available": (memory_root / "cortex_cli.py").is_file(),
        "mcp_server_available": (
            (memory_root / "cortex_stdio.py").is_file()
            and (memory_root / "cortex_rpc.py").is_file()
            and (memory_root / "cortex_rpc_tools.py").is_file()
        ),
        "claude_project_configured": (root / ".mcp.json").is_file(),
        "codex_project_configured": (root / ".codex" / "config.toml").is_file(),
        "ollama_adapter_available": (memory_root / "cortex_ollama_link.py").is_file(),
        "llama_cpp_adapter_available": (memory_root / "cortex_openai_local.py").is_file(),
        "project_adapter_factory_available": (memory_root / "cortex_project_adapter.py").is_file(),
        "hardware_adapter_factory_available": (memory_root / "cortex_hardware_adapter.py").is_file(),
        "service_adapter_factory_available": (memory_root / "cortex_service_adapter.py").is_file(),
        "research_adapter_factory_available": (memory_root / "cortex_research_adapter.py").is_file(),
        "runtime_orchestration_available": (
            memory_root / "cortex_runtime_model_orchestration.py"
        ).is_file(),
        "research_social_credentials_available": (
            memory_root / "cortex_research_social_credentials.py"
        ).is_file(),
        "server_federation_audit_available": (
            memory_root / "cortex_server_federation_audit.py"
        ).is_file(),
        "server_worker_queue_available": (
            memory_root / "cortex_federation_queue.py"
        ).is_file(),
        "signed_task_envelopes_available": (
            memory_root / "cortex_server_federation_audit.py"
        ).is_file(),
        "remote_receipts_available": (
            memory_root / "cortex_server_federation_audit.py"
        ).is_file(),
        "hermes_autodiscovery_available": (
            memory_root / "cortex_server_federation_audit.py"
        ).is_file(),
        "gtixt_read_only_audit_available": (
            memory_root / "cortex_server_federation_audit.py"
        ).is_file(),
        "internal_api_available": (
            (memory_root / "cortex_server_api.py").is_file() and server_compose.is_file()
        ),
        "https_reverse_proxy_available": caddyfile.is_file(),
        "research_service_packaging_available": research_compose.is_file(),
        "service_packaging_available": server_compose.is_file() and caddyfile.is_file(),
        "media_runtime_contract_available": (
            memory_root / "cortex_media_runtime.py"
        ).is_file(),
        "latent_world_model_lab_available": (
            (memory_root / "cortex_latent_lab.py").is_file()
            and (memory_root / "cortex_latent_experiment.py").is_file()
        ),
        "world_model_training_evaluation_available": (
            memory_root / "cortex_world_model_eval.py"
        ).is_file(),
        "next_wave_cli_available": (
            memory_root / "cortex_next_wave_cli.py"
        ).is_file(),
    }
    facts: dict[str, bool] = {
        **evidence,
        "local_model_runtime_available": False,
        "ollama_endpoint_configured": False,
        "llama_server_endpoint_configured": False,
        "media_runtime_available": False,
        "comfyui_endpoint_configured": False,
        "web_search_adapter_configured": False,
        "hardware_adapter_available": False,
        "project_adapter_available": False,
        "hermes_adapter_available": False,
        "private_or_tunneled_transport_available": False,
        "kali_profile_configured": False,
        "learned_world_model_available": False,
    }
    if overrides is not None:
        if not all(
            isinstance(key, str) and isinstance(value, bool)
            for key, value in overrides.items()
        ):
            raise ValueError("runtime overrides must be boolean values")
        facts.update(overrides)
    true_facts = sorted(key for key, value in facts.items() if value)
    false_facts = sorted(key for key, value in facts.items() if not value)
    return {
        "probe_type": "cortex_runtime_probe",
        "project_root": str(root),
        "filesystem_only": True,
        "network_probe_performed": False,
        "process_probe_performed": False,
        "runtime_facts": facts,
        "true_fact_count": len(true_facts),
        "false_fact_count": len(false_facts),
        "true_facts": true_facts,
        "false_facts": false_facts,
        "next_action": "configure_external_runtimes" if false_facts else "run_operational_audit",
    }
