from __future__ import annotations

import hashlib
import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from hex_cortex.memory.cortex_federation_queue import enqueue_federation_task
from hex_cortex.memory.cortex_server_federation_audit import audit_server_federation
from hex_cortex.memory.cortex_server_federation_audit import build_hermes_autodiscovery_plan


def serve() -> None:
    host = os.environ.get("HEX_CORTEX_API_HOST", "127.0.0.1")
    port = int(os.environ.get("HEX_CORTEX_API_PORT", "8765"))
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("internal API must bind to localhost; expose it through a reverse proxy")
    server = ThreadingHTTPServer((host, port), CortexRequestHandler)
    server.serve_forever()


class CortexRequestHandler(BaseHTTPRequestHandler):
    server_version = "HEX-CORTEX/1.0"

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract.
        path = urlparse(self.path).path
        if path == "/health":
            self._write_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "hex-cortex-internal-api",
                    "public_bind": False,
                    "memory_policy": "separate_no_merge",
                },
            )
            return
        if path == "/v1/hermes/autodiscovery":
            self._write_json(HTTPStatus.OK, build_hermes_autodiscovery_plan())
            return
        if path == "/v1/federation/audit":
            self._write_json(
                HTTPStatus.OK,
                audit_server_federation(runtime_facts=_runtime_facts_from_environment()),
            )
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"status": "blocked", "blocker": "route_unknown"})

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler contract.
        path = urlparse(self.path).path
        if path == "/v1/tasks/enqueue":
            self._enqueue_task()
            return
        if path == "/v1/webhooks/telegram":
            self._telegram_webhook()
            return
        self._write_json(HTTPStatus.NOT_FOUND, {"status": "blocked", "blocker": "route_unknown"})

    def log_message(self, format: str, *args: object) -> None:
        return

    def _enqueue_task(self) -> None:
        signing_key = os.environ.get("HEX_CORTEX_FEDERATION_SIGNING_KEY", "")
        if not signing_key:
            self._write_json(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {"status": "blocked", "blockers": ["federation_signing_key_missing"]},
            )
            return
        payload = self._read_json()
        if payload is None:
            return
        envelope = payload.get("envelope")
        if not isinstance(envelope, dict):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "blocked", "blockers": ["envelope_missing"]},
            )
            return
        result = enqueue_federation_task(
            _profile_path(),
            envelope=envelope,
            signing_key=signing_key.encode("utf-8"),
        )
        status = HTTPStatus.ACCEPTED if result.get("queue_allowed") is True else HTTPStatus.FORBIDDEN
        self._write_json(status, result)

    def _telegram_webhook(self) -> None:
        expected = os.environ.get("HEX_CORTEX_TELEGRAM_WEBHOOK_SECRET", "")
        observed = self.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if not expected or not observed or not hashlib.sha256(observed.encode()).digest() == hashlib.sha256(expected.encode()).digest():
            self._write_json(
                HTTPStatus.FORBIDDEN,
                {"status": "blocked", "blockers": ["telegram_webhook_secret_invalid"]},
            )
            return
        raw = self._read_body()
        if raw is None:
            return
        receipt = {
            "status": "accepted",
            "update_hash": hashlib.sha256(raw).hexdigest(),
            "raw_update_persisted": False,
            "message_sent": False,
            "next_action": "dispatch_telegram_update_to_read_only_handler",
        }
        self._write_json(HTTPStatus.OK, receipt)

    def _read_json(self) -> dict[str, object] | None:
        raw = self._read_body()
        if raw is None:
            return None
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "blocked", "blockers": ["invalid_json"]},
            )
            return None
        if not isinstance(payload, dict):
            self._write_json(
                HTTPStatus.BAD_REQUEST,
                {"status": "blocked", "blockers": ["json_object_required"]},
            )
            return None
        return payload

    def _read_body(self) -> bytes | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length < 1 or length > 1_000_000:
            self._write_json(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {"status": "blocked", "blockers": ["request_size_invalid"]},
            )
            return None
        return self.rfile.read(length)

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload, sort_keys=True).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)


def _profile_path() -> Path:
    return Path(os.environ.get("HEX_CORTEX_PROFILE", ".hex-cortex"))


def _runtime_facts_from_environment() -> dict[str, bool]:
    names = (
        "internal_api_available",
        "https_reverse_proxy_available",
        "private_or_tunneled_transport_available",
        "server_worker_queue_available",
        "signed_task_envelopes_available",
        "remote_receipts_available",
        "hermes_autodiscovery_available",
        "gtixt_read_only_audit_available",
    )
    return {
        name: os.environ.get(f"HEX_CORTEX_{name.upper()}", "false").lower() == "true"
        for name in names
    }


if __name__ == "__main__":
    serve()
