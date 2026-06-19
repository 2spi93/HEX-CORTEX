from __future__ import annotations

_CHANNELS = [
    {"channel_id": "telegram", "auth_mode": "bot_token"},
    {"channel_id": "whatsapp", "auth_mode": "access_token"},
    {"channel_id": "linkedin", "auth_mode": "oauth2"},
    {"channel_id": "instagram", "auth_mode": "access_token"},
    {"channel_id": "reddit", "auth_mode": "oauth2"},
]


def list_cortex_channels() -> list[dict[str, object]]:
    return [
        {
            **item,
            "state": "candidate",
            "credentials_required": True,
            "operator_approval_required_for_write": True,
            "network_calls_enabled": False,
            "content_published": False,
            "messages_read": False,
        }
        for item in _CHANNELS
    ]


def get_cortex_channel(channel_id: str) -> dict[str, object]:
    for item in list_cortex_channels():
        if item["channel_id"] == channel_id:
            return item
    return {
        "channel_id": channel_id,
        "state": "blocked",
        "blocker": "unknown_channel_candidate",
    }


def evaluate_cortex_channel_candidate(
    *,
    channel_id: str,
    mode: str,
    credentials_available: bool,
    operator_approved: bool,
) -> dict[str, object]:
    channel = get_cortex_channel(channel_id)
    blockers = []
    if channel.get("state") == "blocked":
        blockers.append(str(channel.get("blocker")))
    if mode not in {"read", "write"}:
        blockers.append("channel_mode_invalid")
    if channel.get("credentials_required") is True and not credentials_available:
        blockers.append("channel_credentials_required")
    if mode == "write" and not operator_approved:
        blockers.append("operator_approval_required_for_write")
    ready = not blockers
    return {
        "channel_candidate_type": "cortex_channel_candidate",
        "channel_id": channel_id,
        "mode": mode,
        "candidate_ready": ready,
        "auth_mode": channel.get("auth_mode"),
        "network_call_allowed": False,
        "credential_persistence_allowed": False,
        "content_published": False,
        "messages_read": False,
        "next_action": (
            "prepare_channel_adapter_receipt"
            if ready
            else "repair_channel_candidate"
        ),
        "blockers": blockers,
    }
