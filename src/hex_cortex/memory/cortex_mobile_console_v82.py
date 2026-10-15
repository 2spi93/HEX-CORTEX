"""V8.2 private mobile console: CPU-only, read-only, no robot commands.

This intentionally runs as a SEPARATE loopback HTTP service. Publish it only
through private HTTPS with Tailscale Serve, not a public port or Funnel.
The browser camera remains on-device; no photos are sent to this service.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_mobile_view_v82 import CSS, HTML, JS
from hex_cortex.memory.cortex_deepseek_sdk_receipt_v8 import imported_sdk_pilot_summary

_TAILNET = re.compile(r"[a-z0-9](?:[a-z0-9.-]{2,240}[a-z0-9])?\.ts\.net\Z")
_HEADERS = {
    "Cache-Control": "no-store",
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=()",
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; "
        "img-src 'self' blob: data:; connect-src 'self'; "
        "media-src blob:; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
}


def mobile_status(project_root: Path) -> dict:
    """Expose only a fixed public capability shape, never repository content."""
    try:
        receipt = imported_sdk_pilot_summary(project_root)
        receipt_status = receipt["status"]
    except (OSError, ValueError, TypeError, KeyError):
        receipt_status = "local_receipt_rejected"
    return {
        "schema": "hex.mobile_console.v82",
        "mode": "read_only_private_https_cpu",
        "camera": "browser_local_permission_required",
        "photo_uploaded": False,
        "phone_microphone_streamed": False,
        "deepseek_sdk_pilot_receipt": receipt_status,
        "deepseek_agent_connected": False,
        "deepseek_tools_connected": False,
        "local_cpu_model_called": False,
        "command_center_v8_proxied": False,
        "drone_telemetry_connected": False,
        "drone_actuation_enabled": False,
        "hardware_commands_available": [],
        "server_gpu_used": False,
    }


class MobileConsoleHandler(BaseHTTPRequestHandler):
    server_version = "HEX-CORTEX-Mobile/8.2"

    def log_message(self, _format: str, *args: object) -> None:
        """Never log credentials, URL queries or client-supplied headers."""

    def _respond(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for k, v in _HEADERS.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def _authorized_host(self) -> bool:
        host = self.headers.get("Host", "").lower()
        port = self.server.server_port
        if host in {f"127.0.0.1:{port}", f"localhost:{port}"}:
            return True
        remote = self.server.tailnet_host
        return bool(
            remote and host in {remote, remote + ":443"}
            and self.headers.get("X-Forwarded-Proto") == "https"
        )

    def _authenticated(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic ") or len(header) > 250:
            return False
        try:
            raw = base64.b64decode(header[6:], validate=True).decode("utf-8")
        except (ValueError, UnicodeDecodeError, binascii.Error):
            return False
        name, sep, password = raw.partition(":")
        return bool(
            sep and secrets.compare_digest(name, "operator")
            and secrets.compare_digest(password, self.server.operator_password)
        )

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized_host():
            self._respond(HTTPStatus.FORBIDDEN, b"Host denied", "text/plain")
            return
        if not self._authenticated():
            self.send_response(HTTPStatus.UNAUTHORIZED)
            self.send_header("WWW-Authenticate", 'Basic realm="HEX-CORTEX Mobile"')
            self.send_header("Content-Length", "0")
            for k, v in _HEADERS.items():
                self.send_header(k, v)
            self.end_headers()
            return
        url = urlsplit(self.path)
        if url.query or url.fragment:
            self._respond(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            return
        assets = {
            "/": (HTML.encode("utf-8"), "text/html; charset=utf-8"),
            "/assets/mobile.css": (CSS.encode("utf-8"), "text/css; charset=utf-8"),
            "/assets/mobile.js": (JS.encode("utf-8"), "text/javascript; charset=utf-8"),
        }
        if url.path == "/api/mobile/status":
            data = json.dumps(mobile_status(self.server.project_root), sort_keys=True)
            self._respond(HTTPStatus.OK, data.encode("utf-8"), "application/json")
        elif url.path in assets:
            payload, kind = assets[url.path]
            self._respond(HTTPStatus.OK, payload, kind)
        else:
            self._respond(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")

    def do_POST(self) -> None:  # noqa: N802
        self._respond(HTTPStatus.METHOD_NOT_ALLOWED, b"Read only", "text/plain")


class MobileConsoleServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(
        self, project_root: Path, port: int, *, operator_password: str,
        tailnet_host: str = "",
    ) -> None:
        if len(operator_password) < 24 or len(operator_password) > 180:
            raise ValueError("high_entropy_operator_password_required")
        if tailnet_host and not _TAILNET.fullmatch(tailnet_host):
            raise ValueError("tailnet_host_must_be_exact_ts_net_hostname")
        if not 1024 <= port <= 65535:
            raise ValueError("port_out_of_range")
        root = project_root.resolve(strict=True)
        if not root.is_dir():
            raise ValueError("invalid_project_root")
        super().__init__(("127.0.0.1", port), MobileConsoleHandler)
        self.project_root = root
        self.operator_password = operator_password
        self.tailnet_host = tailnet_host


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private CPU mobile console, no actuation")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--port", type=int, default=8788)
    parser.add_argument("--tailnet-host", default="",
                        help="Exact private HTTPS hostname e.g. pc.example.ts.net")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    password = os.environ.get("HEX_CORTEX_MOBILE_PASSWORD", "")
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only",
            "operator_password_configured": 24 <= len(password) <= 180,
            "bind_host": "127.0.0.1",
            "tailnet_host_configured": bool(args.tailnet_host),
            "model_called": False,
            "camera_upload_enabled": False,
            "drone_actuation_enabled": False,
        }, sort_keys=True))
        return 0
    try:
        with MobileConsoleServer(
            args.project_root, args.port, operator_password=password,
            tailnet_host=args.tailnet_host,
        ) as server:
            print(f"HEX-CORTEX Mobile: http://127.0.0.1:{server.server_port}/ "
                  "private HTTPS proxy only; read-only.", flush=True)
            server.serve_forever()
    except (OSError, ValueError):
        print(json.dumps({"status": "blocked", "reason": "mobile_server_configuration_denied"}))
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
