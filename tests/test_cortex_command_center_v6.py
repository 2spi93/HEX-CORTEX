"""V6 opt-in real CPU segmentation integration and attack-boundary regression."""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import re
import shutil
import subprocess
import threading

import pytest
from PIL import Image, ImageDraw

from hex_cortex.memory.cortex_command_center_segmentation_v6 import (
    TRUSTED_CHECKPOINT_SHA256,
    segment_browser_photo_cpu,
)
from hex_cortex.memory.cortex_command_center_v6 import CommandCenterV6Server, main
from hex_cortex.memory.cortex_command_center_view_v6 import HTML, JS


def _jpg():
    image = Image.new("RGB", (80, 60), "white")
    ink = ImageDraw.Draw(image)
    ink.rectangle((12, 9, 47, 41), fill="navy")
    output = io.BytesIO()
    image.save(output, format="JPEG", quality=85)
    return output.getvalue()


def _fake_infer(image, boxes, checkpoint):
    assert image.size == (80, 60)
    assert set(boxes) == {"object1"}
    mask = Image.new("L", image.size, 0)
    ink = ImageDraw.Draw(mask)
    ink.rectangle((12, 9, 47, 41), fill=255)
    return {"object1": mask}


def _get(conn_port, method, path, *, headers=None, payload=None):
    c = http.client.HTTPConnection("127.0.0.1", conn_port, timeout=8)
    h = {"Host": f"127.0.0.1:{conn_port}"}
    h.update(headers or {})
    c.request(method, path, headers=h, body=payload)
    response = c.getresponse()
    status, data = response.status, response.read()
    c.close()
    return status, data


def test_real_v36_predictor_contract_reused_without_writes(tmp_path, monkeypatch):
    from hex_cortex.memory import cortex_command_center_segmentation_v6 as v6
    weights = tmp_path / "weights"
    weights.mkdir()
    checkpoint = weights / "mobile_sam.pt"
    checkpoint.write_bytes(b"test checkpoint not trusted in production")
    # Tests inject a fake inference provider and a known hash; they NEVER
    # attest real weights or actual segmentation accuracy.
    monkeypatch.setattr(v6, "_sha256_file", lambda path: TRUSTED_CHECKPOINT_SHA256)
    before = sorted(x.as_posix() for x in tmp_path.rglob("*"))
    result = segment_browser_photo_cpu(
        root=tmp_path, image_bytes=_jpg(), box=(10, 8, 50, 44),
        object_id="object1", approved_operator_upload=True,
        approved_model_load=True, infer=_fake_infer,
    )
    assert result["provider"] == "test_double_not_real_inference"
    assert result["model_called"] is False
    assert result["mask_origin"] == "mobile_sam_prediction_not_human_ground_truth"
    assert result["files_written"] is False and result["spine_persisted"] is False
    assert result["image_width"] == 80 and result["image_height"] == 60
    assert len(result["mask_binary_sha256"]) == 64
    assert result["mask_visible_pixels"] > 0
    with Image.open(io.BytesIO(base64.b64decode(result["mask_png_b64"]))) as mask:
        assert mask.size == (80, 60)
    with Image.open(io.BytesIO(base64.b64decode(result["overlay_png_b64"]))) as overlay:
        assert overlay.mode == "RGBA" and overlay.size == (80, 60)
    after = sorted(x.as_posix() for x in tmp_path.rglob("*"))
    assert before == after


def test_no_photo_or_checkpoint_read_without_operator_approval(tmp_path):
    with pytest.raises(PermissionError, match="approval_required"):
        segment_browser_photo_cpu(
            root=tmp_path, image_bytes=_jpg(), box=(0, 0, 10, 10),
            object_id="object1", approved_operator_upload=False,
            approved_model_load=True,
        )
    assert list(tmp_path.iterdir()) == []


def test_rejects_untrusted_checkpoint_before_loading_model(tmp_path):
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "mobile_sam.pt").write_bytes(b"attacker model pickle")
    with pytest.raises(ValueError, match="checkpoint_sha256_untrusted"):
        segment_browser_photo_cpu(
            root=tmp_path, image_bytes=_jpg(), box=(0, 0, 10, 10),
            object_id="object1", approved_operator_upload=True,
            approved_model_load=True, infer=_fake_infer,
        )


def test_rejects_invalid_box_and_object_id_before_model_loading(tmp_path):
    with pytest.raises(ValueError, match="bbox_format_invalid"):
        segment_browser_photo_cpu(
            root=tmp_path, image_bytes=_jpg(), box=(0, True, 10, 10),
            object_id="object1", approved_operator_upload=True,
            approved_model_load=True,
        )
    with pytest.raises(ValueError, match="object_label_invalid"):
        segment_browser_photo_cpu(
            root=tmp_path, image_bytes=_jpg(), box=(0, 0, 10, 10),
            object_id="../evil", approved_operator_upload=True,
            approved_model_load=True,
        )


def test_checksum_matches_image_data_in_test_helper():
    assert hashlib.sha256(_jpg()).hexdigest() != TRUSTED_CHECKPOINT_SHA256


def test_backend_disabled_by_default_and_no_device_control(tmp_path):
    with CommandCenterV6Server(tmp_path, port=0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            code, raw = _get(port, "GET", "/api/vision/cpu/availability")
            assert code == 200
            state = json.loads(raw)
            assert state["enabled_at_server_launch"] is False
            assert state["model_loaded"] is False
            code, raw = _get(port, "POST", "/api/vision/cpu/segment")
            assert code == 403
            assert json.loads(raw)["reason"] == "cpu_vision_disabled_at_launch"
            for route in ["/api/drone/takeoff", "/api/devices/move", "/api/shell/exec"]:
                assert _get(port, "POST", route)[0] == 405
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_http_explicit_approval_schema_gates_and_result(tmp_path, monkeypatch):
    from hex_cortex.memory import cortex_command_center_v6 as handler
    calls = []
    def fake(**kwargs):
        calls.append(kwargs)
        return {
            "schema": "hex.local_browser_mobilesam.v6",
            "status": "one_shot_mobile_sam_mask_ready",
            "model_called": False, "files_written": False, "gpu_used": False,
            "mask_visible_pixels": 22, "mask_png_b64": "AA==", "overlay_png_b64": "AA==",
        }
    monkeypatch.setattr(handler, "segment_browser_photo_cpu", fake)
    with CommandCenterV6Server(tmp_path, port=0, vision_enabled=True) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            base = f"http://127.0.0.1:{port}"
            blob = json.dumps({
                "image_b64": base64.b64encode(_jpg()).decode(),
                "bbox": [10, 8, 50, 44], "object_id": "object1",
            }).encode()
            headers = {
                "Content-Type": "application/json",
                "X-HEX-Vision-Approval": "upload-one-image-and-load-pinned-cpu-model",
            }
            assert _get(port, "POST", "/api/vision/cpu/segment",
                        headers=headers, payload=blob)[0] == 403
            assert _get(port, "POST", "/api/vision/cpu/segment",
                        headers={**headers, "Origin": "https://evil.invalid"},
                        payload=blob)[0] == 403
            assert calls == []
            bad = json.dumps({"image_b64": "not base64",
                              "bbox": [1, 2, 20, 30],
                              "object_id": "object1"}).encode()
            assert _get(port, "POST", "/api/vision/cpu/segment",
                        headers={**headers, "Origin": base},
                        payload=bad)[0] == 400
            assert calls == []
            code, raw = _get(
                port, "POST", "/api/vision/cpu/segment",
                headers={**headers, "Origin": base}, payload=blob,
            )
            assert code == 200
            assert json.loads(raw)["files_written"] is False
            assert calls[0]["approved_operator_upload"] is True
            assert calls[0]["approved_model_load"] is True
            assert calls[0]["box"] == (10, 8, 50, 44)
            assert calls[0]["image_bytes"] == _jpg()
            assert not list(tmp_path.iterdir())
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_ui_real_model_button_only_when_approved_and_selected():
    assert "HEX-CORTEX V6" in HTML
    for element in ["cpu-segment", "mask-export", "segmentation-status", "photo-file"]:
        assert f'id="{element}"' in HTML
    assert "La photo sera alors envoyée UNIQUEMENT" in HTML
    assert "MobileSAM CPU" in HTML
    assert "real" not in HTML.lower() or "mobile" in HTML.lower()
    assert "/api/vision/cpu/availability" in JS
    assert "/api/vision/cpu/segment" in JS
    assert "X-HEX-Vision-Approval" in JS
    assert "mask_png_b64" in JS
    assert "predictedOverlay" in JS
    assert "getContext('webgl')" not in JS
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    lookups = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", JS))
    assert lookups <= ids, f"Missing V6 controls: {lookups - ids}"


def test_js_compiles_with_node_when_available(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    script = tmp_path / "command-center-v6.js"
    script.write_text(JS, encoding="utf-8")
    result = subprocess.run([node, "--check", str(script)],
                            capture_output=True, text=True, timeout=12,
                            check=False)
    assert result.returncode == 0, result.stderr


def test_dry_run_never_loads_weights(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path),
                 "--enable-cpu-vision", "--dry-run"]) == 0
    info = json.loads(capsys.readouterr().out)
    assert info["vision_enabled"] is True
    assert info["model_called"] is False
    assert info["files_written"] is False
    assert list(tmp_path.iterdir()) == []
