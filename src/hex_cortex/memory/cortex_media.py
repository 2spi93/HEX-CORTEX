from __future__ import annotations

_MEDIA_PROVIDERS = [
    {
        "provider_id": "local_image_service",
        "supported_outputs": ["generate_image"],
        "transport": "loopback_http",
        "local_provider": True,
        "credentials_required": False,
        "requires_operator": False,
    },
    {
        "provider_id": "local_video_service",
        "supported_outputs": ["generate_video"],
        "transport": "loopback_http",
        "local_provider": True,
        "credentials_required": False,
        "requires_operator": False,
    },
    {
        "provider_id": "local_3d_service",
        "supported_outputs": ["generate_3d_scene", "render_3d_asset"],
        "transport": "local_process",
        "local_provider": True,
        "credentials_required": False,
        "requires_operator": False,
    },
    {
        "provider_id": "remote_media_service",
        "supported_outputs": [
            "generate_image",
            "generate_video",
            "generate_3d_scene",
            "render_3d_asset",
        ],
        "transport": "https_api",
        "local_provider": False,
        "credentials_required": True,
        "requires_operator": True,
    },
]


def list_cortex_media_providers() -> list[dict[str, object]]:
    return [
        {
            **item,
            "state": "candidate",
            "execution_enabled": False,
            "raw_input_persistence_allowed": False,
        }
        for item in _MEDIA_PROVIDERS
    ]


def get_cortex_media_provider(provider_id: str) -> dict[str, object]:
    for item in list_cortex_media_providers():
        if item["provider_id"] == provider_id:
            return item
    return {
        "provider_id": provider_id,
        "state": "blocked",
        "blocker": "unknown_media_provider",
    }


def evaluate_cortex_media_candidate(
    *,
    provider_id: str,
    output_id: str,
    local_available: bool,
    credentials_available: bool,
    operator_approved: bool,
) -> dict[str, object]:
    provider = get_cortex_media_provider(provider_id)
    blockers = []
    outputs = provider.get("supported_outputs", [])
    if provider.get("state") == "blocked":
        blockers.append(str(provider.get("blocker")))
    if not isinstance(outputs, list) or output_id not in outputs:
        blockers.append("unsupported_media_output")
    if provider.get("local_provider") is True and not local_available:
        blockers.append("local_media_provider_unavailable")
    if provider.get("credentials_required") is True and not credentials_available:
        blockers.append("media_credentials_required")
    if provider.get("requires_operator") is True and not operator_approved:
        blockers.append("operator_approval_required_for_remote_media")
    ready = not blockers
    return {
        "media_candidate_type": "cortex_media_candidate",
        "provider_id": provider_id,
        "output_id": output_id,
        "candidate_ready": ready,
        "transport": provider.get("transport"),
        "local_provider": provider.get("local_provider"),
        "network_call_allowed": False,
        "local_process_started": False,
        "generation_performed": False,
        "raw_input_persistence_allowed": False,
        "next_action": (
            "prepare_media_receipt"
            if ready
            else "repair_media_candidate"
        ),
        "blockers": blockers,
    }
