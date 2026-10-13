"""End-to-end localhost Command Center tests: security and real local telemetry."""
from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_command_center_v1 import (
    CommandCenterServer,
    _explicit_repo_probe,
    main,
    snapshot,
)
from hex_cortex.spine.canonical_spine import CanonicalSpine
from hex_cortex.spine.jsonl_store import CanonicalSpineJsonlStore


def _json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _inspection(root: Path):
    base = root / "receipts/v40_mask_inspection/run-20261013T181258-825272Z"
    fake_png = b"\x89PNG\r\n\x1a\n" + b"local fixture bytes"
    image = base / "scene03_jump/person_airborne.preview.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(fake_png)
    _json(base / "inspection.json", {
        "schema": "hex.mask_inspection.v40",
        "status": "verified_mask_replay_exported",
        "new_output_dir": "receipts/v40_mask_inspection/run-20261013T181258-825272Z",
        "scene_count": 1, "mask_count": 1,
        "records": [{
            "scene_id": "scene03_jump",
            "objects": [{"object_id": "person_airborne"}],
        }],
    })
    return fake_png


def _spine(root: Path):
    spine = CanonicalSpine()
    spine.append(event_type="vision.object_mask_predicted.v42",
                 task_id="vision:scene03_jump", source="test_fixture",
                 payload={"kind": "prediction_only"})
    target = root / "receipts/v42_canonical_spine/visual_predictions.jsonl"
    target.parent.mkdir(parents=True, exist_ok=True)
    CanonicalSpineJsonlStore(target).save(spine)
    return target


def test_empty_checkout_is_accurate_and_read_only(tmp_path):
    before = list(tmp_path.iterdir())
    result = snapshot(tmp_path)
    assert result["mode"] == "local_cpu_safe_readonly"
    assert result["writes_enabled"] is False
    assert result["features"]["chat"] == "not_connected"
    assert result["vision"]["status"] == "not_available"
    assert result["spine"]["status"] == "not_recorded"
    assert result["harness"]["model_calls_budget"] == 0
    assert result["harness"]["tools"] == ["repo_manifest"]
    assert list(tmp_path.iterdir()) == before


def test_real_canonical_spine_and_preview_inspection(tmp_path):
    blob = _inspection(tmp_path)
    _spine(tmp_path)
    result = snapshot(tmp_path)
    assert result["vision"]["mask_count"] == 1
    assert result["vision"]["scenes"][0]["scene_id"] == "scene03_jump"
    assert result["vision"]["scenes"][0]["objects"][0]["preview_url"]
    assert result["spine"]["status"] == "verified_local_spine"
    assert result["spine"]["integrity"] is True
    assert result["spine"]["visual_predictions"] == 1
    assert blob.startswith(b"\x89PNG")


def test_corrupted_spine_never_yields_false_ok(tmp_path):
    file = _spine(tmp_path)
    text = file.read_text(encoding="utf-8")
    file.write_text(text.replace("prediction_only", "false_statement"), encoding="utf-8")
    report = snapshot(tmp_path)
    assert report["spine"]["status"] == "error"
    assert report["spine"]["reason"] == "spine_evidence_invalid_or_unreadable"


def test_symlinked_receipt_folder_rejected(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "_external")
    outside.mkdir()
    (tmp_path / "receipts").mkdir()
    try:
        (tmp_path / "receipts/v40_mask_inspection").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("insufficient permission for test symlink")
    assert snapshot(tmp_path)["vision"]["status"] == "error"


def test_read_only_harness_probe_exercises_existing_receipts(tmp_path):
    (tmp_path / "README.md").write_text("Test", encoding="utf-8")
    result = _explicit_repo_probe(tmp_path)
    assert result["status"] == "complete"
    assert result["repository_manifest_names"] == ["README.md"]
    assert len(result["receipt_sha256"]) == 64
    assert result["model_called"] is False
    assert result["spine_persisted"] is False
    assert sorted(p.name for p in tmp_path.iterdir()) == ["README.md"]


def test_cli_dry_run_refuses_any_socket_or_files(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--port", "8777", "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["files_written"] is False
    assert data["network_used"] is False
    assert main(["--port", "1", "--dry-run"]) == 2
    assert not list(tmp_path.iterdir())


def _http(server, method, route, *, host=None, origin=None, probe=False, body=None,
          fetch_site=None, fetch_mode=None, fetch_dest=None):
    port = server.server_port
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if origin is not None:
        headers["Origin"] = origin
    if fetch_site is not None:
        headers["Sec-Fetch-Site"] = fetch_site
    if fetch_mode is not None:
        headers["Sec-Fetch-Mode"] = fetch_mode
    if fetch_dest is not None:
        headers["Sec-Fetch-Dest"] = fetch_dest
    if probe:
        headers["X-HEX-Read-Probe"] = "explicit"
        headers["Content-Length"] = "0"
    conn.request(method, route, body=body, headers=headers)
    response = conn.getresponse()
    status, content_type = response.status, response.getheader("Content-Type")
    data = response.read()
    security = response.getheader("Content-Security-Policy")
    conn.close()
    return status, content_type, data, security


def test_actual_http_routes_and_permissions(tmp_path):
    before = _inspection(tmp_path)
    with CommandCenterServer(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, mime, page, policy = _http(server, "GET", "/")
            assert status == 200 and "text/html" in mime
            assert b"HEX-CORTEX" in page
            assert "script-src 'self'" in policy
            for path, expected in [
                ("/assets/command-center.css", "text/css"),
                ("/assets/command-center.js", "text/javascript"),
            ]:
                status, mime, content, _ = _http(server, "GET", path)
                assert status == 200 and expected in mime and content
            status, mime, raw, _ = _http(server, "GET", "/api/snapshot")
            assert status == 200 and "application/json" in mime
            assert json.loads(raw)["vision"]["mask_count"] == 1
            status, mime, image, _ = _http(
                server, "GET",
                "/api/vision/preview?scene=scene03_jump&object=person_airborne",
            )
            assert status == 200 and image == before and mime == "image/png"

            for route in [
                "/api/vision/preview?scene=../../etc&object=person_airborne",
                "/api/vision/preview?scene=scene03_jump&object=../../passwd",
                "/api/vision/preview?scene=scene03_jump&object=none",
            ]:
                assert _http(server, "GET", route)[0] in {400, 404}

            status, _, _, _ = _http(server, "POST", "/api/harness/probe")
            assert status == 403  # explicit operator click required
            status, _, _, _ = _http(server, "POST", "/api/harness/probe",
                                   origin=f"http://127.0.0.1:{server.server_port}", probe=True)
            assert status == 200

            status, _, _, _ = _http(server, "POST", "/v1/tasks/enqueue",
                                   origin=f"http://127.0.0.1:{server.server_port}", probe=True)
            assert status == 405  # no existing mutating API routes inherited
            status, _, _, _ = _http(server, "GET", "/api/snapshot", host="evil.example")
            assert status == 403
            status, _, _, _ = _http(server, "GET", "/api/snapshot", origin="https://evil.example")
            assert status == 403
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_no_post_based_path_to_tools_or_model(tmp_path):
    with CommandCenterServer(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path in ("/api/chat", "/api/model/load", "/api/tools/exec", "/v1/tasks/enqueue"):
                status, _, data, _ = _http(server, "POST", path)
                assert status == 405
                assert b"mutating_endpoint_disabled" in data
            assert not list(tmp_path.iterdir())
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_cross_site_link_can_open_dashboard_but_cannot_access_api_or_probe(tmp_path):
    """Clicking from ChatGPT is a cross-site navigation, not API authorization."""
    with CommandCenterServer(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            browser_entry = {
                "fetch_site": "cross-site",
                "fetch_mode": "navigate",
                "fetch_dest": "document",
            }
            status, mime, body, _ = _http(server, "GET", "/", **browser_entry)
            assert status == 200 and "text/html" in mime
            assert b"Command Center" in body

            # Even an external navigation cannot reach a JSON route.
            for route in ("/api/snapshot", "/health", "/assets/command-center.js"):
                status, _, data, _ = _http(server, "GET", route, **browser_entry)
                assert status == 403
                assert json.loads(data)["reason"] == "cross_site_request_denied"

            # Direct API reads from another site and CSRF POST are denied.
            status, _, data, _ = _http(
                server, "GET", "/api/snapshot",
                fetch_site="cross-site", fetch_mode="cors",
            )
            assert status == 403
            assert json.loads(data)["reason"] == "cross_site_request_denied"
            status, _, data, _ = _http(
                server, "POST", "/api/harness/probe",
                fetch_site="cross-site", fetch_mode="navigate",
                fetch_dest="document",
                origin=f"http://127.0.0.1:{server.server_port}", probe=True,
            )
            assert status == 403
            assert json.loads(data)["reason"] == "cross_site_request_denied"

            # An explicitly foreign Origin always remains forbidden.
            status, _, data, _ = _http(
                server, "GET", "/", **browser_entry, origin="https://external.example",
            )
            assert status == 403
            assert json.loads(data)["reason"] == "origin_not_allowed"

            # Assets/data fetched from inside our page are same-origin.
            for route in ("/api/snapshot", "/assets/command-center.js"):
                assert _http(
                    server, "GET", route, fetch_site="same-origin",
                    fetch_mode="cors",
                )[0] == 200
        finally:
            server.shutdown()
            thread.join(timeout=5)
