"""Local Command Center V2: fluent tabs, opt-in CPU chat, capability catalog.

Extends the protected V1 web application rather than copying its API or
permissions. In particular, it cannot expose V1's mutating server API.
"""
from __future__ import annotations

import argparse
import json
import threading
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_chat_v2 import (
    available_models,
    safe_cpu_chat,
)
from hex_cortex.memory.cortex_command_center_v1 import (
    CommandCenterHandler,
    CommandCenterServer,
)
from hex_cortex.memory.cortex_command_center_view_v2 import CSS, HTML, JS


def capabilities(*, chat_enabled: bool) -> dict:
    """Explicit accurate distinction: existing code, connected, or not wired."""
    return {
        "schema": "hex.command_center.capabilities.v2",
        "features": [
            {"id": "harness", "name": "LocalHarness V2",
             "status": "connected_readonly", "action": "repo_manifest"},
            {"id": "vision", "name": "MobileSAM / V40",
             "status": "connected_receipt_viewer", "action": "existing_previews_only"},
            {"id": "spine", "name": "CanonicalSpine / V43",
             "status": "connected_local_ledger_reader", "action": "integrity_and_counts"},
            {"id": "chat", "name": "Ollama / LocalOllamaBrain",
             "status": "enabled_cpu_opt_in" if chat_enabled else "disabled_until_launch_opt_in",
             "action": "single_turn_without_tools"},
            {"id": "mcp", "name": "MCP tools",
             "status": "existing_modules_not_exposed", "action": "requires_gateway_review"},
            {"id": "world", "name": "World Model / DINOv2",
             "status": "existing_modules_not_exposed", "action": "requires_eval_gate"},
            {"id": "voice", "name": "Wake word / STT / TTS",
             "status": "not_connected", "action": "not_available"},
            {"id": "desktop", "name": "Windows desktop actions",
             "status": "not_connected", "action": "not_available"},
            {"id": "agents", "name": "Scheduled Jarvis agents",
             "status": "not_connected", "action": "not_available"},
            {"id": "skills", "name": "Skill catalog / Replay",
             "status": "existing_modules_not_exposed", "action": "requires_sandbox_and_review"},
        ],
        "automatic_tools_enabled": False,
        "gpu_access_enabled": False,
        "cloud_access_enabled": False,
    }


class CommandCenterV2Handler(CommandCenterHandler):
    server_version = "HEX-CORTEX-CommandCenter/2.0"

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        parsed = urlsplit(self.path)
        if parsed.query:
            return super().do_GET()
        if parsed.path == "/":
            self._reply(HTTPStatus.OK, HTML.encode(), "text/html; charset=utf-8")
        elif parsed.path == "/assets/command-center.css":
            self._reply(HTTPStatus.OK, CSS.encode(), "text/css; charset=utf-8")
        elif parsed.path == "/assets/command-center.js":
            self._reply(HTTPStatus.OK, JS.encode(), "text/javascript; charset=utf-8")
        elif parsed.path == "/api/capabilities":
            self._json(HTTPStatus.OK, capabilities(chat_enabled=self.server.chat_enabled))
        elif parsed.path == "/api/ollama/models":
            if not self.server.chat_enabled:
                self._json(HTTPStatus.FORBIDDEN, {
                    "status": "disabled", "reason": "cpu_chat_not_enabled_at_launch",
                })
                return
            try:
                names = available_models()
            except (OSError, ValueError, KeyError, TypeError):
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                    "status": "unavailable", "reason": "local_ollama_unavailable",
                    "models": [],
                })
                return
            self._json(HTTPStatus.OK, {
                "status": "available", "models": names,
                "source": "local_ollama_api_tags",
                "gpu_usage": "model_not_loaded_for_inventory",
            })
        else:
            return super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/api/ollama/chat" or parsed.query:
            return super().do_POST()
        if not self._allowed_request():
            return
        if not self.server.chat_enabled:
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "cpu_chat_not_enabled_at_launch",
            })
            return
        if (
            self.headers.get("Origin") != f"http://{self.headers.get('Host')}"
            or self.headers.get("X-HEX-Chat-Approval") != "single-cpu-request"
            or self.headers.get("Content-Type") != "application/json"
            or self.headers.get("Transfer-Encoding") is not None
        ):
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "explicit_same_origin_approval_required",
            })
            return
        raw_length = self.headers.get("Content-Length", "")
        if not raw_length.isascii() or not raw_length.isdecimal():
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "invalid_content_length",
            })
            return
        size = int(raw_length)
        if not 0 < size <= 4096:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "status": "blocked", "reason": "chat_payload_too_large",
            })
            return
        try:
            data = json.loads(self.rfile.read(size).decode("utf-8"))
        except (ValueError, UnicodeError):
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "invalid_json",
            })
            return
        if (
            not isinstance(data, dict)
            or set(data) != {"prompt", "model"}
            or not isinstance(data["prompt"], str)
            or not isinstance(data["model"], str)
            or not 0 < len(data["prompt"].strip()) <= 1600
            or not 0 < len(data["model"]) <= 120
        ):
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "invalid_chat_request",
            })
            return
        if not self.server.chat_gate.acquire(blocking=False):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {
                "status": "busy", "reason": "one_cpu_inference_at_a_time",
            })
            return
        try:
            reply = safe_cpu_chat(
                root=self.server.project_root,
                model=data["model"], prompt=data["prompt"],
            )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "status": "blocked", "reason": "local_cpu_inference_unavailable",
            })
        else:
            self._json(
                HTTPStatus.OK if reply["status"] == "completed"
                else HTTPStatus.SERVICE_UNAVAILABLE,
                reply,
            )
        finally:
            self.server.chat_gate.release()


class CommandCenterV2Server(CommandCenterServer):
    def __init__(self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False):
        self.chat_enabled = chat_enabled
        self.chat_gate = threading.BoundedSemaphore(1)
        super().__init__(project_root, port)
        self.RequestHandlerClass = CommandCenterV2Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HEX-CORTEX command center V2; loopback only")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--enable-cpu-chat", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1",
            "port": args.port, "chat_enabled": args.enable_cpu_chat,
            "model_called": False, "files_written": False,
            "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV2Server(
            args.project_root, args.port, chat_enabled=args.enable_cpu_chat,
        ) as server:
            print(
                f"HEX-CORTEX Command Center V2: http://127.0.0.1:{server.server_port}/ "
                f"CPU chat: {'opt-in' if server.chat_enabled else 'disabled'}",
                flush=True,
            )
            server.serve_forever()
    except (OSError, ValueError):
        print(json.dumps({"status": "blocked", "reason": "loopback_bind_failed"}))
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
