from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import list_cortex_units
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_registry import build_cortex_registry
from hex_cortex.memory.cortex_registry import build_cortex_registry_plan
from hex_cortex.memory.cortex_registry import describe_cortex_r

_EXPECTED_UNITS = [
    "a.build",
    "b.build",
    "c.build",
    "domains.list",
    "lc.build",
    "links.list",
    "modal.list",
    "preferences.profile",
    "r.describe",
    "sensor.receipt",
    "stability.compute",
    "web.describe",
    "world.compute",
]


def test_cortex_registry_lists_expected_units() -> None:
    registry = build_cortex_registry()

    assert sorted(registry) == _EXPECTED_UNITS
    rows = list_cortex_units(registry)
    names = [row["name"] for row in rows]
    assert names == _EXPECTED_UNITS
    sensor = next(row for row in rows if row["name"] == "sensor.receipt")
    assert sensor["requires_operator"] is True
    assert sensor["mutates_receipt"] is True


def test_describe_cortex_r_does_not_execute_runner() -> None:
    payload = describe_cortex_r(
        endpoint="http://127.0.0.1:11434/api/generate",
        timeout_seconds=3.0,
    )

    assert payload["adapter_type"] == "cortex_r"
    assert payload["endpoint_redacted"] == "http://127.0.0.1:<redacted>"
    assert payload["timeout_seconds"] == 3.0
    assert payload["runner_created"] is True
    assert payload["runner_executed"] is False
    assert payload["next_action"] == "inject_runner_into_b_or_c"


def test_cortex_registry_plan_runs_safe_units(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = build_cortex_registry()
    plan = build_cortex_registry_plan(profile)

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 10
    assert payload["result_count"] == 10
    assert all(step["name"] != "sensor.receipt" for step in plan)
    assert payload["results"][0]["name"] == "lc.build"
    assert payload["results"][1]["name"] == "a.build"
    assert payload["results"][2]["name"] == "r.describe"
    assert payload["results"][3]["name"] == "web.describe"
    assert payload["results"][4]["name"] == "stability.compute"
    assert payload["results"][5]["name"] == "domains.list"
    assert payload["results"][6]["name"] == "modal.list"
    assert payload["results"][7]["name"] == "world.compute"
    assert payload["results"][8]["name"] == "links.list"
    assert payload["results"][9]["name"] == "preferences.profile"


def test_sensor_receipt_runs_with_explicit_approval(tmp_path) -> None:
    profile = tmp_path / ".hex-cortex"
    profile.mkdir()
    registry = build_cortex_registry()

    payload = run_cortex_units(
        registry,
        [
            {
                "name": "sensor.receipt",
                "kwargs": {
                    "profile": profile,
                    "capability_id": "screen_vision",
                    "operator_approved": True,
                },
            }
        ],
    )

    assert payload["bus_allowed"] is True
    output = payload["results"][0]["output"]
    record = output["modal_receipt_records"][0]
    assert record["modal_allowed"] is True
    assert record["capture_performed"] is False


def test_cortex_registry_combines_without_duplicate() -> None:
    registry = build_cortex_registry()
    combined = combine_cortex_registries(registry)

    assert combined == registry
