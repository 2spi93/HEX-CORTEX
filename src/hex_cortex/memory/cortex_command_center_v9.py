"""Command Center V9: V8 backend unchanged, mobile bbox proof import in UI."""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_v8 import (
    CommandCenterV8Handler,
    CommandCenterV8Server,
)
from hex_cortex.memory.cortex_command_center_view_v9 import CSS, HTML, JS


class CommandCenterV9Handler(CommandCenterV8Handler):
    server_version = "HEX-CORTEX-CommandCenter/9.0"

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
        else:
            super().do_GET()


class CommandCenterV9Server(CommandCenterV8Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
        vision_enabled: bool = False,
    ):
        super().__init__(
            project_root, port, chat_enabled=chat_enabled,
            vision_enabled=vision_enabled,
        )
        self.RequestHandlerClass = CommandCenterV9Handler


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="HEX-CORTEX V9 Android-to-CPU-vision verified bbox")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--enable-cpu-chat", action="store_true")
    parser.add_argument("--enable-cpu-vision", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1",
            "port": args.port, "chat_enabled": args.enable_cpu_chat,
            "vision_enabled": args.enable_cpu_vision,
            "mobile_bbox_sha256_verification_in_browser": True,
            "remote_phone_control": False,
            "model_called": False, "files_written": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV9Server(
            args.project_root, args.port, chat_enabled=args.enable_cpu_chat,
            vision_enabled=args.enable_cpu_vision,
        ) as server:
            print(
                f"HEX-CORTEX V9: http://127.0.0.1:{server.server_port}/ "
                "Mobile JSON bbox import active; no automatic inference",
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
