from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_project_fit import analyze_cortex_project_fit
from hex_cortex.memory.cortex_wave3_link import build_cortex_wave3_link
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring


def test_wave3_link_exposes_expected_units() -> None:
    registry = build_cortex_wave3_link()

    assert set(registry) == {
        "runtime.targets",
        "runtime.health",
        "runtime.select",
        "runtime.benchmark.plan",
        "research.flow",
        "auth.ref.build",
        "auth.ref.register",
        "connectors.list",
        "connector.plan",
        "bridge.transports",
        "bridge.detect",
        "exchange.build",
        "exchange.verify",
        "project.fit",
        "service.profile",
        "service.caddy",
    }
    assert registry["runtime.health"].mutates_receipt is False
    assert registry["auth.ref.register"].mutates_receipt is True
    assert registry["exchange.build"].mutates_receipt is True


def test_full_bundle_contains_wave3_units_and_remains_complete() -> None:
    registry = build_cortex_bundle()
    audit = audit_cortex_wiring(registry)

    assert set(build_cortex_wave3_link()).issubset(registry)
    assert audit["architecture_ready"] is True
    assert audit["coverage"] == 1.0
    stage = next(
        row
        for row in audit["stage_rows"]
        if row["stage"] == "external_runtime_integrations"
    )
    assert stage["present_count"] == 16
    assert stage["missing_count"] == 0


def test_project_fit_uses_federation_when_capabilities_overlap() -> None:
    payload = analyze_cortex_project_fit(
        project_id="gtixt",
        existing_capabilities=["predictor", "evidence", "publication"],
        proposed_capabilities=["predictor", "research", "multimodal"],
    )

    assert payload["integration_mode"] == "federated_read_only"
    assert payload["overlapping_capabilities"] == ["predictor"]
    assert payload["extension_capabilities"] == ["multimodal", "research"]
    assert payload["shared_memory"] is False
    assert payload["project_remains_source_of_truth"] is True
