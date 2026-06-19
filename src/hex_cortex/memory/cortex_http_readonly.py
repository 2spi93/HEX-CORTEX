from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_surfaces import list_cortex_surfaces
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring

HeaderVerifier = Callable[[dict[str, str]], bool]


def dispatch_cortex_http(
    *,
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
    hook_verifier: HeaderVerifier | None = None,
) -> tuple[int, dict[str, object]]:
    if method == "GET" and path == "/healthz":
        return 200, {"status": "ok", "service": "hex-cortex"}
    if method == "GET" and path == "/v1/read/wiring":
        return 200, audit_cortex_wiring(build_cortex_bundle())
    if method == "GET" and path == "/v1/read/surfaces":
        rows = list_cortex_surfaces()
        return 200, {"status": "ok", "surface_count": len(rows), "surfaces": rows}
    if method == "POST" and path == "/v1/hooks/telegram":
        if hook_verifier is None:
            return 503, {"status": "blocked", "blockers": ["hook_verifier_missing"]}
        normalized_headers = {key.lower(): value for key, value in (headers or {}).items()}
        if not hook_verifier(normalized_headers):
            return 401, {"status": "blocked", "blockers": ["hook_not_authorized"]}
        if len(body) > 2 * 1024 * 1024:
            return 413, {"status": "blocked", "blockers": ["request_too_large"]}
        try:
            payload: Any = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return 400, {"status": "blocked", "blockers": ["invalid_json"]}
        if not isinstance(payload, dict):
            return 400, {"status": "blocked", "blockers": ["payload_must_be_object"]}
        return 202, {
            "status": "accepted",
            "update_hash": hashlib.sha256(body).hexdigest(),
            "raw_update_persisted": False,
            "action_executed": False,
            "next_action": "queue_telegram_update",
        }
    return 404, {"status": "blocked", "blockers": ["route_not_found"]}


def build_cortex_http_handler(
    *,
    hook_verifier: HeaderVerifier | None = None,
):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - stdlib callback name.
            self._respond("GET", b"")

        def do_POST(self) -> None:  # noqa: N802 - stdlib callback name.
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(min(length, 2 * 1024 * 1024 + 1))
            self._respond("POST", body)

        def _respond(self, method: str, body: bytes) -> None:
            status, payload = dispatch_cortex_http(
                method=method,
                path=self.path,
                body=body,
                headers={key: value for key, value in self.headers.items()},
                hook_verifier=hook_verifier,
            )
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format: str, *args: object) -> None:
            return

    return Handler


def serve_cortex_http(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    hook_verifier: HeaderVerifier | None = None,
) -> int:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("HTTP service must bind to loopback")
    if port < 1024 or port > 65535:
        raise ValueError("port must be in [1024, 65535]")
    server = ThreadingHTTPServer(
        (host, port),
        build_cortex_http_handler(hook_verifier=hook_verifier),
    )
    server.serve_forever()
    return 0
