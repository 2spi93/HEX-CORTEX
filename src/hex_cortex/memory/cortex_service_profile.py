from __future__ import annotations

from urllib.parse import urlparse


def build_cortex_service_profile(
    *,
    public_base_url: str,
    app_port: int = 8765,
    tunnel: str = "none",
    telegram_hook: bool = False,
) -> dict[str, object]:
    parsed = urlparse(public_base_url)
    blockers = []
    if parsed.scheme != "https" or not parsed.hostname:
        blockers.append("public_base_url_must_use_https")
    if app_port < 1024 or app_port > 65535:
        blockers.append("app_port_out_of_range")
    if tunnel not in {"none", "cloudflare", "tailscale"}:
        blockers.append("tunnel_mode_invalid")
    allowed = not blockers
    return {
        "profile_type": "cortex_service_deployment",
        "service_allowed": allowed,
        "bind_host": "127.0.0.1",
        "app_port": app_port,
        "public_base_url": public_base_url,
        "reverse_proxy": "caddy",
        "automatic_https": True,
        "tunnel": tunnel,
        "telegram_webhook_url": (
            f"{public_base_url.rstrip('/')}/v1/hooks/telegram"
            if telegram_hook and allowed
            else None
        ),
        "request_body_limit_mb": 2,
        "health_path": "/healthz",
        "read_only_path": "/v1/read",
        "next_action": (
            "render_service_files"
            if allowed
            else "repair_service_profile"
        ),
        "blockers": blockers,
    }
