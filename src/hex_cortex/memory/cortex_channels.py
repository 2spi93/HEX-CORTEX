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
