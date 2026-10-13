"""Operator transcript -> allowlisted intent -> simulated object, never actuator.

This is NOT ASR or microphone support. User-provided transcript is the input.
No unbounded LLM instructions are interpreted as hardware commands.
"""
from __future__ import annotations

import hashlib

from hex_cortex.memory.cortex_simulated_object_control_v26 import (
    plan_simulated_object_control,
)
from hex_cortex.memory.cortex_universal_sensing_v26 import observe_transcript

_SIMULATE = {
    "simule le mouvement", "simule le déplacement",
    "simulate movement", "simulate object movement",
}
_INSPECT = {"inspecte objet", "inspect object", "état du monde", "world status"}


def handle_operator_voice_transcript(
    *, transcript: str,
    device_id: str = "virtual_cart",
    approved_transcript: bool = False,
    approved_simulation: bool = False,
) -> dict[str, object]:
    if not approved_transcript:
        return {
            "status": "blocked", "reason": "transcript_approval_required",
            "model_called": False, "physical_action_executed": False,
        }
    observed = observe_transcript(text=transcript, approved=True)
    intent = transcript.strip().casefold()
    if intent not in _SIMULATE and intent not in _INSPECT:
        return {
            "status": "blocked", "reason": "voice_intent_not_allowlisted",
            "source_sha256": observed["source_sha256"],
            "speech_recognition_performed": False,
            "physical_action_executed": False,
        }
    if not approved_simulation:
        return {
            "status": "blocked", "reason": "simulation_approval_required",
            "source_sha256": observed["source_sha256"],
            "physical_action_executed": False,
        }
    action = plan_simulated_object_control(
        device_id=device_id,
        intent="simulate_move" if intent in _SIMULATE else "inspect",
        state={"x": 0.0, "y": 0.0, "vx": 0.0, "vy": 0.0},
        acceleration={"ax": 1.0, "ay": 0.0},
        duration_seconds=1.0, approved=True,
    )
    return {
        "status": action["status"],
        "intent": action["intent"],
        "source_sha256": observed["source_sha256"],
        "response_sha256": hashlib.sha256(action["receipt_sha256"].encode()).hexdigest(),
        "virtual_object_state": action["simulated_next_state"],
        "speech_recognition_performed": False,
        "hardware_handler_called": False,
        "physical_action_executed": False,
        "text_to_speech_performed": False,
    }
