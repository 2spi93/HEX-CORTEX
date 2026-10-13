"""Command Center V5: truthful, live project-aware Ollama; no extra tools."""
from __future__ import annotations

import argparse
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_chat_v2 import safe_cpu_chat
from hex_cortex.memory.cortex_command_center_facts_v5 import (
    project_system_facts,
    verified_project_brief,
)
from hex_cortex.memory.cortex_command_center_v4 import (
    CommandCenterV4Handler,
    CommandCenterV4Server,
)
from hex_cortex.memory.cortex_command_center_view_v5 import CSS, HTML, JS


class CommandCenterV5Handler(CommandCenterV4Handler):
    server_version = "HEX-CORTEX-CommandCenter/5.0"

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        parsed = urlsplit(self.path)
        if not parsed.query and parsed.path == "/":
            self._reply(HTTPStatus.OK, HTML.encode(), "text/html; charset=utf-8")
        elif not parsed.query and parsed.path == "/assets/command-center.js":
            self._reply(HTTPStatus.OK, JS.encode(), "text/javascript; charset=utf-8")
        elif not parsed.query and parsed.path == "/assets/command-center.css":
            self._reply(HTTPStatus.OK, CSS.encode(), "text/css; charset=utf-8")
        elif not parsed.query and parsed.path == "/api/project/brief":
            try:
                brief = verified_project_brief(
                    self.server.project_root, chat_enabled=self.server.chat_enabled,
                )
            except (OSError, ValueError, TypeError, KeyError):
                self._json(HTTPStatus.SERVICE_UNAVAILABLE, {
                    "status": "blocked", "reason": "project_evidence_unavailable",
                })
                return
            self._json(HTTPStatus.OK, brief)
        else:
            super().do_GET()

    def _invoke_cpu_chat(
        self, *, model: str, prompt: str, history: tuple[tuple[str, str], ...],
    ) -> dict:
        """V3 handles authentication and budgets; facts derived HERE, not from user."""
        brief = verified_project_brief(
            self.server.project_root, chat_enabled=self.server.chat_enabled,
        )
        result = safe_cpu_chat(
            root=self.server.project_root, model=model, prompt=prompt,
            history=history, trusted_project_facts=project_system_facts(brief),
        )
        if result["status"] == "completed":
            result["project_facts_sha256"] = brief["facts_sha256"]
            result["source_ids"] = ["snapshot", "capabilities", "devices"]
            result["source_type"] = "verified_local_server_metadata_not_external_citations"
            result["model_semantic_accuracy_proven"] = False
        return result


class CommandCenterV5Server(CommandCenterV4Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
    ):
        super().__init__(project_root, port, chat_enabled=chat_enabled)
        self.RequestHandlerClass = CommandCenterV5Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HEX-CORTEX V5: verified project-aware CPU chat")
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
            "status": "configuration_only", "host": "127.0.0.1",
            "port": args.port, "chat_enabled": args.enable_cpu_chat,
            "live_project_facts": True,
            "tools_enabled": False, "remote_device_control": False,
            "files_written": False, "model_called": False, "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV5Server(
            args.project_root, args.port, chat_enabled=args.enable_cpu_chat,
        ) as server:
            print(
                f"HEX-CORTEX V5: http://127.0.0.1:{server.server_port}/ "
                "Trusted project facts: enabled; tool calls: disabled.",
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
