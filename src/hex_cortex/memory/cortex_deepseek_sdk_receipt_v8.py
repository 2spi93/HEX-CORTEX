"""Read-only, untrusted operator-imported V8 DSH SDK pilot receipt.

No automatic CanonicalSpine promotion, no runtime access, no tool calls.
A locally copied receipt demonstrates what an external VM *reports*, not
independent proof of VM isolation, identity, correctness or permissions.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_RECEIPT = Path("receipts/v8_deepseek_sdk/operator_import.json")
_SHA = re.compile(r"[a-f0-9]{64}\Z")
_SAFE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,120}\Z")
_KINDS = {
    "turn/start", "turn/end", "step/start", "step/end",
    "tool/call", "tool/result", "assistant/message",
}


def imported_sdk_pilot_summary(root: Path) -> dict:
    project = Path(root).resolve(strict=True)
    file = project / _RECEIPT
    if not file.is_file():
        return {
            "schema": "hex.deepseek_sdk_import_v8",
            "status": "no_operator_imported_receipt",
            "pilot_runtime_connected_to_chat": False,
            "auto_promoted_to_canonical_spine": False,
            "tools_granted_to_chat": [],
            "files_written": False,
        }
    if file.is_symlink() or file.parent.is_symlink():
        raise ValueError("v8_import_symlinks_denied")
    if not file.resolve().is_relative_to(project):
        raise ValueError("v8_receipt_outside_repo")
    if file.stat().st_size > 24_000:
        raise ValueError("v8_operator_receipt_too_large")
    raw = file.read_bytes()
    try:
        record = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("v8_invalid_receipt_json") from exc
    if not isinstance(record, dict) or record.get("schema") != "hex.deepseek_sdk_disposable_pilot.v8":
        raise ValueError("v8_unexpected_receipt_schema")
    if (
        record.get("profile") != "sdk-minimal"
        or record.get("external_sdk_runtime_launched") is not True
        or record.get("model_called") is not True
        or record.get("sdk_test_double_used") is not False
        or record.get("auto_promoted_to_canonical_spine") is not False
        or not isinstance(record.get("observed_tool_call_events"), int)
        or type(record["observed_tool_call_events"]) is not int
        or not isinstance(record.get("observed_tool_result_events"), int)
        or type(record["observed_tool_result_events"]) is not int
        or any(
            not 0 <= record[k] <= 20_000
            for k in ("observed_tool_call_events", "observed_tool_result_events")
        )
    ):
        raise ValueError("v8_not_a_genuine_sdk_pilot_receipt")
    for name in ("session_id_sha256", "prompt_sha256", "response_sha256",
                 "calc_file_sha256_after"):
        if not isinstance(record.get(name), str) or not _SHA.fullmatch(record[name]):
            raise ValueError("v8_invalid_receipt_digest")
    for name in ("model", "provider", "sdk_version_expected"):
        if not isinstance(record.get(name), str) or not _SAFE_NAME.fullmatch(record[name]):
            raise ValueError("v8_invalid_receipt_label")
    counts = record.get("root_event_type_counts")
    if not isinstance(counts, dict) or set(counts) != _KINDS or any(
        type(value) is not int or value < 0 or value > 20_000
        for value in counts.values()
    ):
        raise ValueError("v8_invalid_event_counts")
    if (
        counts["tool/call"] != record["observed_tool_call_events"]
        or counts["tool/result"] != record["observed_tool_result_events"]
    ):
        raise ValueError("v8_inconsistent_event_counts")
    return {
        "schema": "hex.deepseek_sdk_import_v8",
        "status": "operator_imported_vm_report_unverified",
        "fixture_sdk_turn_reported": True,
        "fixture_exact_expected_fix_reported": record.get("exact_expected_fix_found") is True,
        "model": record["model"],
        "provider": record["provider"],
        "sdk_version_reported": record["sdk_version_expected"],
        "session_id_sha256": record["session_id_sha256"],
        "source_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "observed_tool_call_events_reported": counts["tool/call"],
        "observed_tool_result_events_reported": counts["tool/result"],
        "specific_tool_name_registry_connected": False,
        "independent_vm_isolation_attested": False,
        "pilot_runtime_connected_to_chat": False,
        "tools_granted_to_chat": [],
        "human_review_required": True,
        "auto_promoted_to_canonical_spine": False,
        "files_written": False,
    }
