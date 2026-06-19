from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_diag_link import build_cortex_diag_link


def test_diag_link_exposes_expected_units() -> None:
    registry = build_cortex_diag_link()

    assert sorted(registry) == [
        "runtime.facts",
        "runtime.probe",
        "surface.audit",
        "surface.manifest",
        "surfaces.list",
        "wiring.audit",
        "wiring.stages",
    ]
    assert all(unit.mutates_receipt is False for unit in registry.values())


def test_wiring_audit_runs_through_full_bundle() -> None:
    registry = build_cortex_bundle()
    payload = run_cortex_units(
        registry,
        [
            {
                "name": "wiring.audit",
                "kwargs": {"registry": registry},
            }
        ],
    )

    assert payload["bus_allowed"] is True
    audit = payload["results"][0]["output"]
    assert audit["architecture_ready"] is True
    assert audit["coverage"] == 1.0
    assert audit["operational_ready"] is False


def test_runtime_probe_runs_through_full_bundle(tmp_path) -> None:
    registry = build_cortex_bundle()
    payload = run_cortex_units(
        registry,
        [
            {
                "name": "runtime.probe",
                "kwargs": {"project_root": tmp_path},
            }
        ],
    )

    assert payload["bus_allowed"] is True
    probe = payload["results"][0]["output"]
    assert probe["filesystem_only"] is True
    assert probe["network_probe_performed"] is False


def test_surface_audit_runs_through_full_bundle() -> None:
    registry = build_cortex_bundle()
    payload = run_cortex_units(
        registry,
        [
            {
                "name": "surface.audit",
                "kwargs": {
                    "surface_id": "server",
                    "registry": registry,
                    "runtime_facts": {
                        "cli_entrypoint_available": True,
                        "service_packaging_available": False,
                    },
                },
            }
        ],
    )

    assert payload["bus_allowed"] is True
    audit = payload["results"][0]["output"]
    assert audit["contract_ready"] is True
    assert audit["usable_ready"] is True
    assert audit["native_ready"] is False
