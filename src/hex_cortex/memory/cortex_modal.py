from __future__ import annotations

_CAPABILITIES = [
    {
        "capability_id": "screen_vision",
        "input_type": "screen_frame_or_screenshot",
        "default_mode": "operator_approved_readonly",
        "raw_input_persistence_allowed": False,
        "next_action": "candidate_adapter_receipt",
    },
    {
        "capability_id": "camera_vision",
        "input_type": "camera_frame",
        "default_mode": "operator_approved_readonly",
        "raw_input_persistence_allowed": False,
        "next_action": "candidate_adapter_receipt",
    },
    {
        "capability_id": "vision_3d",
        "input_type": "multi_view_depth_point_cloud_or_mesh",
        "default_mode": "operator_approved_readonly",
        "raw_input_persistence_allowed": False,
        "next_action": "candidate_adapter_receipt",
    },
    {
        "capability_id": "voice_input",
        "input_type": "audio_or_transcript",
        "default_mode": "operator_approved_readonly",
        "raw_input_persistence_allowed": False,
        "next_action": "candidate_adapter_receipt",
    },
    {
        "capability_id": "voice_output",
        "input_type": "text_to_speech_request",
        "default_mode": "operator_approved_output",
        "raw_input_persistence_allowed": False,
        "next_action": "candidate_adapter_receipt",
    },
]


def list_cortex_multimodal_capabilities() -> list[dict[str, object]]:
    return [dict(item) for item in _CAPABILITIES]


def describe_cortex_multimodal_capability(capability_id: str) -> dict[str, object]:
    for item in _CAPABILITIES:
        if item["capability_id"] == capability_id:
            return dict(item)
    return {
        "capability_id": capability_id,
        "status": "blocked",
        "blocker": "unknown_multimodal_capability",
    }
