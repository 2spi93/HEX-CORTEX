from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from hex_cortex.memory.cortex_gateway import CortexAdapter

MediaTransport = Callable[[str, str, dict[str, object] | None, float], dict[str, object]]
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_WORKFLOWS = (
    ("image.local.v1", "generate_image", 1),
    ("video.local.v1", "generate_video", 1),
    ("geometry.local.v1", "generate_3d_scene", 1),
)


def list_media_runtime_workflows() -> list[dict[str, object]]:
    return [
        {
            "workflow_id": workflow_id,
            "output_id": output_id,
            "workflow_version": version,
            "backend": "comfyui",
            "state": "declared",
            "raw_prompt_persistence_allowed": False,
        }
        for workflow_id, output_id, version in _WORKFLOWS
    ]


def build_media_runtime_plan(endpoint: str = "http://127.0.0.1:8188") -> dict[str, object]:
    return {
        "plan_type": "media_runtime_v1",
        "backend": "comfyui",
        "base_url": _local_base_url(endpoint),
        "submit_path": "/prompt",
        "history_path": "/history/{prompt_id}",
        "gateway_lane": "asset",
        "operator_gate_required": True,
        "workflows": list_media_runtime_workflows(),
        "raw_prompt_persistence_allowed": False,
        "next_action": "probe_media_runtime",
    }


def submit_media_workflow(
    request: dict[str, object],
    *,
    endpoint: str = "http://127.0.0.1:8188",
    transport: MediaTransport | None = None,
    timeout_seconds: float = 15.0,
) -> dict[str, object]:
    workflow_id = request.get("workflow_id")
    output_id = request.get("output_id")
    version = request.get("workflow_version")
    graph = request.get("workflow_graph")
    client_id = request.get("client_id")
    declared = next(
        (row for row in list_media_runtime_workflows() if row["workflow_id"] == workflow_id),
        None,
    )
    blockers = []
    if declared is None:
        blockers.append("unknown_media_workflow")
    elif output_id != declared["output_id"]:
        blockers.append("workflow_output_mismatch")
    elif version != declared["workflow_version"]:
        blockers.append("workflow_version_mismatch")
    if not isinstance(graph, dict) or not graph:
        blockers.append("workflow_graph_missing")
    if not isinstance(client_id, str) or not client_id:
        blockers.append("client_id_missing")
    if blockers:
        return {
            "status": "blocked",
            "summary": "media workflow request blocked",
            "blockers": blockers,
            "network_call_performed": False,
            "external_effect_performed": False,
        }
    caller = transport or _http_json
    response = caller(
        "POST",
        _local_base_url(endpoint) + "/prompt",
        {"prompt": graph, "client_id": client_id},
        timeout_seconds,
    )
    prompt_id = response.get("prompt_id")
    if not isinstance(prompt_id, str) or not prompt_id:
        return {
            "status": "blocked",
            "summary": "media backend returned no prompt id",
            "blockers": ["prompt_id_missing"],
            "network_call_performed": True,
            "external_effect_performed": False,
        }
    return {
        "status": "ok",
        "summary": "media workflow queued",
        "backend": "comfyui",
        "workflow_id": workflow_id,
        "workflow_version": version,
        "output_id": output_id,
        "prompt_id_hash": hashlib.sha256(prompt_id.encode("utf-8")).hexdigest(),
        "workflow_graph_hash": _hash(graph),
        "queued": True,
        "network_call_performed": True,
        "external_effect_performed": True,
        "raw_prompt_persisted": False,
        "raw_result_persisted": False,
    }


def build_comfyui_media_adapter(
    *,
    endpoint: str = "http://127.0.0.1:8188",
    timeout_seconds: float = 15.0,
    transport: MediaTransport | None = None,
) -> CortexAdapter:
    _local_base_url(endpoint)

    def handler(request: dict[str, object]) -> dict[str, object]:
        return submit_media_workflow(
            request,
            endpoint=endpoint,
            transport=transport,
            timeout_seconds=timeout_seconds,
        )

    return CortexAdapter(
        name="local.comfyui",
        lane="asset",
        handler=handler,
        description="Versioned local media workflow adapter.",
        requires_operator=True,
        network_capable=True,
        auto_safe_capable=False,
        timeout_seconds=timeout_seconds,
    )


def build_media_artifact_receipt(
    *,
    runtime_result: dict[str, object],
    source_request_hash: str,
    artifact_refs: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    refs = list(artifact_refs or [])
    blockers = []
    if runtime_result.get("status") != "ok":
        blockers.append("media_runtime_not_ok")
    if runtime_result.get("external_effect_performed") is not True:
        blockers.append("media_effect_not_performed")
    if not source_request_hash:
        blockers.append("source_request_hash_missing")
    allowed = not blockers
    stable = {
        "workflow_id": runtime_result.get("workflow_id"),
        "workflow_version": runtime_result.get("workflow_version"),
        "output_id": runtime_result.get("output_id"),
        "source_request_hash": source_request_hash,
        "workflow_graph_hash": runtime_result.get("workflow_graph_hash"),
        "artifact_refs": refs,
        "allowed": allowed,
    }
    return {
        "receipt_type": "media_artifact_receipt",
        "receipt_allowed": allowed,
        "workflow_id": runtime_result.get("workflow_id"),
        "workflow_version": runtime_result.get("workflow_version"),
        "output_id": runtime_result.get("output_id"),
        "source_request_hash": source_request_hash,
        "workflow_graph_hash": runtime_result.get("workflow_graph_hash"),
        "artifact_refs": refs,
        "artifact_count": len(refs),
        "raw_prompt_persisted": False,
        "artifact_bytes_persisted": False,
        "blockers": blockers,
        "receipt_hash": _hash(stable),
    }


def _http_json(
    method: str,
    url: str,
    payload: dict[str, object] | None,
    timeout_seconds: float,
) -> dict[str, object]:
    _local_url(url)
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = Request(url, data=body, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - localhost only.
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError("media response must be a JSON object")
    return result


def _local_base_url(value: str) -> str:
    parsed = _local_url(value)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def _local_url(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("media endpoint must be localhost http with explicit port")
    return parsed


def _hash(payload: object) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
