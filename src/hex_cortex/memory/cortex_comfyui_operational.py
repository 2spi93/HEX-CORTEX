from __future__ import annotations

import copy
import hashlib
import json
import re
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

JsonTransport = Callable[[str, str, dict[str, object] | None, float], dict[str, object]]

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_WORKFLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_PLACEHOLDER = re.compile(r"^__[A-Z0-9_]+__$")
_ALLOWED_CAPABILITIES = {
    "generate_image",
    "generate_video",
    "generate_3d_scene",
    "render_3d_asset",
}


def probe_comfyui(
    endpoint: str = "http://127.0.0.1:8188",
    *,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 3.0,
) -> dict[str, object]:
    base_url = _validated_local_base_url(endpoint)
    caller = transport or _http_json
    receipts: dict[str, dict[str, object]] = {}
    for name, path in (
        ("system_stats", "/system_stats"),
        ("queue", "/queue"),
        ("object_info", "/object_info"),
    ):
        started = time.monotonic()
        error_type: str | None = None
        response: dict[str, object] = {}
        try:
            response = caller("GET", base_url + path, None, timeout_seconds)
        except Exception as exc:  # noqa: BLE001
            error_type = type(exc).__name__
        receipts[name] = {
            "healthy": error_type is None,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
            "error_type": error_type,
            "response_hash": _stable_hash(response) if error_type is None else None,
            "raw_response_persisted": False,
        }
    healthy = all(row["healthy"] is True for row in receipts.values())
    system = receipts["system_stats"]
    return {
        "receipt_type": "comfyui_operational_probe_v1",
        "endpoint": base_url,
        "healthy": healthy,
        "system_stats_healthy": system["healthy"],
        "queue_healthy": receipts["queue"]["healthy"],
        "object_info_healthy": receipts["object_info"]["healthy"],
        "checks": receipts,
        "network_call_performed": True,
        "raw_response_persisted": False,
        "next_action": "import_reviewed_workflow" if healthy else "start_or_repair_comfyui",
    }


def validate_api_workflow(
    workflow: dict[str, object],
    *,
    allow_placeholders: bool = False,
) -> dict[str, object]:
    blockers: list[str] = []
    class_counts: dict[str, int] = {}
    unresolved: list[str] = []
    node_ids = set(workflow)
    if not workflow:
        blockers.append("workflow_empty")
    for node_id, raw_node in workflow.items():
        if not isinstance(node_id, str) or not node_id:
            blockers.append("node_id_invalid")
            continue
        if not isinstance(raw_node, dict):
            blockers.append(f"node_not_object:{node_id}")
            continue
        class_type = raw_node.get("class_type")
        inputs = raw_node.get("inputs")
        if not isinstance(class_type, str) or not class_type:
            blockers.append(f"class_type_missing:{node_id}")
        else:
            class_counts[class_type] = class_counts.get(class_type, 0) + 1
        if not isinstance(inputs, dict):
            blockers.append(f"inputs_missing:{node_id}")
            continue
        for input_name, value in inputs.items():
            if isinstance(value, str) and _PLACEHOLDER.fullmatch(value):
                unresolved.append(f"{node_id}.{input_name}:{value}")
            if _looks_like_link(value):
                source_id = str(value[0])
                output_slot = value[1]
                if source_id not in node_ids:
                    blockers.append(f"link_source_missing:{node_id}.{input_name}->{source_id}")
                if not isinstance(output_slot, int) or output_slot < 0:
                    blockers.append(f"link_slot_invalid:{node_id}.{input_name}")
    if unresolved and not allow_placeholders:
        blockers.append("unresolved_placeholders")
    output_nodes = sorted(
        node_id
        for node_id, node in workflow.items()
        if isinstance(node, dict)
        and isinstance(node.get("class_type"), str)
        and node["class_type"].startswith(("Save", "Preview"))
    )
    if not output_nodes:
        blockers.append("output_node_missing")
    blockers = sorted(set(blockers))
    allowed = not blockers
    stable = {
        "workflow_hash": _stable_hash(workflow),
        "node_count": len(workflow),
        "class_counts": class_counts,
        "unresolved": unresolved,
        "blockers": blockers,
    }
    return {
        "validation_type": "comfyui_api_workflow_validation_v1",
        "workflow_valid": allowed,
        "workflow_hash": stable["workflow_hash"],
        "node_count": len(workflow),
        "class_counts": dict(sorted(class_counts.items())),
        "output_nodes": output_nodes,
        "unresolved_placeholders": unresolved,
        "placeholder_mode": allow_placeholders,
        "blockers": blockers,
        "validation_hash": _stable_hash(stable),
        "next_action": "homologate_workflow" if allowed else "repair_workflow",
    }


def homologate_workflow(
    *,
    workflow_id: str,
    capability: str,
    workflow: dict[str, object],
    bindings: dict[str, dict[str, object]],
    allow_placeholders: bool = False,
    operator_approved: bool = False,
) -> dict[str, object]:
    blockers: list[str] = []
    if not _WORKFLOW_ID.fullmatch(workflow_id):
        blockers.append("workflow_id_invalid")
    if capability not in _ALLOWED_CAPABILITIES:
        blockers.append("capability_unsupported")
    if not operator_approved:
        blockers.append("operator_approval_required")
    validation = validate_api_workflow(workflow, allow_placeholders=allow_placeholders)
    if validation["workflow_valid"] is not True:
        blockers.extend(validation["blockers"])
    blockers.extend(_validate_bindings(workflow, bindings))
    blockers = sorted(set(blockers))
    approved = not blockers
    stable = {
        "workflow_id": workflow_id,
        "capability": capability,
        "workflow_hash": validation["workflow_hash"],
        "bindings": bindings,
        "template_mode": allow_placeholders,
        "blockers": blockers,
    }
    return {
        "manifest_type": "comfyui_homologated_workflow_v1",
        "workflow_id": workflow_id,
        "capability": capability,
        "workflow_hash": validation["workflow_hash"],
        "validation_hash": validation["validation_hash"],
        "bindings": bindings,
        "template_mode": allow_placeholders,
        "review_status": "approved_template" if approved and allow_placeholders else (
            "approved_runnable" if approved else "blocked"
        ),
        "homologated": approved,
        "raw_prompt_persisted": False,
        "manifest_hash": _stable_hash(stable),
        "blockers": blockers,
        "next_action": "persist_workflow_bundle" if approved else "repair_homologation",
    }


def import_workflow_bundle(
    *,
    source_path: Path,
    registry_root: Path,
    workflow_id: str,
    capability: str,
    bindings: dict[str, dict[str, object]],
    allow_placeholders: bool = False,
    operator_approved: bool = False,
) -> dict[str, object]:
    source = source_path.resolve()
    registry = registry_root.resolve()
    if not source.is_file():
        return _import_blocked("workflow_source_missing")
    try:
        workflow = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _import_blocked("workflow_source_invalid_json")
    if not isinstance(workflow, dict):
        return _import_blocked("workflow_source_must_be_object")
    manifest = homologate_workflow(
        workflow_id=workflow_id,
        capability=capability,
        workflow=workflow,
        bindings=bindings,
        allow_placeholders=allow_placeholders,
        operator_approved=operator_approved,
    )
    if manifest["homologated"] is not True:
        return {
            "receipt_type": "comfyui_workflow_import_v1",
            "imported": False,
            "manifest": manifest,
            "files_written": [],
            "blockers": list(manifest["blockers"]),
            "next_action": "repair_homologation",
        }
    target = registry / workflow_id
    target.mkdir(parents=True, exist_ok=True)
    workflow_file = target / "workflow.api.json"
    manifest_file = target / "manifest.json"
    workflow_file.write_text(_canonical_json(workflow) + "\n", encoding="utf-8")
    manifest_file.write_text(_canonical_json(manifest) + "\n", encoding="utf-8")
    return {
        "receipt_type": "comfyui_workflow_import_v1",
        "workflow_id": workflow_id,
        "imported": True,
        "registry_path": str(target),
        "workflow_hash": manifest["workflow_hash"],
        "manifest_hash": manifest["manifest_hash"],
        "files_written": [str(workflow_file), str(manifest_file)],
        "blockers": [],
        "next_action": "bind_and_validate_workflow",
    }


def load_workflow_bundle(
    registry_root: Path,
    workflow_id: str,
) -> tuple[dict[str, object], dict[str, object]]:
    if not _WORKFLOW_ID.fullmatch(workflow_id):
        raise ValueError("workflow_id_invalid")
    target = registry_root.resolve() / workflow_id
    workflow = json.loads((target / "workflow.api.json").read_text(encoding="utf-8"))
    manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(workflow, dict) or not isinstance(manifest, dict):
        raise ValueError("workflow_bundle_invalid")
    if _stable_hash(workflow) != manifest.get("workflow_hash"):
        raise ValueError("workflow_hash_mismatch")
    return workflow, manifest


def bind_workflow(
    workflow: dict[str, object],
    manifest: dict[str, object],
    values: dict[str, object],
) -> dict[str, object]:
    result = copy.deepcopy(workflow)
    bindings = manifest.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("manifest_bindings_invalid")
    missing: list[str] = []
    for semantic_name, binding in bindings.items():
        if not isinstance(binding, dict):
            raise ValueError(f"binding_invalid:{semantic_name}")
        required = binding.get("required", True) is True
        if semantic_name not in values:
            if required:
                missing.append(semantic_name)
            continue
        node_id = str(binding.get("node_id"))
        input_name = binding.get("input")
        node = result.get(node_id)
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            raise ValueError(f"binding_node_missing:{semantic_name}")
        if not isinstance(input_name, str) or input_name not in node["inputs"]:
            raise ValueError(f"binding_input_missing:{semantic_name}")
        node["inputs"][input_name] = values[semantic_name]
    if missing:
        raise ValueError("required_bindings_missing:" + ",".join(sorted(missing)))
    validation = validate_api_workflow(result, allow_placeholders=False)
    if validation["workflow_valid"] is not True:
        raise ValueError("bound_workflow_invalid:" + ",".join(validation["blockers"]))
    return result


def submit_and_wait(
    *,
    endpoint: str,
    workflow: dict[str, object],
    operator_approved: bool = False,
    transport: JsonTransport | None = None,
    timeout_seconds: float = 120.0,
    poll_interval_seconds: float = 0.5,
) -> dict[str, object]:
    if not operator_approved:
        return {
            "receipt_type": "comfyui_execution_v1",
            "status": "blocked",
            "network_call_performed": False,
            "generation_performed": False,
            "blockers": ["operator_approval_required"],
            "next_action": "request_operator_approval",
        }
    validation = validate_api_workflow(workflow, allow_placeholders=False)
    if validation["workflow_valid"] is not True:
        return {
            "receipt_type": "comfyui_execution_v1",
            "status": "blocked",
            "network_call_performed": False,
            "generation_performed": False,
            "blockers": list(validation["blockers"]),
            "next_action": "repair_workflow",
        }
    base_url = _validated_local_base_url(endpoint)
    caller = transport or _http_json
    client_id = "hex-cortex-" + validation["workflow_hash"][:16]
    response = caller(
        "POST",
        base_url + "/prompt",
        {"prompt": workflow, "client_id": client_id},
        min(timeout_seconds, 15.0),
    )
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        return {
            "receipt_type": "comfyui_execution_v1",
            "status": "failed",
            "network_call_performed": True,
            "generation_performed": False,
            "blockers": ["prompt_id_missing"],
            "next_action": "inspect_comfyui_logs",
        }
    deadline = time.monotonic() + timeout_seconds
    history: dict[str, object] = {}
    while time.monotonic() < deadline:
        history = caller("GET", base_url + f"/history/{prompt_id}", None, 10.0)
        if prompt_id in history:
            break
        time.sleep(poll_interval_seconds)
    completed = prompt_id in history
    outputs = _output_manifest(history.get(prompt_id, {}) if completed else {})
    stable = {
        "workflow_hash": validation["workflow_hash"],
        "prompt_id": prompt_id,
        "completed": completed,
        "outputs": outputs,
    }
    return {
        "receipt_type": "comfyui_execution_v1",
        "status": "completed" if completed else "timeout",
        "prompt_id": prompt_id,
        "workflow_hash": validation["workflow_hash"],
        "output_manifest": outputs,
        "network_call_performed": True,
        "generation_performed": completed,
        "raw_history_persisted": False,
        "receipt_hash": _stable_hash(stable),
        "blockers": [] if completed else ["history_timeout"],
        "next_action": "consume_output_manifest" if completed else "inspect_queue_and_history",
    }


def _validate_bindings(
    workflow: dict[str, object],
    bindings: dict[str, dict[str, object]],
) -> list[str]:
    blockers: list[str] = []
    if not bindings:
        return ["bindings_empty"]
    for semantic_name, binding in bindings.items():
        if not isinstance(semantic_name, str) or not semantic_name:
            blockers.append("binding_name_invalid")
            continue
        if not isinstance(binding, dict):
            blockers.append(f"binding_not_object:{semantic_name}")
            continue
        node_id = str(binding.get("node_id"))
        input_name = binding.get("input")
        node = workflow.get(node_id)
        if not isinstance(node, dict) or not isinstance(node.get("inputs"), dict):
            blockers.append(f"binding_node_missing:{semantic_name}")
            continue
        if not isinstance(input_name, str) or input_name not in node["inputs"]:
            blockers.append(f"binding_input_missing:{semantic_name}")
    return blockers


def _output_manifest(history_entry: object) -> list[dict[str, object]]:
    if not isinstance(history_entry, dict):
        return []
    outputs = history_entry.get("outputs")
    if not isinstance(outputs, dict):
        return []
    rows: list[dict[str, object]] = []
    for node_id, raw_output in outputs.items():
        if not isinstance(raw_output, dict):
            continue
        for key in ("images", "gifs", "audio"):
            assets = raw_output.get(key)
            if not isinstance(assets, list):
                continue
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                rows.append(
                    {
                        "node_id": str(node_id),
                        "asset_kind": key,
                        "filename": asset.get("filename"),
                        "subfolder": asset.get("subfolder"),
                        "folder_type": asset.get("type"),
                    }
                )
    return rows


def _looks_like_link(value: object) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and isinstance(value[0], str | int)
    )


def _import_blocked(blocker: str) -> dict[str, object]:
    return {
        "receipt_type": "comfyui_workflow_import_v1",
        "imported": False,
        "files_written": [],
        "blockers": [blocker],
        "next_action": "repair_workflow_source",
    }


def _http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    timeout_seconds: float,
) -> dict[str, object]:
    _validated_local_url(url)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(
        url,
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("comfyui response must be a JSON object")
    return result


def _validated_local_base_url(value: str) -> str:
    parsed = _validated_local_url(value)
    host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
    return f"http://{host}:{parsed.port}"


def _validated_local_url(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("ComfyUI endpoint must be explicit localhost HTTP with port")
    return parsed


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, indent=2)


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
