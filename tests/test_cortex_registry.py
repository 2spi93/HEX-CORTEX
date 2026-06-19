from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import list_cortex_units
from hex_cortex.memory.cortex_bus import run_cortex_units
from hex_cortex.memory.cortex_registry import build_cortex_registry
from hex_cortex.memory.cortex_registry import build_cortex_registry_plan
from hex_cortex.memory.cortex_registry import describe_cortex_r


def test_cortex_registry_lists_expected_units() -> None:
    registry = build_cortex_registry()

    assert sorted(registry) == [
        "a.build",
        "b.build",
        "c.build",
        "lc.build",
        "r.describe",
        "stability.compute",
        "web.describe",
    ]
    rows = list_cortex_units(registry)
    names = [row["name"] for row in rows]
    assert names == [
        "a.build",
        "b.build",
        "c.build",
        "lc.build",
        "r.describe",
        "stability.compute",
        "web.describe",
    ]
    assert any(row["requires_operator"] is True for row in rows)


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
    assert payload["step_count"] == 5
    assert payload["result_count"] == 5
    assert payload["results"][0]["name"] == "lc.build"
    assert payload["results"][1]["name"] == "a.build"
    assert payload["results"][2]["name"] == "r.describe"
    assert payload["results"][3]["name"] == "web.describe"
    assert payload["results"][4]["name"] == "stability.compute"


def test_cortex_registry_combines_without_duplicate() -> None:
    registry = build_cortex_registry()
    combined = combine_cortex_registries(registry)

    assert combined == registry
