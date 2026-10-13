"""V8 external DSH SDK outcome import + read-only UI safety tests."""
from __future__ import annotations

import hashlib
import http.client
import json
import re
import shutil
import subprocess
import threading

import pytest

from hex_cortex.memory.cortex_command_center_v8 import CommandCenterV8Server, main
from hex_cortex.memory.cortex_command_center_view_v8 import HTML, JS
from hex_cortex.memory.cortex_deepseek_sdk_receipt_v8 import (
    imported_sdk_pilot_summary,
)


def _valid_receipt():
    kinds = {
        "turn/start": 1, "turn/end": 1, "step/start": 1,
        "step/end": 1, "tool/call": 1, "tool/result": 1,
        "assistant/message": 2,
    }
    return {
        "schema": "hex.deepseek_sdk_disposable_pilot.v8",
        "status": "sdk_turn_finished_without_accuracy_attestation",
        "profile": "sdk-minimal",
        "external_sdk_runtime_launched": True,
        "model_called": True,
        "sdk_test_double_used": False,
        "auto_promoted_to_canonical_spine": False,
        "observed_tool_call_events": 1,
        "observed_tool_result_events": 1,
        "root_event_type_counts": kinds,
        "session_id_sha256": "a" * 64,
        "prompt_sha256": "b" * 64,
        "response_sha256": "c" * 64,
        "calc_file_sha256_after": "d" * 64,
        "model": "deepseek-v4-flash",
        "provider": "deepseek-official",
        "sdk_version_expected": "0.2.1",
    }


def _receipt_path(root):
    location = root / "receipts" / "v8_deepseek_sdk"
    location.mkdir(parents=True, exist_ok=True)
    return location / "operator_import.json"


def test_no_receipt_reports_no_external_runtime(tmp_path):
    data = imported_sdk_pilot_summary(tmp_path)
    assert data["status"] == "no_operator_imported_receipt"
    assert data["pilot_runtime_connected_to_chat"] is False
    assert data["tools_granted_to_chat"] == []
    assert list(tmp_path.iterdir()) == []


def test_operator_receipt_is_explicitly_untrusted(tmp_path):
    path = _receipt_path(tmp_path)
    data = _valid_receipt()
    path.write_text(json.dumps(data), encoding="utf-8")
    report = imported_sdk_pilot_summary(tmp_path)
    assert report["status"] == "operator_imported_vm_report_unverified"
    assert report["fixture_sdk_turn_reported"] is True
    assert report["independent_vm_isolation_attested"] is False
    assert report["pilot_runtime_connected_to_chat"] is False
    assert report["tools_granted_to_chat"] == []
    assert report["specific_tool_name_registry_connected"] is False
    assert report["observed_tool_call_events_reported"] == 1
    assert report["source_receipt_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_never_disclose_raw_model_response_or_custom_file_payload(tmp_path):
    p = _receipt_path(tmp_path)
    data = _valid_receipt()
    data["final_response"] = "PROPRIETARY_SECRET"
    data["tool_log"] = "RUN AN UNRESTRICTED COMMAND"
    p.write_text(json.dumps(data), encoding="utf-8")
    safe = json.dumps(imported_sdk_pilot_summary(tmp_path))
    assert "PROPRIETARY_SECRET" not in safe
    assert "UNRESTRICTED COMMAND" not in safe


@pytest.mark.parametrize("field,value", [
    ("profile", "sdk"),
    ("model_called", False),
    ("external_sdk_runtime_launched", False),
    ("sdk_test_double_used", True),
    ("observed_tool_call_events", -1),
    ("model", "../../secret"),
    ("session_id_sha256", "wrong"),
])
def test_invalid_or_untrusted_receipt_denied(tmp_path, field, value):
    p = _receipt_path(tmp_path)
    data = _valid_receipt()
    data[field] = value
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="v8_"):
        imported_sdk_pilot_summary(tmp_path)


def test_event_accounting_mismatch_denied(tmp_path):
    p = _receipt_path(tmp_path)
    data = _valid_receipt()
    data["root_event_type_counts"]["tool/call"] = 0
    p.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="inconsistent_event_counts"):
        imported_sdk_pilot_summary(tmp_path)


def test_symlink_receipt_denied(tmp_path):
    directory = tmp_path / "receipts" / "v8_deepseek_sdk"
    directory.mkdir(parents=True)
    outside = tmp_path / "other.json"
    outside.write_text(json.dumps(_valid_receipt()), encoding="utf-8")
    path = directory / "operator_import.json"
    try:
        path.symlink_to(outside)
    except OSError:
        pytest.skip("Creating Windows symlinks requires extra privileges")
    with pytest.raises(ValueError, match="symlinks_denied"):
        imported_sdk_pilot_summary(tmp_path)


def _get(port, path, *, origin=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=8)
    headers = {"Host": f"127.0.0.1:{port}"}
    if origin:
        headers["Origin"] = origin
    conn.request("GET", path, headers=headers)
    response = conn.getresponse()
    status, payload = response.status, response.read()
    conn.close()
    return status, payload


def test_v8_http_preserves_v7_and_v6_without_execution(tmp_path):
    with CommandCenterV8Server(
        tmp_path, port=0, chat_enabled=False, vision_enabled=False,
    ) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = server.server_port
            code, data = _get(port, "/api/integrations/deepseek-harness/pilot")
            assert code == 200
            assert json.loads(data)["status"] == "no_operator_imported_receipt"
            assert _get(port, "/api/integrations/deepseek-harness")[0] == 200
            assert _get(port, "/api/project/brief")[0] == 200
            assert _get(port, "/api/vision/cpu/availability")[0] == 200
            assert _get(port, "/api/integrations/deepseek-harness/pilot?run=1")[0] == 404
            assert _get(port, "/api/integrations/deepseek-harness/pilot",
                        origin="https://evil.invalid")[0] == 403
            assert list(tmp_path.iterdir()) == []
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_v8_ui_has_distinct_real_vm_report_and_js_compiles(tmp_path):
    assert "HEX-CORTEX V8" in HTML
    assert "dsh-pilot-refresh" in HTML
    assert "pilot" in JS
    assert "/api/integrations/deepseek-harness/pilot" in JS
    assert "non attesté indépendamment" in JS
    assert "Aucun shell DeepSeek ne s'exécute ici" in HTML
    ids = set(re.findall(r'id="([^"]+)"', HTML))
    lookups = set(re.findall(r"\$\('([A-Za-z0-9_-]+)'\)", JS))
    assert lookups <= ids, f"Missing DOM IDs: {lookups - ids}"
    node = shutil.which("node")
    if not node:
        pytest.skip("Node not installed")
    f = tmp_path / "command-center-v8.js"
    f.write_text(JS, encoding="utf-8")
    result = subprocess.run(
        [node, "--check", str(f)], capture_output=True,
        text=True, check=False, timeout=12,
    )
    assert result.returncode == 0, result.stderr


def test_v8_dry_run_has_zero_side_effects(tmp_path, capsys):
    assert main(["--project-root", str(tmp_path), "--dry-run"]) == 0
    state = json.loads(capsys.readouterr().out)
    assert state["deepseek_sdk_operated_by_server"] is False
    assert state["tool_execution_enabled"] is False
    assert state["model_called"] is False
    assert list(tmp_path.iterdir()) == []
