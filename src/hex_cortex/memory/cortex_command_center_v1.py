"""HEX-CORTEX Command Center MVP: loopback-only, read-only observability.

Unlike the historical static readiness cockpit, this operator UI reads live
fixed-path data. No model is loaded, no network request is initiated, no
unapproved action/memory edit is exposed. A single explicit POST runs the
pre-existing allowlisted, in-memory read-only LocalHarness repo probe.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from hex_cortex.memory.cortex_command_center_assets_v1 import CSS, HTML, JS
from hex_cortex.memory.cortex_local_harness_v2 import (
    Task,
    build_readonly_harness,
)
from hex_cortex.memory.cortex_ui_cockpit_builder import (
    CORTEX_UI_COCKPIT_BUILD_FILENAME,
    summarize_cortex_ui_cockpit_builds,
)
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore

_V40 = Path("receipts/v40_mask_inspection")
_SPINE = Path("receipts/v42_canonical_spine/visual_predictions.jsonl")
_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
_RUN = re.compile(r"run-\d{8}T\d{6}-\d{6}Z\Z")
_MAX_INSPECTION = 512_000
_MAX_PREVIEW = 8_000_000
_MAX_SPINE = 4_000_000


def _safe_path(root: Path, rel: Path) -> Path:
    """Return existing or prospective fixed location, never following symlinks."""
    if rel.is_absolute() or ".." in rel.parts:
        raise ValueError("unsafe_path")
    target = root / rel
    if not target.resolve().is_relative_to(root):
        raise ValueError("unsafe_path")
    cursor = target
    while cursor != root:
        if cursor.is_symlink():
            raise ValueError("symlink_denied")
        cursor = cursor.parent
    return target


def _latest_inspection(root: Path) -> tuple[Path, dict] | None:
    base = _safe_path(root, _V40)
    if not base.exists():
        return None
    if not base.is_dir():
        raise ValueError("inspection_base_invalid")
    for item in sorted(base.iterdir(), reverse=True):
        if item.is_symlink() or not item.is_dir() or not _RUN.fullmatch(item.name):
            continue
        receipt = _safe_path(root, _V40 / item.name / "inspection.json")
        if not receipt.is_file() or not 0 < receipt.stat().st_size <= _MAX_INSPECTION:
            continue
        with receipt.open("r", encoding="utf-8") as source:
            data = json.load(source)
        if not isinstance(data, dict) or data.get("schema") != "hex.mask_inspection.v40":
            raise ValueError("inspection_schema_invalid")
        if data.get("new_output_dir") != (_V40 / item.name).as_posix():
            raise ValueError("inspection_directory_mismatch")
        if data.get("status") != "verified_mask_replay_exported":
            raise ValueError("inspection_status_invalid")
        return item, data
    return None


def _vision(root: Path) -> dict:
    found = _latest_inspection(root)
    if found is None:
        return {"status": "not_available", "scenes": [], "mask_count": 0,
                "quality_iou": None, "real_model_attested_by_ui": False}
    folder, receipt = found
    records = receipt.get("records")
    if not isinstance(records, list) or not 0 < len(records) <= 9:
        raise ValueError("inspection_records_invalid")
    scenes = []
    count = 0
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("inspection_record_invalid")
        scene = record.get("scene_id")
        if not isinstance(scene, str) or not _ID.fullmatch(scene) or scene in seen:
            raise ValueError("inspection_scene_invalid")
        seen.add(scene)
        objects = record.get("objects")
        if not isinstance(objects, list) or not 0 < len(objects) <= 24:
            raise ValueError("inspection_objects_invalid")
        titles = []
        ids = set()
        for obj in objects:
            if not isinstance(obj, dict):
                raise ValueError("inspection_object_invalid")
            name = obj.get("object_id")
            if not isinstance(name, str) or not _ID.fullmatch(name) or name in ids:
                raise ValueError("inspection_object_invalid")
            ids.add(name)
            # Do not blindly follow a receipt-provided path.
            expected = _V40 / folder.name / scene / f"{name}.preview.png"
            image = _safe_path(root, expected)
            available = image.is_file() and 0 < image.stat().st_size <= _MAX_PREVIEW
            titles.append({
                "object_id": name,
                "preview_url": f"/api/vision/preview?scene={scene}&object={name}"
                if available else None,
                "has_independent_iou": False,
            })
        count += len(titles)
        scenes.append({"scene_id": scene, "objects": titles})
    if count != receipt.get("mask_count") or len(scenes) != receipt.get("scene_count"):
        raise ValueError("inspection_count_mismatch")
    return {
        "status": "operator_receipt_loaded",
        "scenes": scenes,
        "mask_count": count,
        "quality_iou": None,
        "labels_source": "operator_selected",
        "real_model_attested_by_ui": False,
        "provenance": "reported_and_locally_inspectable_not_independently_ground_truthed",
    }


def _spine(root: Path) -> dict:
    path = _safe_path(root, _SPINE)
    if not path.exists():
        return {"status": "not_recorded", "events": 0, "integrity": None,
                "types": [], "visual_predictions": 0}
    if not path.is_file() or path.stat().st_size > _MAX_SPINE:
        raise ValueError("spine_file_denied")
    spine = CanonicalSpineJsonlStore(path).load()
    integrity = spine.verify_integrity()
    if not integrity.ok:
        raise ValueError("spine_integrity_failed")
    counter = Counter(event.event_type for event in spine.events)
    return {
        "status": "verified_local_spine",
        "events": len(spine.events),
        "integrity": True,
        "types": [
            {"type": name, "count": qty}
            for name, qty in counter.most_common(12)
        ],
        "visual_predictions": counter.get("vision.object_mask_predicted.v42", 0),
        "is_main_application_spine": False,
    }


def _cockpit(root: Path) -> dict:
    log = _safe_path(root, Path(".hex-cortex") / CORTEX_UI_COCKPIT_BUILD_FILENAME)
    if not log.exists():
        return {"status": "not_built", "build_count": 0, "latest_allowed": None}
    if not log.is_file() or log.stat().st_size > 1_000_000:
        raise ValueError("cockpit_history_invalid")
    data = summarize_cortex_ui_cockpit_builds(log)
    return {
        "status": "existing_cockpit_history",
        "build_count": data["total_build_count"],
        "latest_allowed": data["latest_build_allowed"],
        "latest_status": data["latest_build_status"],
    }


def snapshot(root: Path) -> dict:
    """Structured local diagnostic; section errors never claim successful health."""
    safe = root.resolve(strict=True)
    if not safe.is_dir():
        raise ValueError("project_root_invalid")
    harness = build_readonly_harness(safe, session_id="command-center")
    result = {
        "schema": "hex.command_center.v1",
        "mode": "local_cpu_safe_readonly",
        "features": {
            "chat": "not_connected",
            "voice": "not_connected",
            "vision": "receipt_metadata_only",
            "tools": "readonly_repo_probe_only",
            "automatic_agents": "disabled",
            "gpu_operations": "disabled",
        },
        "harness": {
            "mode": "existing_readonly_local_harness",
            "grants": sorted(str(c.value) for c in harness.grants),
            "tools": sorted(harness.tools),
            "model_calls_budget": harness.budget.max_model_calls,
            "tool_calls_budget": harness.budget.max_tool_calls,
        },
        "writes_enabled": False,
    }
    for key, loader in (("vision", _vision), ("spine", _spine), ("cockpit", _cockpit)):
        try:
            result[key] = loader(safe)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            result[key] = {"status": "error", "reason": f"{key}_evidence_invalid_or_unreadable"}
    return result


def _explicit_repo_probe(root: Path) -> dict:
    harness = build_readonly_harness(root, session_id="command-center-manual-probe")
    outcome = harness.execute(
        Task("command-center-manifest-probe", "repo_read",
             "Inspect allowlisted repository root metadata", "repo_manifest"),
        approved=True,
    )
    if not harness.verify_replay():
        raise ValueError("harness_replay_invalid")
    receipt = outcome["receipt"]
    return {
        "status": outcome["status"],
        "reason": outcome["reason"],
        "tool": receipt["tool_used"],
        "receipt_sha256": receipt["sha256"],
        "repository_manifest_names": outcome.get("tool_result", {}).get("manifest", []),
        "model_called": False,
        "files_written": False,
        "spine_persisted": False,
    }


class CommandCenterHandler(BaseHTTPRequestHandler):
    server_version = "HEX-CORTEX-CommandCenter/1.0"

    def log_message(self, format: str, *args: object) -> None:
        return  # avoid logging query contents

    def _allowed_request(self) -> bool:
        """Permit a cross-site *top-level page navigation*, never API access.

        Following a local link from ChatGPT can set Sec-Fetch-Site=cross-site.
        GET / is inert HTML and may be opened. Its subsequent /assets and
        /api requests must come from the local document's own origin.
        """
        host = self.headers.get("Host", "")
        port = self.server.server_address[1]
        allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
        if host not in allowed:
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "host_not_allowed",
            })
            return False
        origin = self.headers.get("Origin")
        if origin is not None and origin not in {f"http://{h}" for h in allowed}:
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "origin_not_allowed",
            })
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site":
            target = urlsplit(self.path)
            is_safe_entry = (
                self.command == "GET"
                and target.path == "/"
                and not target.query
                and self.headers.get("Sec-Fetch-Mode") == "navigate"
                and self.headers.get("Sec-Fetch-Dest") == "document"
            )
            if not is_safe_entry:
                self._json(HTTPStatus.FORBIDDEN, {
                    "status": "blocked", "reason": "cross_site_request_denied",
                })
                return False
        return True

    def _reply(self, status: HTTPStatus, body: bytes, kind: str = "application/json") -> None:
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Permissions-Policy", "microphone=(), camera=(), geolocation=()")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self'; connect-src 'self'; base-uri 'none'; "
            "form-action 'none'; frame-ancestors 'none'",
        )
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, result: dict) -> None:
        self._reply(status, json.dumps(result, sort_keys=True, ensure_ascii=False).encode())

    def do_GET(self) -> None:  # noqa: N802 - HTTP handler contract
        if not self._allowed_request():
            return
        path = urlsplit(self.path)
        root = self.server.project_root
        if path.path == "/" and not path.query:
            self._reply(HTTPStatus.OK, HTML.encode("utf-8"), "text/html; charset=utf-8")
        elif path.path == "/assets/command-center.css" and not path.query:
            self._reply(HTTPStatus.OK, CSS.encode("utf-8"), "text/css; charset=utf-8")
        elif path.path == "/assets/command-center.js" and not path.query:
            self._reply(HTTPStatus.OK, JS.encode("utf-8"), "text/javascript; charset=utf-8")
        elif path.path == "/api/snapshot" and not path.query:
            self._json(HTTPStatus.OK, snapshot(root))
        elif path.path == "/health" and not path.query:
            self._json(HTTPStatus.OK, {
                "status": "ok", "service": "hex-cortex-command-center",
                "loopback_only": True, "writes_enabled": False,
            })
        elif path.path == "/api/vision/preview":
            self._preview(root, path.query)
        else:
            self._json(HTTPStatus.NOT_FOUND, {"status": "blocked", "reason": "route_unknown"})

    def _preview(self, root: Path, query: str) -> None:
        args = parse_qs(query, keep_blank_values=True, strict_parsing=False)
        if set(args) != {"scene", "object"} or any(len(vals) != 1 for vals in args.values()):
            self._json(HTTPStatus.BAD_REQUEST, {"status": "blocked"})
            return
        scene, obj = args["scene"][0], args["object"][0]
        if not _ID.fullmatch(scene) or not _ID.fullmatch(obj):
            self._json(HTTPStatus.BAD_REQUEST, {"status": "blocked"})
            return
        try:
            info = _vision(root)
            available = next(
                (o for s in info["scenes"] if s["scene_id"] == scene
                 for o in s["objects"] if o["object_id"] == obj),
                None,
            )
            if available is None or not available["preview_url"]:
                raise ValueError("no_preview")
            inspection = _latest_inspection(root)
            if inspection is None:
                raise ValueError("missing_run")
            file = _safe_path(root, _V40 / inspection[0].name / scene / f"{obj}.preview.png")
            if not file.is_file() or not 0 < file.stat().st_size <= _MAX_PREVIEW:
                raise ValueError("invalid_image")
            data = file.read_bytes()
            if not data.startswith(b"\x89PNG\r\n\x1a\n"):
                raise ValueError("not_png")
        except (OSError, ValueError, KeyError, TypeError):
            self._json(HTTPStatus.NOT_FOUND, {"status": "blocked", "reason": "preview_unavailable"})
            return
        self._reply(HTTPStatus.OK, data, "image/png")

    def do_POST(self) -> None:  # noqa: N802
        if not self._allowed_request():
            return
        if urlsplit(self.path).path != "/api/harness/probe" or urlsplit(self.path).query:
            self._json(HTTPStatus.METHOD_NOT_ALLOWED, {
                "status": "blocked", "reason": "mutating_endpoint_disabled",
            })
            return
        expected_origin = f"http://{self.headers.get('Host')}"
        if (self.headers.get("Origin") != expected_origin
                or self.headers.get("X-HEX-Read-Probe") != "explicit"
                or self.headers.get("Content-Length") != "0"):
            self._json(HTTPStatus.FORBIDDEN, {
                "status": "blocked", "reason": "explicit_same_origin_probe_required",
            })
            return
        try:
            report = _explicit_repo_probe(self.server.project_root)
        except (OSError, ValueError, KeyError, TypeError):
            self._json(HTTPStatus.INTERNAL_SERVER_ERROR, {
                "status": "blocked", "reason": "readonly_probe_failed",
            })
            return
        self._json(HTTPStatus.OK, report)


class CommandCenterServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, project_root: Path, port: int = 8777):
        root = Path(project_root).resolve(strict=True)
        if not root.is_dir():
            raise ValueError("project_root_invalid")
        self.project_root = root
        super().__init__(("127.0.0.1", port), CommandCenterHandler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local read-only HEX-CORTEX Command Center")
    parser.add_argument("--project-root", type=Path, default=Path("."))
    parser.add_argument("--port", type=int, default=8777)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if not 1024 <= args.port <= 65535:
        print(json.dumps({"status": "blocked", "reason": "port_out_of_range"}))
        return 2
    if args.dry_run:
        print(json.dumps({
            "status": "configuration_only", "host": "127.0.0.1",
            "port": args.port, "model_called": False,
            "files_written": False, "network_used": False,
        }, sort_keys=True))
        return 0
    try:
        with CommandCenterServer(args.project_root, args.port) as server:
            print(f"HEX-CORTEX Command Center: http://127.0.0.1:{server.server_port}/", flush=True)
            server.serve_forever()
    except (OSError, ValueError):
        print(json.dumps({"status": "blocked", "reason": "cannot_bind_loopback_or_invalid_root"}))
        return 2
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
