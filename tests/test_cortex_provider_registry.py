from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_provider_registry import build_cortex_provider_registry
from hex_cortex.memory.cortex_registry import build_cortex_registry


def test_provider_registry_exposes_providers_list() -> None:
    registry = build_cortex_provider_registry()

    assert sorted(registry) == ["providers.list"]
    unit = registry["providers.list"]
    assert unit.requires_operator is False
    assert unit.mutates_receipt is False


def test_provider_registry_combines_with_base_registry() -> None:
    registry = combine_cortex_registries(
        build_cortex_registry(),
        build_cortex_provider_registry(),
    )

    payload = run_cortex_units(
        registry,
        [{"name": "providers.list", "kwargs": {}}],
    )

    assert payload["bus_allowed"] is True
    rows = payload["results"][0]["output"]
    ids = {row["provider_id"] for row in rows}
    assert "browser_display" in ids
    assert "browser_camera" in ids
    assert "browser_microphone" in ids
