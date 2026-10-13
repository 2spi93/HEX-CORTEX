"""V8 DeepSeek SDK pilot observation: read only, external VM executes agent."""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_v7 import (
    CommandCenterV7Handler, CommandCenterV7Server,
)
from hex_cortex.memory.cortex_command_center_view_v8 import CSS, HTML, JS
from hex_cortex.memory.cortex_deepseek_sdk_receipt_v8 import (
    imported_sdk_pilot_summary,
)


class CommandCenterV8Handler(CommandCenterV7Handler):
    server_version = "HEX-CORTEX-CommandCenter/8.0"

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        p = urlsplit(self.path)
        if p.path == "/" and not p.query:
            self._reply(HTTPStatus.OK, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif p.path == "/assets/command-center.js" and not p.query:
            self._reply(HTTPStatus.OK, JS.encode("utf-8"), "text/javascript; charset=utf-8")
        elif p.path == "/assets/command-center.css" and not p.query:
            self._reply(HTTPStatus.OK, CSS.encode("utf-8"), "text/css; charset=utf-8")
        elif p.path == "/api/integrations/deepseek-harness/pilot" and not p.query:
            try:
                result = imported_sdk_pilot_summary(self.server.project_root)
            except (ValueError, OSError, TypeError):
                self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                    "status": "blocked", "reason": "v8_receipt_rejected",
                })
                return
            self._json(HTTPStatus.OK, result)
        else:
            super().do_GET()


class CommandCenterV8Server(CommandCenterV7Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
        vision_enabled: bool = False,
    ):
        super().__init__(
            project_root, port, chat_enabled=chat_enabled, vision_enabled=vision_enabled,
        )
        self.RequestHandlerClass = CommandCenterV8Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="HEX-CORTEX V8: display external VM SDK pilot evidence",
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--enable-cpu-chat", action="store_true")
    p.add_argument("--enable-cpu-vision", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if not 1024 <= a.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if a.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1", "port": a.port,
            "chat_enabled": a.enable_cpu_chat, "vision_enabled": a.enable_cpu_vision,
            "deepseek_sdk_operated_by_server": False, "tool_execution_enabled": False,
            "pilot_receipt_read_only": True, "model_called": False,
            "files_written": False, "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV8Server(
            a.project_root, a.port, chat_enabled=a.enable_cpu_chat,
            vision_enabled=a.enable_cpu_vision,
        ) as server:
            print(
                f"HEX-CORTEX V8: http://127.0.0.1:{server.server_port}/ "
                "DSH SDK pilot: independent VM only, no host actions.",
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
