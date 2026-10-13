"""Command Center V3: bounded role-aware conversation, browser-only context.

History is supplied per request by the browser, considered *untrusted* and
never saved on the server. Each inference passes through the existing
LocalHarness + LocalOllamaBrain with CALL_MODEL only, num_gpu=0 and no tools.
"""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_chat_v2 import safe_cpu_chat
from hex_cortex.memory.cortex_command_center_v2 import (
    CommandCenterV2Handler,
    CommandCenterV2Server,
    capabilities,
)
from hex_cortex.memory.cortex_command_center_view_v3 import CSS, HTML, JS


def _history_from_wire(value: object) -> tuple[tuple[str, str], ...]:
    """Three complete previous exchanges max; retain role separation."""
    if not isinstance(value, list) or len(value) > 6 or len(value) % 2:
        raise ValueError("v3_history_length_invalid")
    history: list[tuple[str, str]] = []
    for index, turn in enumerate(value):
        expected = "user" if index % 2 == 0 else "assistant"
        if (
            not isinstance(turn, dict)
            or set(turn) != {"role", "content"}
            or turn["role"] != expected
            or not isinstance(turn["content"], str)
            or not 0 < len(turn["content"].strip()) <= 600
        ):
            raise ValueError("v3_history_turn_invalid")
        history.append((expected, turn["content"]))
    return tuple(history)


class CommandCenterV3Handler(CommandCenterV2Handler):
    server_version = "HEX-CORTEX-CommandCenter/3.0"

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        parsed = urlsplit(self.path)
        if not parsed.query and parsed.path == "/":
            self._reply(HTTPStatus.OK, HTML.encode(), "text/html; charset=utf-8")
        elif not parsed.query and parsed.path == "/assets/command-center.css":
            self._reply(HTTPStatus.OK, CSS.encode(), "text/css; charset=utf-8")
        elif not parsed.query and parsed.path == "/assets/command-center.js":
            self._reply(HTTPStatus.OK, JS.encode(), "text/javascript; charset=utf-8")
        elif not parsed.query and parsed.path == "/api/capabilities":
            catalog = capabilities(chat_enabled=self.server.chat_enabled)
            catalog["schema"] = "hex.command_center.capabilities.v3"
            for feature in catalog["features"]:
                if feature["id"] == "chat":
                    feature["action"] = "bounded_three_exchange_context_no_tools"
            self._json(HTTPStatus.OK, catalog)
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlsplit(self.path)
        if parsed.path != "/api/ollama/conversation" or parsed.query:
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
        size_raw = self.headers.get("Content-Length", "")
        if not size_raw.isascii() or not size_raw.isdecimal():
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "invalid_content_length",
            })
            return
        size = int(size_raw)
        if not 0 < size <= 8_192:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "status": "blocked", "reason": "conversation_payload_too_large",
            })
            return
        try:
            payload = json.loads(self.rfile.read(size).decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"prompt", "model", "history"}
                or not isinstance(payload["model"], str)
                or not 0 < len(payload["model"]) <= 120
                or not isinstance(payload["prompt"], str)
                or not 0 < len(payload["prompt"].strip()) <= 1600
            ):
                raise ValueError("v3_invalid_conversation")
            history = _history_from_wire(payload["history"])
        except (ValueError, UnicodeError, KeyError, TypeError):
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "conversation_context_invalid",
            })
            return
        if not self.server.chat_gate.acquire(blocking=False):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {
                "status": "busy", "reason": "one_cpu_inference_at_a_time",
            })
            return
        try:
            result = safe_cpu_chat(
                root=self.server.project_root, model=payload["model"],
                prompt=payload["prompt"], history=history,
            )
        except (OSError, ValueError, RuntimeError, KeyError, TypeError):
            self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                "status": "blocked", "reason": "local_cpu_inference_unavailable",
            })
        else:
            result["conversation_context_provenance"] = "browser_supplied_ephemeral_untrusted"
            result["history_items_used"] = len(history)
            result["server_history_persisted"] = False
            result["automatic_tool_use"] = False
            self._json(
                HTTPStatus.OK if result["status"] == "completed"
                else HTTPStatus.SERVICE_UNAVAILABLE, result,
            )
        finally:
            self.server.chat_gate.release()


class CommandCenterV3Server(CommandCenterV2Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
    ):
        super().__init__(project_root, port, chat_enabled=chat_enabled)
        self.RequestHandlerClass = CommandCenterV3Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HEX-CORTEX V3 conversation / model adapter")
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--enable-cpu-chat", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if not 1024 <= a.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if a.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1",
            "port": a.port, "chat_enabled": a.enable_cpu_chat,
            "context_max_previous_exchanges": 3,
            "files_written": False, "model_called": False, "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV3Server(
            a.project_root, a.port, chat_enabled=a.enable_cpu_chat,
        ) as server:
            print(
                f"HEX-CORTEX V3: http://127.0.0.1:{server.server_port}/ "
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
