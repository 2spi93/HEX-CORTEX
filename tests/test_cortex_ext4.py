from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_ext3 import build_cortex_ext3


def test_ext3_exposes_expected_units() -> None:
    registry = build_cortex_ext3()

    assert sorted(registry) == [
        "account.receipt",
        "action.pick",
        "asset.check",
        "asset.list",
        "asset.receipt",
        "encode.list",
        "encode.receipt",
    ]
    assert registry["action.pick"].mutates_receipt is True
    assert registry["asset.list"].mutates_receipt is False
    assert registry["encode.receipt"].mutates_receipt is True


def test_ext3_runs_catalogs_through_bus() -> None:
    payload = run_cortex_units(
        build_cortex_ext3(),
        [
            {"name": "asset.list", "kwargs": {}},
            {"name": "encode.list", "kwargs": {}},
        ],
    )

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 2
    assert payload["result_count"] == 2
    asset_rows = payload["results"][0]["output"]
    encoder_rows = payload["results"][1]["output"]
    assert len(asset_rows) == 4
    assert len(encoder_rows) == 5
    assert all(row["execution_enabled"] is False for row in asset_rows)
    assert all(row["encoding_enabled"] is False for row in encoder_rows)
