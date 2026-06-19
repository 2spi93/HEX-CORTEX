from __future__ import annotations

from urllib.parse import urlparse

_CONNECTORS = {
    "telegram": {
        "auth_mode": "token",
        "callback_required": False,
        "supports_inbound": True,
        "supports_outbound": True,
    },
    "linkedin": {
        "auth_mode": "oauth2",
        "callback_required": True,
        "supports_inbound": True,
        "supports_outbound": True,
    },
    "instagram": {
        "auth_mode": "oauth2",
        "callback_required": True,
        "supports_inbound": True,
        "supports_outbound": True,
    },
    "whatsapp": {
        "auth_mode": "token",
        "callback_required": True,
        "supports_inbound": True,
        "supports_outbound": True,
    },
    "reddit": {
        "auth_mode": "oauth2",
        "callback_required": True,
        "supports_inbound": False,
        "supports_outbound": True,
    },
}


def list_cortex_connectors() -> list[dict[str, object]]:
    return [
        {
            "provider": provider,
            **config,
            "default_mode": "read",
            "outbound_requires_operator": True,
            "value_persisted": False,
        }
        for provider, config in sorted(_CONNECTORS.items())
    ]


def build_cortex_connector_plan(
    *,
    provider: str,
    account: str = "main",
    mode: str = "read",
    callback_url: str | None = None,
) -> dict[str, object]:
    config = _CONNECTORS.get(provider)
    if config is None:
        return _blocked(provider, account, "unknown_connector")
    if mode not in {"read", "outbound"}:
        return _blocked(provider, account, "invalid_connector_mode")
    blockers = []
    if config["callback_required"] is True:
        if callback_url is None:
            blockers.append("callback_url_required")
        elif not _valid_https(callback_url):
            blockers.append("callback_url_must_use_https")
    if mode == "outbound" and config["supports_outbound"] is not True:
        blockers.append("outbound_not_supported")
    allowed = not blockers
    return {
        "plan_type": "cortex_external_connector",
        "provider": provider,
        "account": account,
        "mode": mode,
        "auth_mode": config["auth_mode"],
        "callback_url": callback_url,
        "callback_required": config["callback_required"],
        "supports_inbound": config["supports_inbound"],
        "supports_outbound": config["supports_outbound"],
        "connection_allowed": allowed,
        "operator_required": mode == "outbound",
        "value_persisted": False,
        "next_action": (
            "register_external_auth_reference"
            if allowed
            else "repair_connector_plan"
        ),
        "blockers": blockers,
    }


def _valid_https(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and bool(parsed.hostname)


def _blocked(
    provider: str,
    account: str,
    blocker: str,
) -> dict[str, object]:
    return {
        "plan_type": "cortex_external_connector",
        "provider": provider,
        "account": account,
        "connection_allowed": False,
        "operator_required": True,
        "value_persisted": False,
        "next_action": "repair_connector_plan",
        "blockers": [blocker],
    }
