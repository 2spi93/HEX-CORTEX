"""Hardware registry is wired but real physical handler cannot be called."""
from __future__ import annotations

import pytest

from hex_cortex.memory.cortex_simulated_object_control_v26 import (
    plan_simulated_object_control,
)


def _kwargs() -> dict:
    return dict(
        device_id="virtual_cart", intent="simulate_move",
        state={"x": 0.0, "y": 0.0, "vx": 1.0, "vy": 0.0},
        acceleration={"ax": 1.0, "ay": 0.0},
        duration_seconds=2.0,
    )


def test_registered_hardware_device_is_simulation_only() -> None:
    result = plan_simulated_object_control(**_kwargs(), approved=True)
    assert result["status"] == "simulation_only"
    assert result["registered_adapter"] == "hardware.virtual_cart"
    assert result["simulated_next_state"]["x"] == 4.0
    assert result["physical_action_executed"] is False
    assert result["hardware_handler_called"] is False
    assert result["gateway_dispatch_authorized"] is False
    assert result["safety_interlock_certified"] is False


@pytest.mark.parametrize("intent", ["actuate", "move", "power_on", "deploy", "delete"])
def test_all_real_device_intents_denied(intent: str) -> None:
    result = plan_simulated_object_control(
        **{**_kwargs(), "intent": intent}, approved=True
    )
    assert result["status"] == "blocked"
    assert result["hardware_handler_called"] is False
    assert result["physical_action_executed"] is False


def test_operator_must_approve_even_simulated_control() -> None:
    result = plan_simulated_object_control(**_kwargs())
    assert result["status"] == "blocked"
    assert result["hardware_handler_called"] is False


def test_invalid_hardware_id_refused() -> None:
    with pytest.raises(ValueError, match="device_id"):
        plan_simulated_object_control(
            **{**_kwargs(), "device_id": "../../hardware"}, approved=True,
        )
