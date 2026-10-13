"""V7 coexistence gateway: safe DSH inventory, zero execution and no data egress.

The official DeepSeek Harness is an independent third-party agent runtime.
This route intentionally DOES NOT start it or offer a model-facing tool.
"""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_v6 import (
    CommandCenterV6Handler,
    CommandCenterV6Server,
)
from hex_cortex.memory.cortex_command_center_view_v7 import CSS, HTML, JS
from hex_cortex.memory.cortex_deepseek_harness_bridge_v7 import (
    deepseek_harness_bridge_status,
)


class CommandCenterV7Handler(CommandCenterV6Handler):
    server_version = "HEX-CORTEX-CommandCenter/7.0"

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
        elif p.path == "/api/integrations/deepseek-harness" and not p.query:
            try:
                status = deepseek_harness_bridge_status(self.server.project_root)
            except (OSError, ValueError, TypeError, KeyError):
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                    "status": "blocked", "reason": "v7_readonly_inventory_unavailable",
                })
                return
            self._json(HTTPStatus.OK, status)
        else:
            super().do_GET()


class CommandCenterV7Server(CommandCenterV6Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
        vision_enabled: bool = False,
    ):
        super().__init__(
            project_root, port, chat_enabled=chat_enabled, vision_enabled=vision_enabled,
        )
        self.RequestHandlerClass = CommandCenterV7Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="HEX-CORTEX V7 real external DeepSeek Harness inventory only",
    )
    p.add_argument("--project-root", type=Path, default=Path("."))
    p.add_argument("--port", type=int, default=8777)
    p.add_argument("--enable-cpu-chat", action="store_true")
    p.add_argument("--enable-cpu-vision", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1",
            "port": args.port, "chat_enabled": args.enable_cpu_chat,
            "vision_enabled": args.enable_cpu_vision,
            "dsh_connection": "read_only_inventory_no_runtime",
            "files_written": False, "model_called": False,
            "external_harness_launched": False, "external_network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV7Server(
            args.project_root, args.port, chat_enabled=args.enable_cpu_chat,
            vision_enabled=args.enable_cpu_vision,
        ) as server:
            print(
                f"HEX-CORTEX V7: http://127.0.0.1:{server.server_port}/ "
                "DSH adapter: inventory only, no agent launched.",
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
