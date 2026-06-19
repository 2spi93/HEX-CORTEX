from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring
from hex_cortex.memory.cortex_wiring import list_cortex_runtime_facts
from hex_cortex.memory.cortex_wiring import list_cortex_wiring_stages


def test_wiring_audit_confirms_complete_static_architecture() -> None:
    payload = audit_cortex_wiring(build_cortex_bundle())

    assert payload["architecture_ready"] is True
    assert payload["coverage"] == 1.0
    assert payload["missing_units"] == []
    assert payload["missing_route_units"] == []
    assert payload["operational_ready"] is False
    assert "native_mcp_server_not_available" in payload["runtime_blockers"]
    assert "learned_world_model_not_available" in payload["runtime_blockers"]


def test_wiring_audit_can_reach_operational_ready() -> None:
    facts = {
        row["fact"]: True
        for row in list_cortex_runtime_facts()
    }

    payload = audit_cortex_wiring(
        build_cortex_bundle(),
        runtime_facts=facts,
    )

    assert payload["architecture_ready"] is True
    assert payload["operational_ready"] is True
    assert payload["runtime_blockers"] == []
    assert payload["next_action"] == "operate_cortex"


def test_wiring_audit_detects_missing_route_target() -> None:
    registry = build_cortex_bundle()
    registry.pop("voice.receipt")

    payload = audit_cortex_wiring(registry)

    assert payload["architecture_ready"] is False
    assert "voice.receipt" in payload["missing_units"]
    assert "voice.receipt" in payload["missing_route_units"]


def test_wiring_catalog_lists_all_stages_and_runtime_facts() -> None:
    stages = list_cortex_wiring_stages()
    facts = list_cortex_runtime_facts()

    assert {row["stage"] for row in stages} == {
        "local_model",
        "perception_and_state",
        "world_model_loop",
        "effect_receipts",
        "execution_gateway",
        "knowledge_and_integrations",
    }
    assert len(facts) == 7
