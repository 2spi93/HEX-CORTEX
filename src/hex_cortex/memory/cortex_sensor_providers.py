from __future__ import annotations

_PROVIDERS = [
    {
        "provider_id": "browser_display",
        "capability_id": "screen_vision",
        "state": "candidate",
        "permission_mode": "explicit_user_selection",
        "secure_context_required": True,
        "raw_input_persistence_allowed": False,
    },
    {
        "provider_id": "browser_camera",
        "capability_id": "camera_vision",
        "state": "candidate",
        "permission_mode": "explicit_user_permission",
        "secure_context_required": True,
        "raw_input_persistence_allowed": False,
    },
    {
        "provider_id": "browser_microphone",
        "capability_id": "voice_input",
        "state": "candidate",
        "permission_mode": "explicit_user_permission",
        "secure_context_required": True,
        "raw_input_persistence_allowed": False,
    },
    {
        "provider_id": "browser_speech_output",
        "capability_id": "voice_output",
        "state": "candidate",
        "permission_mode": "operator_requested_output",
        "secure_context_required": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "provider_id": "local_image_file",
        "capability_id": "screen_vision",
        "state": "candidate",
        "permission_mode": "operator_selected_file",
        "secure_context_required": False,
        "raw_input_persistence_allowed": False,
    },
    {
        "provider_id": "local_transcript",
        "capability_id": "voice_input",
        "state": "candidate",
        "permission_mode": "operator_supplied_text",
        "secure_context_required": False,
        "raw_input_persistence_allowed": False,
    },
]


def list_cortex_sensor_providers() -> list[dict[str, object]]:
    return [dict(item) for item in _PROVIDERS]


def get_cortex_sensor_provider(provider_id: str) -> dict[str, object]:
    for item in _PROVIDERS:
        if item["provider_id"] == provider_id:
            return dict(item)
    return {
        "provider_id": provider_id,
        "state": "blocked",
        "blocker": "unknown_sensor_provider",
    }


def score_cortex_sensor_provider(provider_id: str) -> dict[str, object]:
    provider = get_cortex_sensor_provider(provider_id)
    if provider.get("state") == "blocked":
        return {
            "provider_id": provider_id,
            "ready": False,
            "score": 0.0,
            "blockers": [str(provider.get("blocker"))],
        }
    checks = {
        "candidate_state": provider.get("state") == "candidate",
        "permission_declared": isinstance(provider.get("permission_mode"), str),
        "secure_context_declared": isinstance(
            provider.get("secure_context_required"),
            bool,
        ),
        "raw_persistence_blocked": provider.get("raw_input_persistence_allowed") is False,
    }
    score = round(100 * sum(checks.values()) / len(checks), 2)
    return {
        "provider_id": provider_id,
        "ready": all(checks.values()),
        "score": score,
        "checks": checks,
        "blockers": [name for name, passed in checks.items() if not passed],
    }
