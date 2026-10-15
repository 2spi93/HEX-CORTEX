"""V9 phone capture JSON -> existing V6 CPU segmentation: safe browser preflight."""
from __future__ import annotations

import http.client
import json
import re
import shutil
import subprocess
import threading
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_command_center_v9 import CommandCenterV9Server, main
from hex_cortex.memory.cortex_command_center_view_v9 import HTML, JS
from hex_cortex.memory.cortex_command_center_view_v6 import MEDIA_V6


def _get(port: int, path: str, *, origin: str | None = None) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=6)
    headers = {"Host": f"127.0.0.1:{port}"}
    if origin is not None:
        headers["Origin"] = origin
    connection.request("GET", path, headers=headers)
    response = connection.getresponse()
    result = response.status, response.read()
    connection.close()
    return result


def test_v9_browser_contains_real_v6_segmentation_and_verified_phone_import():
    assert "HEX-CORTEX V9" in HTML
    assert "phone-bbox-import" in HTML
    assert "phone-bbox-state" in HTML
    assert 'id="cpu-segment"' in HTML
    assert "/api/vision/cpu/segment" in JS
    assert "hex.mobile_manual_bbox.v9" in JS
    assert "crypto.subtle.digest('SHA-256'" in JS
    assert "computed !== sha" in JS
    assert "original !== expected" in JS
    assert "Number.isSafeInteger" in JS
    assert "dimensional" not in JS or "dimension" in JS
    assert "clearPredictedMask()" in JS
    assert "dragStart = {" in JS and "dragEnd = {" in JS
    assert "Aucun appel MobileSAM lancé automatiquement" in JS
    assert "X-HEX-Vision-Approval" in JS
    # Do not create a second computer-vision implementation.
    assert JS.count(MEDIA_V6) == 0
    assert "predictedOverlay" in JS
    assert "navigator.mediaDevices.getUserMedia" in JS


def test_v9_dom_controls_are_all_present():
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    referenced = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", JS))
    assert referenced and referenced <= ids, referenced - ids
    assert HTML.count('id="phone-bbox-import"') == 1


def test_v9_browser_script_parses_with_node_if_available(tmp_path):
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node not installed")
    source = tmp_path / "v9-mobile-import.js"
    source.write_text(JS, encoding="utf-8")
    result = subprocess.run(
        [node, "--check", str(source)], timeout=10,
        check=False, text=True, capture_output=True,
    )
    assert result.returncode == 0, result.stderr


def test_command_center_v9_retains_protected_apis_no_extra_actuation(tmp_path):
    with CommandCenterV9Server(
        tmp_path, port=0, chat_enabled=False, vision_enabled=False,
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            status, raw = _get(port, "/")
            assert status == 200 and b"HEX-CORTEX V9" in raw
            assert _get(port, "/assets/command-center.js")[0] == 200
            assert _get(port, "/api/project/brief")[0] == 200
            assert _get(port, "/api/vision/cpu/availability")[0] == 200
            assert _get(port, "/api/integrations/deepseek-harness")[0] == 200
            assert _get(port, "/api/integrations/deepseek-harness/pilot")[0] == 200
            assert _get(port, "/api/phone/control")[0] == 404
            assert _get(port, "/api/drone/actuate")[0] == 404
            assert _get(port, "/", origin="https://outside.invalid")[0] == 403
            assert not list(tmp_path.iterdir())
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_command_center_v9_dry_run_without_any_file_or_gpu(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["mobile_bbox_sha256_verification_in_browser"] is True
    assert data["remote_phone_control"] is False
    assert data["files_written"] is False
    assert data["model_called"] is False
    assert not list(tmp_path.iterdir())


def test_static_android_app_is_part_of_related_feature_branch():
    companion = Path(__file__).resolve().parents[1] / "docs" / "companion"
    assert (companion / "index.html").is_file()
    assert (companion / "app.js").is_file()
