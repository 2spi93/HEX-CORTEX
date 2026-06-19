from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_ext3 import build_cortex_ext3


def test_extension_units_are_connected() -> None:
    registry = build_cortex_ext3()
    expected = {
        "account.receipt",
        "action.pick",
        "action.route",
        "asset.check",
        "asset.list",
        "asset.receipt",
        "encode.list",
        "encode.receipt",
        "output.receipt",
        "routes.list",
        "tool.receipt",
        "visual.receipt",
        "voice.receipt",
    }

    assert expected == set(registry)
    routes = registry["routes.list"].unit()
    assert all(row["next_unit"] in registry for row in routes)


def test_extension_catalogs_run_through_bus() -> None:
    payload = run_cortex_units(
        build_cortex_ext3(),
        [
            {"name": "asset.list", "kwargs": {}},
            {"name": "encode.list", "kwargs": {}},
            {"name": "routes.list", "kwargs": {}},
        ],
    )

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 3
    assert payload["result_count"] == 3
    assert len(payload["results"][0]["output"]) == 4
    assert len(payload["results"][1]["output"]) == 5
    assert len(payload["results"][2]["output"]) >= 10
