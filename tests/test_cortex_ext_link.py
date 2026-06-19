from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_channel_link import build_cortex_channel_link


def test_extension_link_lists_two_units() -> None:
    registry = build_cortex_channel_link()

    assert sorted(registry) == ["channels.evaluate", "channels.list"]
    assert all(unit.mutates_receipt is False for unit in registry.values())


def test_extension_gate_stays_offline() -> None:
    registry = build_cortex_channel_link()
    channel_id = registry["channels.list"].unit()[0]["channel_id"]
    payload = run_cortex_units(
        registry,
        [
            {
                "name": "channels.evaluate",
                "kwargs": {
                    "channel_id": channel_id,
                    "mode": "read",
                    "credentials_available": True,
                    "operator_approved": False,
                },
            }
        ],
    )

    assert payload["bus_allowed"] is True
    output = payload["results"][0]["output"]
    assert output["candidate_ready"] is True
    assert output["network_call_allowed"] is False
