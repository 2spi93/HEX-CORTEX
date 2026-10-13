"""Control-contract demonstration: plan/inspect/simulate, NEVER real actuation.

Connects the existing HardwareAdapter registry and deterministic world
simulator. Hardware handler deliberately refuses all calls; no Gateway
dispatch is authorized. The LLM cannot give itself actuator permission.
"""
from __future__ import annotations

import hashlib
import json

from hex_cortex.memory.cortex_gateway import (
    build_cortex_adapter_registry, list_cortex_adapters,
)
from hex_cortex.memory.cortex_hardware_adapter import build_cortex_hardware_adapter
from hex_cortex.memory.cortex_universal_world_loop_v26 import (
    simulate_world_transition,
)

_ACTIONS = {"inspect", "simulate_move"}


def _deny_physical_handler(_request: dict[str, object]) -> dict[str, object]:
    raise PermissionError("v26_physical_device_dispatch_unsupported")


def plan_simulated_object_control(
    *, device_id: str, intent: str, state: dict[str, float],
    acceleration: dict[str, float], duration_seconds: float,
    approved: bool = False,
) -> dict[str, object]:
    """Produce a signed-by-hash advisory receipt, never a hardware command."""
    if not approved:
        return {
            "status": "blocked", "reason": "object_control_approval_required",
            "hardware_handler_called": False, "physical_action_executed": False,
        }
    if intent not in _ACTIONS:
        return {
            "status": "blocked", "reason": "physical_or_unsupported_intent_denied",
            "hardware_handler_called": False, "physical_action_executed": False,
        }
    adapter = build_cortex_hardware_adapter(
        device_id=device_id, handler=_deny_physical_handler,
    )
    registry = build_cortex_adapter_registry(adapter)
    descriptor = list_cortex_adapters(registry)[0]
    # Even a requested "inspect" remains simulated here; no hardware polling.
    simulation = simulate_world_transition(
        state=state, action=acceleration, dt_seconds=duration_seconds,
        approved=True,
    )
    proof = {
        "intent": intent,
        "device_id": device_id,
        "world_prediction_hash": simulation["state_prediction_sha256"],
    }
    return {
        "status": "simulation_only",
        "intent": intent,
        "registered_adapter": descriptor["name"],
        "requires_operator": descriptor["requires_operator"],
        "gateway_dispatch_authorized": False,
        "hardware_handler_called": False,
        "physical_action_executed": False,
        "simulated_next_state": simulation["predicted_state"],
        "receipt_sha256": hashlib.sha256(
            json.dumps(proof, sort_keys=True).encode()
        ).hexdigest(),
        "real_device_connection_verified": False,
        "safety_interlock_certified": False,
        "device_commands_generated": False,
    }
