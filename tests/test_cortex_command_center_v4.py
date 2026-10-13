"""Multimodal V4 integration: deny live actuation, verify local interfaces."""
from __future__ import annotations

import http.client
import json
import shutil
import subprocess
import threading

import pytest

from hex_cortex.memory.cortex_command_center_v4 import (
    CommandCenterV4Server,
    code_inventory,
    device_capabilities,
    main,
    read_allowlisted_source,
)
from hex_cortex.memory.cortex_command_center_view_v4 import (
    CSS, HTML, JS,
)


def _request(server, method, path, *, origin=None, extra=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=6)
    headers = {"Host": f"127.0.0.1:{server.server_port}"}
    if origin is not None:
        headers["Origin"] = origin
    headers.update(extra or {})
    conn.request(method, path, headers=headers)
    res = conn.getresponse()
    status, data = res.status, res.read()
    metadata = dict(res.getheaders())
    conn.close()
    return status, data, metadata


def test_v4_has_actual_photo_voice_geometry_code_device_ui():
    for name in [
        "photo-file", "photo-canvas", "camera-start", "camera-stop",
        "camera-snap", "bbox-export", "crop-export", "photo-export",
        "voice-start", "voice-stop", "voice-speak", "voice-to-chat",
        "scene-canvas", "angle-x", "angle-y", "code-files",
        "code-source", "sim-target", "sim-arm", "sim-stop",
    ]:
        assert f'id="{name}"' in HTML, name
    assert ".main section[hidden]" in CSS
    assert "Image" not in CSS or "WebGL" not in JS
    assert "navigator.mediaDevices.getUserMedia" in JS
    assert "new Blob" in JS
    assert "bbox_xyxy" in JS
    assert "SpeechRecognition" in JS
    assert "speechSynthesis" in JS
    assert "getContext('2d')" in JS
    assert "getContext('webgl')" not in JS
    assert "window.HEX_TAB" in JS
    assert "/api/ollama/conversation" in JS
    assert "chatHistory" not in JS  # Fresh bounded context name.
    assert "location.hash.slice(1)||'overview'" in JS
    assert "default-src" not in HTML
    assert "https://" not in HTML


def test_v4_javascript_parses_with_node_when_available(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node unavailable for JS static compilation")
    source = tmp_path / "command-center-v4.js"
    source.write_text(JS, encoding="utf-8")
    completed = subprocess.run(
        [node, "--check", str(source)],
        capture_output=True, text=True, check=False,
        timeout=10,
    )
    assert completed.returncode == 0, completed.stderr


def test_code_files_are_allowlisted_and_no_untrusted_content_is_followed(tmp_path):
    assert code_inventory()["editing_enabled"] is False
    assert len(code_inventory()["entries"]) >= 4
    for name in ("../.env", "../../etc/passwd", ".git/config", "secrets", "blob/../x"):
        with pytest.raises(ValueError, match="allowlisted"):
            read_allowlisted_source(tmp_path, name)
    allowed = tmp_path / "src/hex_cortex/memory/cortex_local_harness_v2.py"
    allowed.parent.mkdir(parents=True)
    allowed.write_text("# LocalHarness source fixture\n", encoding="utf-8")
    result = read_allowlisted_source(tmp_path, "harness")
    assert result["contents"].replace("\r\n", "\n") == "# LocalHarness source fixture\n"
    assert result["read_only"] and result["execution_permitted"] is False
    assert allowed.read_text(encoding="utf-8") == "# LocalHarness source fixture\n"


def test_symlinked_source_never_exposes_external_file(tmp_path):
    allowed = tmp_path / "src/hex_cortex/memory/cortex_local_harness_v2.py"
    allowed.parent.mkdir(parents=True)
    outside = tmp_path.parent / (tmp_path.name + "_secret.txt")
    outside.write_text("NEVER EXPOSE", encoding="utf-8")
    try:
        allowed.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("symlink unavailable")
    with pytest.raises(ValueError):
        read_allowlisted_source(tmp_path, "harness")


def test_device_registry_does_not_pretend_physical_control():
    data = device_capabilities()
    assert data["real_robot_drone_commands_enabled"] is False
    assert data["phone_remote_control_enabled"] is False
    assert "browser_local_simulation" in data["execution_modes"]
    devices = {d["id"]: d for d in data["device_types"]}
    assert devices["drone"]["actions"] == []
    assert devices["robot"]["actions"] == []
    assert devices["phone"]["actions"] == []
    assert devices["camera"]["state"] == "browser_permission_required"
    assert "safety_interlocks" in data["future_live_control_requirements"]


def test_v4_http_serves_media_and_code_without_opening_actuation(tmp_path):
    src = tmp_path / "src/hex_cortex/memory/cortex_local_harness_v2.py"
    src.parent.mkdir(parents=True)
    src.write_text("VALID PUBLIC CODE", encoding="utf-8")
    with CommandCenterV4Server(tmp_path, port=0, chat_enabled=False) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            status, data, headers = _request(server, "GET", "/")
            assert status == 200 and b"HEX-CORTEX V4" in data
            assert "camera=(self)" in headers["Permissions-Policy"]
            assert "microphone=(self)" in headers["Permissions-Policy"]
            assert "geolocation=()" in headers["Permissions-Policy"]
            assert "script-src 'self'" in headers["Content-Security-Policy"]
            assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
            for url in ["/assets/command-center.js", "/assets/command-center.css"]:
                code, raw, _ = _request(server, "GET", url)
                assert code == 200 and raw
            code, data, _ = _request(server, "GET", "/api/code/inventory")
            assert code == 200 and json.loads(data)["readonly"] is True
            code, data, _ = _request(server, "GET", "/api/code/source?name=harness")
            assert code == 200 and json.loads(data)["contents"] == "VALID PUBLIC CODE"
            for url in [
                "/api/code/source?name=../../.env",
                "/api/code/source?name=harness&name=spine",
                "/api/code/source?name=",
            ]:
                assert _request(server, "GET", url)[0] in {400, 404}
            code, data, _ = _request(server, "GET", "/api/capabilities")
            assert code == 200
            declared = {x["id"]: x for x in json.loads(data)["features"]}
            assert declared["code"]["status"] == "connected_allowlisted_readonly"
            assert declared["scene3d"]["status"] == "connected_cpu_wireframe_only"
            assert declared["voice"]["status"] == "browser_speech_opt_in_may_use_cloud"
            assert declared["devices"]["status"] == "simulation_only_no_actuation"
            code, data, _ = _request(server, "GET", "/api/devices/capabilities")
            assert code == 200
            assert not json.loads(data)["real_robot_drone_commands_enabled"]
            for path in [
                "/api/devices/connect", "/api/devices/move", "/api/drone/takeoff",
                "/api/robot/actuate", "/api/phone/control", "/api/shell/exec",
            ]:
                code, data, _ = _request(server, "POST", path)
                assert code == 405
                assert b"mutating_endpoint_disabled" in data
            code, data, _ = _request(server, "GET", "/api/code/source?name=harness",
                                     origin="https://external.example")
            assert code == 403
            code, data, _ = _request(server, "GET", "/api/devices/capabilities",
                                     extra={"Host": "evil.example"})
            assert code == 403
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_v4_preserves_older_readonly_apis(tmp_path):
    with CommandCenterV4Server(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for path in ["/api/snapshot", "/api/capabilities"]:
                code, data, _ = _request(server, "GET", path)
                assert code == 200 and json.loads(data)
            code, data, _ = _request(server, "GET", "/api/ollama/models")
            assert code == 403
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_v4_dry_run_has_no_side_effects(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["remote_devices_enabled"] is False
    assert report["network_used"] is False
    assert report["files_written"] is False
    assert report["model_called"] is False
    assert list(tmp_path.iterdir()) == []
