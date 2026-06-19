from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_surfaces import audit_cortex_surface
from hex_cortex.memory.cortex_surfaces import build_cortex_surface_manifest
from hex_cortex.memory.cortex_surfaces import list_cortex_surfaces


def test_target_catalog_has_ten_entries() -> None:
    rows = list_cortex_surfaces()

    assert len(rows) == 10
    assert {row["surface_id"] for row in rows} == {
        "claude_code",
        "codex_cli",
        "ollama",
        "llama_cpp",
        "hermes_agent",
        "kali_linux",
        "server",
        "hardware_edge",
        "gtixt",
        "generic_project",
    }


def test_all_target_contracts_are_connected() -> None:
    registry = build_cortex_bundle()

    for row in list_cortex_surfaces():
        payload = audit_cortex_surface(
            surface_id=str(row["surface_id"]),
            registry=registry,
        )
        assert payload["contract_ready"] is True
        assert payload["missing_units"] == []


def test_fallback_can_be_ready_before_preferred_transport() -> None:
    payload = audit_cortex_surface(
        surface_id="claude_code",
        registry=build_cortex_bundle(),
        runtime_facts={
            "cli_entrypoint_available": True,
            "claude_project_configured": True,
            "mcp_server_available": False,
        },
    )

    assert payload["usable_ready"] is True
    assert payload["native_ready"] is False
    assert payload["next_action"] == "configure_surface_native_transport"


def test_local_runtime_target_can_be_ready() -> None:
    payload = audit_cortex_surface(
        surface_id="ollama",
        registry=build_cortex_bundle(),
        runtime_facts={
            "local_model_runtime_available": True,
            "ollama_endpoint_configured": True,
        },
    )

    assert payload["contract_ready"] is True
    assert payload["usable_ready"] is True
    assert payload["native_ready"] is True


def test_target_manifest_has_no_raw_secrets() -> None:
    payload = build_cortex_surface_manifest("gtixt")

    assert payload["raw_secrets_in_manifest"] is False
    assert payload["secrets_must_use_environment_or_secret_store"] is True
    assert payload["instruction_file"] == "AGENTS.md"


def test_unknown_target_blocks() -> None:
    payload = audit_cortex_surface(
        surface_id="unknown",
        registry=build_cortex_bundle(),
    )

    assert payload["contract_ready"] is False
    assert payload["blockers"] == ["unknown_surface"]
