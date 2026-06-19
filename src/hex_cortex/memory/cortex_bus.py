from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

Unit = Callable[..., dict[str, object]]


@dataclass(frozen=True)
class CortexUnit:
    name: str
    unit: Unit
    description: str
    mutates_receipt: bool = False
    requires_operator: bool = False


def list_cortex_units(registry: Mapping[str, CortexUnit]) -> list[dict[str, object]]:
    return [
        {
            "name": item.name,
            "description": item.description,
            "mutates_receipt": item.mutates_receipt,
            "requires_operator": item.requires_operator,
        }
        for item in sorted(registry.values(), key=lambda unit: unit.name)
    ]


def run_cortex_units(
    registry: Mapping[str, CortexUnit],
    plan: list[dict[str, object]],
) -> dict[str, object]:
    results = []
    blockers = []
    for index, step in enumerate(plan):
        name = step.get("name")
        kwargs = step.get("kwargs", {})
        if not isinstance(name, str):
            blockers.append(f"step_{index}_missing_name")
            continue
        if name not in registry:
            blockers.append(f"step_{index}_unknown_unit")
            continue
        if not isinstance(kwargs, dict):
            blockers.append(f"step_{index}_kwargs_not_dict")
            continue
        unit = registry[name]
        try:
            output = unit.unit(**kwargs)
        except Exception as exc:  # noqa: BLE001 - receipt must capture any adapter failure.
            blockers.append(f"step_{index}_failed:{type(exc).__name__}")
            results.append({"name": name, "status": "failed", "error_type": type(exc).__name__})
            continue
        results.append({"name": name, "status": "ok", "output": output})
    return {
        "bus_type": "cortex_bus",
        "step_count": len(plan),
        "result_count": len(results),
        "bus_allowed": not blockers,
        "blockers": blockers,
        "results": results,
    }


def combine_cortex_registries(*registries: Mapping[str, CortexUnit]) -> dict[str, CortexUnit]:
    combined: dict[str, CortexUnit] = {}
    for registry in registries:
        overlap = set(combined).intersection(registry)
        if overlap:
            names = ",".join(sorted(overlap))
            raise ValueError(f"duplicate units: {names}")
        combined.update(registry)
    return combined
