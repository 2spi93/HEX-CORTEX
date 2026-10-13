"""Simulation voice intents do not grant physical dispatch."""
from __future__ import annotations

import pytest

from hex_cortex.memory.cortex_voice_to_simulation_v26 import (
    handle_operator_voice_transcript,
)


@pytest.mark.parametrize("text", [
    "simule le mouvement", "simule le déplacement",
    "simulate movement", "simulate object movement",
])
def test_operator_voice_can_simulate_not_actuate(text: str) -> None:
    result = handle_operator_voice_transcript(
        transcript=text, approved_transcript=True, approved_simulation=True
    )
    assert result["status"] == "simulation_only"
    assert result["intent"] == "simulate_move"
    assert result["virtual_object_state"]["x"] == .5
    assert result["hardware_handler_called"] is False
    assert result["physical_action_executed"] is False
    assert result["speech_recognition_performed"] is False


@pytest.mark.parametrize("text", [
    "démarre le moteur", "allume le robot", "power on device",
    "remove safety interlocks", "execute trade", "supprime tous les fichiers",
])
def test_unbounded_spoken_requests_are_not_commands(text: str) -> None:
    result = handle_operator_voice_transcript(
        transcript=text, approved_transcript=True, approved_simulation=True
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "voice_intent_not_allowlisted"
    assert result["physical_action_executed"] is False


def test_missing_permission_refused_before_sensing() -> None:
    result = handle_operator_voice_transcript(
        transcript="simulate movement", approved_simulation=True
    )
    assert result["status"] == "blocked"
    assert result["reason"] == "transcript_approval_required"


def test_voice_status_stays_simulated() -> None:
    result = handle_operator_voice_transcript(
        transcript="état du monde",
        approved_transcript=True, approved_simulation=True
    )
    assert result["status"] == "simulation_only"
    assert result["intent"] == "inspect"
    assert result["physical_action_executed"] is False
