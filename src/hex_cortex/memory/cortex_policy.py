from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from hex_cortex.memory.cortex_bus import CortexUnit


class CortexMode(StrEnum):
    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTO_SAFE = "auto_safe"


@dataclass(frozen=True)
class CortexPolicyDecision:
    allowed: bool
    mode: CortexMode
    unit_name: str
    reason: str
    needs_operator: bool


def decide_cortex_unit_access(
    *,
    mode: CortexMode,
    unit_name: str,
    registry: dict[str, CortexUnit],
    trusted_plan: bool = False,
) -> CortexPolicyDecision:
    if unit_name not in registry:
        return CortexPolicyDecision(
            allowed=False,
            mode=mode,
            unit_name=unit_name,
            reason="unknown_unit_requires_registration",
            needs_operator=True,
        )
    unit = registry[unit_name]
    if mode is CortexMode.MANUAL:
        return CortexPolicyDecision(
            allowed=False,
            mode=mode,
            unit_name=unit_name,
            reason="manual_mode_requires_operator",
            needs_operator=True,
        )
    if mode is CortexMode.ASSISTED:
        return CortexPolicyDecision(
            allowed=not unit.requires_operator,
            mode=mode,
            unit_name=unit_name,
            reason="assisted_allows_readonly_units"
            if not unit.requires_operator
            else "assisted_blocks_operator_units",
            needs_operator=unit.requires_operator,
        )
    if mode is CortexMode.AUTO_SAFE:
        if unit.requires_operator and not trusted_plan:
            return CortexPolicyDecision(
                allowed=False,
                mode=mode,
                unit_name=unit_name,
                reason="auto_safe_requires_trusted_plan_for_operator_units",
                needs_operator=True,
            )
        return CortexPolicyDecision(
            allowed=True,
            mode=mode,
            unit_name=unit_name,
            reason="auto_safe_allowed_registered_unit",
            needs_operator=unit.requires_operator and not trusted_plan,
        )
    return CortexPolicyDecision(
        allowed=False,
        mode=mode,
        unit_name=unit_name,
        reason="unsupported_mode",
        needs_operator=True,
    )
