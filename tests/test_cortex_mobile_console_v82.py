"""V8.2 mobile console: no secret leaks, host allowlist and no actuator paths."""
from __future__ import annotations

import base64
import http.client
import json
import socket
import threading
from contextlib import contextmanager

import pytest

from hex_cortex.memory.cortex_mobile_console_v82 import (
    MobileConsoleServer,
    main,
    mobile_status,
)
from hex_cortex.memory.cortex_mobile_view_v82 import HTML, JS

_PASSWORD = "local-only-high-entropy-example-password-2026"


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@contextmanager
def _server(root, *, tailnet_host=""):
    srv = MobileConsoleServer(
        root, _free_port(), operator_password=_PASSWORD,
        tailnet_host=tailnet_host,
    )
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        yield srv.server_port
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(timeout=4)


def _get(port, path="/api/mobile/status", *, password=_PASSWORD,
         host=None, forwarded_https=None, method="GET"):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=4)
    token = base64.b64encode(f"operator:{password}".encode()).decode()
    headers = {"Host": host or f"127.0.0.1:{port}", "Authorization": f"Basic {token}"}
    if forwarded_https is not None:
        headers["X-Forwarded-Proto"] = forwarded_https
    conn.request(method, path, headers=headers)
    response = conn.getresponse()
    data = response.read()
    hdr = dict(response.getheaders())
    conn.close()
    return response.status, data, hdr


def test_authentication_required_and_strong_password(tmp_path):
    with pytest.raises(ValueError, match="high_entropy"):
        MobileConsoleServer(tmp_path, _free_port(), operator_password="too-short")
    with _server(tmp_path) as port:
        status, _, _ = _get(port, password="incorrect-but-long-enough")
        assert status == 401
        status, body, hdr = _get(port)
        assert status == 200
        assert hdr["Content-Security-Policy"].startswith("default-src 'none'")
        assert hdr["Cache-Control"] == "no-store"
        assert _PASSWORD.encode() not in body


def test_status_is_redacted_and_does_not_claim_deepseek_or_flight(tmp_path):
    record = mobile_status(tmp_path)
    assert record["deepseek_agent_connected"] is False
    assert record["deepseek_tools_connected"] is False
    assert record["drone_actuation_enabled"] is False
    assert record["hardware_commands_available"] == []
    assert record["photo_uploaded"] is False
    assert list(tmp_path.iterdir()) == []
    with _server(tmp_path) as port:
        code, raw, _ = _get(port)
        assert code == 200
        parsed = json.loads(raw)
        assert parsed == record
        assert "model_prompt" not in parsed


def test_host_and_routes_blocked_by_default(tmp_path):
    with _server(tmp_path) as port:
        assert _get(port, host="attacker.example")[0] == 403
        assert _get(port, "/api/drone/takeoff", method="POST")[0] == 405
        assert _get(port, "/api/mobile/status?dump=1")[0] == 404
        assert _get(port, "/api/vision/cpu/segment", method="POST")[0] == 405
        assert _get(port, "/api/secrets")[0] == 404


def test_exact_private_tailnet_hostname_only(tmp_path):
    with pytest.raises(ValueError, match="tailnet"):
        MobileConsoleServer(
            tmp_path, _free_port(), operator_password=_PASSWORD,
            tailnet_host="public.example.org",
        )
    with _server(tmp_path, tailnet_host="pc.example.ts.net") as port:
        assert _get(port, host="pc.example.ts.net")[0] == 403
        assert _get(port, host="pc.example.ts.net",
                    forwarded_https="https")[0] == 200
        assert _get(port, host="evil.example.ts.net",
                    forwarded_https="https")[0] == 403


def test_local_camera_never_uploads_images(tmp_path):
    with _server(tmp_path) as port:
        code, html, _ = _get(port, "/")
        assert code == 200
        assert b"/assets/mobile.js" in html
        code, js, _ = _get(port, "/assets/mobile.js")
        assert code == 200
        assert b"getUserMedia" in js
        assert b"canvas.toBlob" in js
        assert b"/api/vision/cpu/segment" not in js
        assert b"method:'POST'" not in js
        assert b"fetch('/api/mobile/status'" in js
        assert b"window.isSecureContext" in js
        assert "drone" in HTML
        assert "photoUrl" in JS


def test_dry_run_only_reports_configuration(monkeypatch, capsys):
    monkeypatch.setenv("HEX_CORTEX_MOBILE_PASSWORD", _PASSWORD)
    assert main(["--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["operator_password_configured"] is True
    assert data["camera_upload_enabled"] is False
    assert data["drone_actuation_enabled"] is False
