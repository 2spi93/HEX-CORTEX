from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_provider_extra import (
    build_cortex_provider_extra_registry,
)
from hex_cortex.memory.cortex_provider_registry import build_cortex_provider_registry


def test_provider_extra_registry_exposes_score_and_select() -> None:
    registry = build_cortex_provider_extra_registry()

    assert sorted(registry) == ["providers.score", "providers.select"]


def test_provider_registry_runs_list_score_and_select() -> None:
    registry = combine_cortex_registries(
        build_cortex_provider_registry(),
        build_cortex_provider_extra_registry(),
    )
    plan = [
        {"name": "providers.list", "kwargs": {}},
        {"name": "providers.score", "kwargs": {"provider_id": "browser_camera"}},
        {
            "name": "providers.select",
            "kwargs": {
                "capability_id": "screen_vision",
                "prefer_local": True,
            },
        },
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 3
    assert payload["result_count"] == 3
    assert payload["results"][1]["output"]["score"] == 100.0
    assert payload["results"][2]["output"]["provider_id"] == "local_image_file"
