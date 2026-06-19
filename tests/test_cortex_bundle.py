from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_bundle import build_cortex_bundle_read_plan
from hex_cortex.memory.cortex_bus import run_cortex_units


def test_bundle_contains_critical_units() -> None:
    registry = build_cortex_bundle()
    expected = {
        "lc.build",
        "sensor.receipt",
        "providers.list",
        "providers.score",
        "providers.select",
        "seen.build",
        "state.build",
        "transition.build",
        "surprise.build",
        "seq.build",
        "goal.build",
        "cost.evaluate",
        "action.propose",
        "channels.list",
        "channels.evaluate",
        "action.pick",
        "asset.list",
        "asset.check",
        "asset.receipt",
        "encode.list",
        "encode.receipt",
        "account.receipt",
    }

    assert expected.issubset(registry)
    assert len(registry) == len(set(registry))


def test_bundle_read_plan_runs_in_one_pass() -> None:
    payload = run_cortex_units(
        build_cortex_bundle(),
        build_cortex_bundle_read_plan(),
    )

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 9
    assert payload["result_count"] == 9
    names = [item["name"] for item in payload["results"]]
    assert names == [
        "domains.list",
        "modal.list",
        "providers.list",
        "outputs.list",
        "channels.list",
        "asset.list",
        "encode.list",
        "links.list",
        "preferences.profile",
    ]


def test_bundle_builds_encode_receipt(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    payload = run_cortex_units(
        build_cortex_bundle(),
        [
            {
                "name": "encode.receipt",
                "kwargs": {
                    "profile": profile,
                    "encoder_id": "image_encoder",
                    "source_hash": "image-source-hash",
                    "adapter_available": True,
                    "embedding_dimensions": 768,
                },
            }
        ],
    )

    assert payload["bus_allowed"] is True
    record = payload["results"][0]["output"]["encode_records"][0]
    assert record["encode_allowed"] is True
    assert record["encoding_performed"] is False
