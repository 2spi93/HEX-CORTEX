"""Command Center V4: fixed-path code inspector + device capability boundary.

Live physical robots/drones are deliberately NOT connected; the UI may
simulate commands only. Phone/camera media stays in the browser, never uploaded.
"""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from hex_cortex.memory.cortex_command_center_v1 import _safe_path
from hex_cortex.memory.cortex_command_center_v3 import (
    CommandCenterV3Handler,
    CommandCenterV3Server,
)
from hex_cortex.memory.cortex_command_center_view_v4 import CSS, HTML, JS

_CODE_ALLOWLIST = {
    "harness": "src/hex_cortex/memory/cortex_local_harness_v2.py",
    "brain": "src/hex_cortex/memory/cortex_local_ollama_brain.py",
    "command_center": "src/hex_cortex/memory/cortex_command_center_v3.py",
    "spine": "src/hex_cortex/spine/jsonl_store.py",
    "architecture": "docs/COMMAND_CENTER_V3_CONVERSATION_CONTINUITY.md",
}


def device_capabilities() -> dict:
    return {
        "schema": "hex.devices.capabilities.v4",
        "host_access": "browser_camera_and_microphone_permission_only",
        "real_robot_drone_commands_enabled": False,
        "phone_remote_control_enabled": False,
        "execution_modes": ["read", "browser_local_simulation"],
        "device_types": [
            {"id": "camera", "name": "Caméra locale",
             "state": "browser_permission_required",
             "actions": ["preview", "capture_local_frame", "stop"]},
            {"id": "microphone", "name": "Microphone local",
             "state": "browser_permission_required",
             "actions": ["push_to_talk_if_supported", "stop"]},
            {"id": "phone", "name": "Téléphone distant",
             "state": "not_paired", "actions": []},
            {"id": "drone", "name": "Drone",
             "state": "simulation_only", "actions": []},
            {"id": "robot", "name": "Robot",
             "state": "simulation_only", "actions": []},
            {"id": "iot", "name": "Domotique et capteurs",
             "state": "not_connected", "actions": []},
        ],
        "future_live_control_requirements": [
            "explicit_pairing", "authenticated_adapters", "scoped_permissions",
            "safety_interlocks", "e_stop", "human_supervision",
            "verified_sdk_and_hardware_tests",
        ],
    }


def code_inventory() -> dict:
    return {
        "schema": "hex.code_inspector.v4",
        "readonly": True,
        "entries": [
            {"id": key, "path": value}
            for key, value in _CODE_ALLOWLIST.items()
        ],
        "execution_enabled": False,
        "editing_enabled": False,
    }


def read_allowlisted_source(root: Path, name: str) -> dict:
    if name not in _CODE_ALLOWLIST:
        raise ValueError("source_not_allowlisted")
    path = _safe_path(root, Path(_CODE_ALLOWLIST[name]))
    if not path.is_file() or not 0 < path.stat().st_size <= 180_000:
        raise ValueError("source_unavailable_or_too_large")
    raw = path.read_bytes()
    if len(raw) > 180_000:
        raise ValueError("source_too_large")
    contents = raw.decode("utf-8")
    return {
        "status": "source_loaded",
        "id": name,
        "path": _CODE_ALLOWLIST[name],
        "contents": contents,
        "read_only": True,
        "execution_permitted": False,
    }


class CommandCenterV4Handler(CommandCenterV3Handler):
    server_version = "HEX-CORTEX-CommandCenter/4.0"

    def _reply(self, status: HTTPStatus, body: bytes, kind: str = "application/json") -> None:
        # Override V1's "camera=(), microphone=()" to make *user-approved*
        # local browser media functional. Access is never automatic.
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Permissions-Policy",
            "camera=(self), microphone=(self), geolocation=()",
        )
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' blob:; media-src 'self' blob:; "
            "connect-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        parsed = urlsplit(self.path)
        if parsed.path == "/" and not parsed.query:
            self._reply(HTTPStatus.OK, HTML.encode(), "text/html; charset=utf-8")
        elif parsed.path == "/assets/command-center.js" and not parsed.query:
            self._reply(HTTPStatus.OK, JS.encode(), "text/javascript; charset=utf-8")
        elif parsed.path == "/assets/command-center.css" and not parsed.query:
            self._reply(HTTPStatus.OK, CSS.encode(), "text/css; charset=utf-8")
        elif parsed.path == "/api/devices/capabilities" and not parsed.query:
            self._json(HTTPStatus.OK, device_capabilities())
        elif parsed.path == "/api/code/inventory" and not parsed.query:
            self._json(HTTPStatus.OK, code_inventory())
        elif parsed.path == "/api/code/source":
            args = parse_qs(parsed.query, keep_blank_values=True)
            if set(args) != {"name"} or len(args["name"]) != 1:
                self._json(HTTPStatus.BAD_REQUEST, {
                    "status": "blocked", "reason": "source_name_required",
                })
                return
            try:
                result = read_allowlisted_source(self.server.project_root, args["name"][0])
            except (OSError, UnicodeError, ValueError):
                self._json(HTTPStatus.NOT_FOUND, {
                    "status": "blocked", "reason": "source_not_available",
                })
                return
            self._json(HTTPStatus.OK, result)
        else:
            return super().do_GET()


class CommandCenterV4Server(CommandCenterV3Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
    ):
        super().__init__(project_root, port, chat_enabled=chat_enabled)
        self.RequestHandlerClass = CommandCenterV4Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HEX-CORTEX V4: local multimodal Command Center")
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--enable-cpu-chat", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "port": args.port,
            "host": "127.0.0.1", "cpu_chat_enabled": args.enable_cpu_chat,
            "camera_requires_browser_permission": True,
            "microphone_requires_browser_permission": True,
            "remote_devices_enabled": False,
            "network_used": False, "files_written": False, "model_called": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV4Server(
            args.project_root, args.port, chat_enabled=args.enable_cpu_chat,
        ) as server:
            print(
                f"HEX-CORTEX V4: http://127.0.0.1:{server.server_port}/ "
                "Media: browser permission only; remote devices: disabled.",
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
