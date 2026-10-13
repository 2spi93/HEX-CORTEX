"""V7 DeepSeek compatibility gateway, fail-closed and no executable agents."""
from __future__ import annotations

import http.client
import json
import re
import shutil
import subprocess
import threading

import pytest

from hex_cortex.memory import cortex_deepseek_harness_bridge_v7 as bridge
from hex_cortex.memory.cortex_command_center_v7 import (
    CommandCenterV7Server, main,
)
from hex_cortex.memory.cortex_command_center_view_v7 import HTML, JS


def test_external_harness_preflight_distinguishes_sdk_presence_from_execution(tmp_path):
    manifest = bridge.deepseek_harness_bridge_status(tmp_path, sdk_version="0.1-test")
    assert manifest["schema"] == "hex.deepseek_harness_compatibility.v7"
    assert manifest["external_sdk_distribution_installed"] is True
    assert manifest["external_runtime_launched"] is False
    assert manifest["real_deepseek_integration_attested"] is False
    assert manifest["repository_files_exposed"] is False
    assert manifest["network_used"] is False
    assert manifest["files_written"] is False
    assert manifest["executed_tools"] == []
    assert len(manifest["receipt_sha256"]) == 64
    assert "deepseek-ai/deepseek-harness" in manifest["upstream_repo"]
    assert not list(tmp_path.iterdir())


def test_absent_sdk_and_forbidden_live_tools_are_told_truthfully(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "_sdk_version", lambda: None)
    manifest = bridge.deepseek_harness_bridge_status(tmp_path)
    assert manifest["external_sdk_distribution_installed"] is False
    names = {x["capability"]: x for x in manifest["capabilities"]}
    assert names["coding_and_tests"]["candidate"] is True
    assert names["coding_and_tests"]["connected"] is False
    assert names["skills_plugins_mcp"]["connected"] is False
    assert names["remote_robot_drone_actuation"]["connected"] is False
    assert names["canonical_evidence"]["connected"] is False
    assert manifest["requires_before_execution"]
    assert manifest["hex_vision_evidence_status"] == "not_available"


def test_preflight_does_not_import_third_party_sdk_or_execute_anything(tmp_path, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Third-party agent must never be invoked")
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(bridge, "_sdk_version", lambda: "0.1-test")
    assert bridge.deepseek_harness_bridge_status(tmp_path)["model_called"] is False
    assert not list(tmp_path.iterdir())


def test_invalid_version_and_root_denied(tmp_path):
    with pytest.raises(ValueError, match="sdk_version_invalid"):
        bridge.deepseek_harness_bridge_status(tmp_path, sdk_version="X" * 81)
    with pytest.raises(FileNotFoundError):
        bridge.deepseek_harness_bridge_status(tmp_path / "not-found", sdk_version="1")


def _request(server, path, *, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
    headers = {"Host": f"127.0.0.1:{server.server_port}"}
    if origin is not None:
        headers["Origin"] = origin
    conn.request("GET", path, headers=headers)
    res = conn.getresponse()
    status, body = res.status, res.read()
    conn.close()
    return status, body


def test_http_readonly_inventory_existing_cpu_vision_and_chat_preserved(tmp_path):
    with CommandCenterV7Server(
        tmp_path, port=0, chat_enabled=True, vision_enabled=True,
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            code, data = _request(server, "/api/integrations/deepseek-harness")
            assert code == 200
            parsed = json.loads(data)
            assert parsed["external_runtime_launched"] is False
            assert parsed["real_deepseek_integration_attested"] is False
            assert _request(server, "/api/vision/cpu/availability")[0] == 200
            assert _request(server, "/api/project/brief")[0] == 200
            assert _request(server, "/api/integrations/deepseek-harness",
                            origin="https://evil.invalid")[0] == 403
            assert _request(server, "/api/integrations/deepseek-harness?exec=1")[0] == 404
            assert _request(server, "/api/integrations/deepseek-harness/run")[0] == 404
            assert not list(tmp_path.iterdir())
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_v7_html_control_inventory_and_syntax(tmp_path):
    assert "HEX-CORTEX V7" in HTML
    assert '<section id="dsh"' in HTML
    assert 'href="#dsh"' in HTML
    assert "/api/integrations/deepseek-harness" in JS
    assert "DeepSeek Harness" in HTML
    assert "Aucun runtime DeepSeek lancé" in HTML
    assert "segment" in JS  # V6 photo segmentation workflow is retained
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    lookups = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", JS))
    assert lookups <= ids, f"Missing V7 controls: {lookups - ids}"
    node = shutil.which("node")
    if not node:
        pytest.skip("Node is unavailable")
    file = tmp_path / "command-center-v7.js"
    file.write_text(JS, encoding="utf-8")
    check = subprocess.run(
        [node, "--check", str(file)], capture_output=True,
        text=True, timeout=10, check=False,
    )
    assert check.returncode == 0, check.stderr


def test_v7_dry_run_is_not_dsh_invocation(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["external_harness_launched"] is False
    assert result["model_called"] is False
    assert result["files_written"] is False
    assert not list(tmp_path.iterdir())
