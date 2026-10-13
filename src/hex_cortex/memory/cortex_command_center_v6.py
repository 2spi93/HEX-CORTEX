"""V6 Command Center: operator-authorized real V36 MobileSAM on local image.

One strictly localhost, same-origin, deliberately clicked photo upload; no
automatic webcam transmission, file persistence, CUDA, remote device actions
or Cloud network. Uses the existing V36 CPU predictor and checkpoint pin.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import json
from http import HTTPStatus
from pathlib import Path
from urllib.parse import urlsplit

from hex_cortex.memory.cortex_command_center_segmentation_v6 import (
    TRUSTED_CHECKPOINT_SHA256,
    segment_browser_photo_cpu,
)
from hex_cortex.memory.cortex_command_center_v5 import (
    CommandCenterV5Handler,
    CommandCenterV5Server,
)
from hex_cortex.memory.cortex_command_center_view_v6 import CSS, HTML, JS


class CommandCenterV6Handler(CommandCenterV5Handler):
    server_version = "HEX-CORTEX-CommandCenter/6.0"

    def do_GET(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        p = urlsplit(self.path)
        if p.path == "/" and not p.query:
            self._reply(HTTPStatus.OK, HTML.encode(), "text/html; charset=utf-8")
        elif p.path == "/assets/command-center.js" and not p.query:
            self._reply(HTTPStatus.OK, JS.encode(), "text/javascript; charset=utf-8")
        elif p.path == "/assets/command-center.css" and not p.query:
            self._reply(HTTPStatus.OK, CSS.encode(), "text/css; charset=utf-8")
        elif p.path == "/api/vision/cpu/availability" and not p.query:
            self._json(HTTPStatus.OK, {
                "schema": "hex.local_cpu_vision.v6",
                "enabled_at_server_launch": self.server.vision_enabled,
                "checkpoint_relative_path": "weights/mobile_sam.pt",
                "expected_checkpoint_sha256": TRUSTED_CHECKPOINT_SHA256,
                "weight_file_hash_verified_by_this_get": False,
                "model_loaded": False, "gpu_used": False,
                "image_upload_or_inference_performed": False,
                "operator_approval_required_per_request": True,
            })
        else:
            super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        p = urlsplit(self.path)
        if p.path != "/api/vision/cpu/segment" or p.query:
            return super().do_POST()
        if not self._allowed_request():
            return
        if not self.server.vision_enabled:
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "cpu_vision_disabled_at_launch",
            })
            return
        if (
            self.headers.get("Origin") != f"http://{self.headers.get('Host')}"
            or self.headers.get("X-HEX-Vision-Approval") != "upload-one-image-and-load-pinned-cpu-model"
            or self.headers.get("Content-Type") != "application/json"
            or self.headers.get("Transfer-Encoding") is not None
        ):
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "explicit_same_origin_photo_upload_required",
            })
            return
        raw_size = self.headers.get("Content-Length", "")
        if not raw_size.isascii() or not raw_size.isdecimal():
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "invalid_content_length",
            })
            return
        length = int(raw_size)
        if not 0 < length <= 11_000_000:
            self._json(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {
                "status": "blocked", "reason": "image_payload_too_large",
            })
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if (
                not isinstance(payload, dict)
                or set(payload) != {"image_b64", "bbox", "object_id"}
                or not isinstance(payload["image_b64"], str)
                or not 0 < len(payload["image_b64"]) <= 10_700_000
                or not isinstance(payload["object_id"], str)
                or not isinstance(payload["bbox"], list)
                or len(payload["bbox"]) != 4
            ):
                raise ValueError("v6_photo_schema_denied")
            raw = base64.b64decode(payload["image_b64"], validate=True)
            box = payload["bbox"]
            if any(type(value) is not int for value in box):
                raise ValueError("v6_bbox_denied")
        except (ValueError, UnicodeError, KeyError, TypeError, binascii.Error):
            self._json(HTTPStatus.BAD_REQUEST, {
                "status": "blocked", "reason": "photo_or_bbox_invalid",
            })
            return
        # Shares the CPU inference gate with Ollama; prevents concurrent large
        # CPU model loads from saturating this workstation.
        if not self.server.chat_gate.acquire(blocking=False):
            self._json(HTTPStatus.TOO_MANY_REQUESTS, {
                "status": "busy", "reason": "cpu_inference_already_running",
            })
            return
        try:
            result = segment_browser_photo_cpu(
                root=self.server.project_root, image_bytes=raw,
                box=tuple(box), object_id=payload["object_id"],
                approved_operator_upload=True, approved_model_load=True,
            )
        except (OSError, ValueError, RuntimeError, PermissionError, ImportError):
            self._json(HTTPStatus.UNPROCESSABLE_ENTITY, {
                "status": "blocked",
                "reason": "cpu_segmentation_unavailable_or_input_denied",
                "model_result_ready": False, "files_written": False,
            })
        else:
            self._json(HTTPStatus.OK, result)
        finally:
            self.server.chat_gate.release()


class CommandCenterV6Server(CommandCenterV5Server):
    def __init__(
        self, project_root: Path, port: int = 8777, *, chat_enabled: bool = False,
        vision_enabled: bool = False,
    ):
        self.vision_enabled = vision_enabled
        super().__init__(project_root, port, chat_enabled=chat_enabled)
        self.RequestHandlerClass = CommandCenterV6Handler


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="HEX-CORTEX V6 real CPU opt-in vision")
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
            "files_written": False, "model_called": False, "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterV6Server(
            a.project_root, a.port, chat_enabled=a.enable_cpu_chat,
            vision_enabled=a.enable_cpu_vision,
        ) as server:
            print(
                f"HEX-CORTEX V6: http://127.0.0.1:{server.server_port}/ "
                f"CPU model vision: {'OPT-IN' if server.vision_enabled else 'disabled'}",
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
