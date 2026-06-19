import json

import pytest

from hex_cortex.memory.cortex_caddy import render_cortex_caddyfile
from hex_cortex.memory.cortex_http_readonly import dispatch_cortex_http
from hex_cortex.memory.cortex_http_readonly import serve_cortex_http
from hex_cortex.memory.cortex_service_profile import build_cortex_service_profile


def test_service_profile_requires_https_and_loopback_proxy() -> None:
    blocked = build_cortex_service_profile(
        public_base_url="http://example.test"
    )
    ready = build_cortex_service_profile(
        public_base_url="https://cortex.example.test",
        tunnel="cloudflare",
        telegram_hook=True,
    )

    assert blocked["service_allowed"] is False
    assert ready["service_allowed"] is True
    assert ready["bind_host"] == "127.0.0.1"
    assert ready["reverse_proxy"] == "caddy"
    assert ready["automatic_https"] is True
    assert ready["telegram_webhook_url"] == (
        "https://cortex.example.test/v1/hooks/telegram"
    )


def test_caddy_renderer_uses_loopback_and_security_headers() -> None:
    profile = build_cortex_service_profile(
        public_base_url="https://cortex.example.test",
        app_port=8765,
    )

    text = render_cortex_caddyfile(profile)

    assert text.startswith("cortex.example.test {")
    assert "reverse_proxy 127.0.0.1:8765" in text
    assert "Strict-Transport-Security" in text
    assert "max_size 2MB" in text


def test_http_read_routes_are_available() -> None:
    health_status, health = dispatch_cortex_http(
        method="GET",
        path="/healthz",
    )
    wiring_status, wiring = dispatch_cortex_http(
        method="GET",
        path="/v1/read/wiring",
    )

    assert health_status == 200
    assert health["status"] == "ok"
    assert wiring_status == 200
    assert wiring["architecture_ready"] is True


def test_telegram_hook_requires_authorization_and_hashes_payload() -> None:
    body = json.dumps({"update_id": 1}).encode("utf-8")
    blocked_status, blocked = dispatch_cortex_http(
        method="POST",
        path="/v1/hooks/telegram",
        body=body,
    )
    ready_status, ready = dispatch_cortex_http(
        method="POST",
        path="/v1/hooks/telegram",
        body=body,
        headers={"X-Hook": "ready"},
        hook_verifier=lambda headers: headers.get("x-hook") == "ready",
    )

    assert blocked_status == 503
    assert blocked["blockers"] == ["hook_verifier_missing"]
    assert ready_status == 202
    assert ready["raw_update_persisted"] is False
    assert ready["action_executed"] is False
    assert len(ready["update_hash"]) == 64


def test_http_service_rejects_non_loopback_bind() -> None:
    with pytest.raises(ValueError, match="loopback"):
        serve_cortex_http(host="0.0.0.0", port=8765)
