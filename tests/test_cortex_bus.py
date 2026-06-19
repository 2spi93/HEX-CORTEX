import pytest

from hex_cortex.memory.cortex_bus import CortexUnit
from hex_cortex.memory.cortex_bus import combine_cortex_registries
from hex_cortex.memory.cortex_bus import list_cortex_units
from hex_cortex.memory.cortex_bus import run_cortex_units


def test_cortex_bus_lists_units() -> None:
    registry = {"one": CortexUnit("one", _one, "first unit")}

    rows = list_cortex_units(registry)

    assert rows == [
        {
            "name": "one",
            "description": "first unit",
            "mutates_receipt": False,
            "requires_operator": False,
        }
    ]


def test_cortex_bus_runs_multiple_units() -> None:
    registry = {
        "one": CortexUnit("one", _one, "first unit"),
        "two": CortexUnit("two", _two, "second unit"),
    }
    plan = [
        {"name": "one", "kwargs": {"value": 2}},
        {"name": "two", "kwargs": {"value": 3}},
    ]

    payload = run_cortex_units(registry, plan)

    assert payload["bus_allowed"] is True
    assert payload["step_count"] == 2
    assert payload["result_count"] == 2
    assert payload["results"][0]["output"] == {"value": 3}
    assert payload["results"][1]["output"] == {"value": 6}


def test_cortex_bus_blocks_unknown_unit() -> None:
    payload = run_cortex_units({}, [{"name": "missing", "kwargs": {}}])

    assert payload["bus_allowed"] is False
    assert "step_0_unknown_unit" in payload["blockers"]


def test_combine_cortex_registries_rejects_duplicate() -> None:
    one = {"unit": CortexUnit("unit", _one, "one")}
    two = {"unit": CortexUnit("unit", _two, "two")}

    with pytest.raises(ValueError, match="duplicate"):
        combine_cortex_registries(one, two)


def _one(*, value: int) -> dict[str, object]:
    return {"value": value + 1}


def _two(*, value: int) -> dict[str, object]:
    return {"value": value * 2}
