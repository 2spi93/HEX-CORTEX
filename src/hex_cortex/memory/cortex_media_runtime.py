from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from time import monotonic
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from uuid import uuid4

MediaTransport = Callable[[str, str, dict[str, object] | None, float], dict[str, object]]

_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_WORKFLOW_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_OUTPUT_LIMITS = {
    "generate_image": (4096, 4096, 1),
    "generate_video": (1920, 1080, 1024),
    "generate_3d_scene": (2048, 2048, 1),
    "render_3d_asset": (4096, 4096, 1),
}


def build_media_runtime_descriptors(
    *,
    comfyui_endpoint: str = "http://127.0.0.1:8188",
) -> list[dict[str, object]]:
    base_url = _validated_local_base_url(comfyui_endpoint)
    return [
        {
            "runtime_id": "media.comfyui.image",
            "runtime_kind": "comfyui",
            "base_url": base_url,
            "health_path": "/system_stats",
            "submit_path": "/prompt",
            "supported_outputs": ["generate_image"],
            "priority": 0,
            "local_only": True,
        },
        {
            "runtime_id": "media.comfyui.video",
            "runtime_kind": "comfyui",
            "base_url": base_url,
            "health_path": "/system_stats",
            "submit_path": "/prompt",
            "supported_outputs": ["generate_video"],
            "priority": 10,
            "local_only": True,
        },
        {
            "runtime_id": "media.comfyui.3d",
            "runtime_kind": "comfyui",
            "base_url": base_url,
            "health_path": "/system_stats",
            "submit_path": "/prompt",
            "supported_outputs": ["generate_3d_scene", "render_3d_asset"],
            "priority": 20,
            "local_only": True,
        },
    ]


def probe_media_runtime(
    descriptor: dict[str, object],
    *,
    transport: MediaTransport | None = None,
    timeout_seconds: float = 2.0,
) -> dict[str, object]:
    runtime_id = _required_string(descriptor, "runtime_id")
    base_url = _validated_local_base_url(_required_string(descriptor, "base_url"))
    health_path = _required_string(descriptor, "health_path")
    caller = transport or _http_json
    started = monotonic()
    response: dict[str, object] = {}
    error_type: str | None = None
    try:
        response = caller("GET", base_url + health_path, None, timeout_seconds)
    except Exception as exc:  # noqa: BLE001
        error_type = type(exc).__name__
    devices = _device_summary(response)
    healthy = error_type is None
    stable = {
        "runtime_id": runtime_id,
        "healthy": healthy,
        "devices": devices,
        "error_type": error_type,
    }
    return {
        "receipt_type": "media_runtime_health",
        "runtime_id": runtime_id,
        "runtime_kind": descriptor.get("runtime_kind"),
        "healthy": healthy,
        "latency_ms": round((monotonic() - started) * 1000, 3),
        "supported_outputs": list(descriptor.get("supported_outputs", [])),
        "device_count": len(devices),
        "devices": devices,
        "network_call_performed": True,
        "raw_response_persisted": False,
        "error_type": error_type,
        "receipt_hash": _stable_hash(stable),
    }


def build_media_job(
    *,
    output_id: str,
    prompt: str,
    workflow_id: str = "default.v1",
    negative_prompt: str = "",
    seed: int = 0,
    width: int = 1024,
    height: int = 1024,
    frames: int = 1,
) -> dict[str, object]:
    blockers: list[str] = []
    limits = _OUTPUT_LIMITS.get(output_id)
    if limits is None:
        blockers.append("unsupported_media_output")
    if not prompt.strip():
        blockers.append("prompt_empty")
    if not _WORKFLOW_ID.fullmatch(workflow_id):
        blockers.append("workflow_id_invalid")
    if not 0 <= seed <= 2**63 - 1:
        blockers.append("seed_out_of_range")
    if width < 64 or height < 64 or width % 8 or height % 8:
        blockers.append("dimensions_invalid")
    if limits is not None and (width > limits[0] or height > limits[1]):
        blockers.append("dimensions_exceed_output_limit")
    if frames < 1 or (limits is not None and frames > limits[2]):
        blockers.append("frames_out_of_range")
    if output_id != "generate_video" and frames != 1:
        blockers.append("frames_only_valid_for_video")
    stable = {
        "output_id": output_id,
        "workflow_id": workflow_id,
        "prompt_hash": _text_hash(prompt),
        "negative_prompt_hash": _text_hash(negative_prompt),
        "seed": seed,
        "width": width,
        "height": height,
        "frames": frames,
        "blockers": blockers,
    }
    allowed = not blockers
    return {
        "job_type": "media_runtime_job_v1",
        "job_id": f"media_job_{uuid4().hex}",
        "output_id": output_id,
        "workflow_id": workflow_id,
        "prompt_hash": stable["prompt_hash"],
        "negative_prompt_hash": stable["negative_prompt_hash"],
        "prompt_persisted": False,
        "negative_prompt_persisted": False,
        "seed": seed,
        "width": width,
        "height": height,
        "frames": frames,
        "job_allowed": allowed,
        "generation_performed": False,
        "network_call_performed": False,
        "raw_workflow_persisted": False,
        "blockers": blockers,
        "job_hash": _stable_hash(stable),
        "next_action": "submit_media_job" if allowed else "repair_media_job",
    }


def submit_media_job(
    descriptor: dict[str, object],
    *,
    job: dict[str, object],
    workflow: dict[str, object],
    execute_network: bool = False,
    operator_approved: bool = False,
    transport: MediaTransport | None = None,
    timeout_seconds: float = 8.0,
) -> dict[str, object]:
    blockers: list[str] = []
    if job.get("job_allowed") is not True:
        blockers.append("media_job_not_allowed")
    supported = descriptor.get("supported_outputs", [])
    if not isinstance(supported, list) or job.get("output_id") not in supported:
        blockers.append("runtime_does_not_support_output")
    if not workflow:
        blockers.append("workflow_empty")
    if execute_network and not operator_approved:
        blockers.append("operator_approval_required")
    base_url = _validated_local_base_url(_required_string(descriptor, "base_url"))
    submit_path = _required_string(descriptor, "submit_path")
    workflow_hash = _stable_hash(workflow)
    if blockers:
        return _submission_receipt(job, descriptor, workflow_hash, blockers=blockers)
    if not execute_network:
        return _submission_receipt(
            job,
            descriptor,
            workflow_hash,
            status="planned",
            next_action="rerun_with_network_and_operator_approval",
        )
    caller = transport or _http_json
    started = monotonic()
    error_type: str | None = None
    response: dict[str, object] = {}
    try:
        response = caller(
            "POST",
            base_url + submit_path,
            {"prompt": workflow, "client_id": f"hex-cortex-{job.get('job_id')}"},
            timeout_seconds,
        )
    except Exception as exc:  # noqa: BLE001
        error_type = type(exc).__name__
    prompt_id = response.get("prompt_id") if error_type is None else None
    if error_type is None and not isinstance(prompt_id, str):
        error_type = "MissingPromptId"
    latency_ms = round((monotonic() - started) * 1000, 3)
    if error_type is not None:
        return _submission_receipt(
            job,
            descriptor,
            workflow_hash,
            blockers=["media_submission_failed"],
            error_type=error_type,
            latency_ms=latency_ms,
            network_call_performed=True,
        )
    return _submission_receipt(
        job,
        descriptor,
        workflow_hash,
        status="submitted",
        next_action="poll_media_job",
        prompt_id=prompt_id,
        latency_ms=latency_ms,
        network_call_performed=True,
        generation_performed=True,
    )


def orchestrate_media_runtime(
    *,
    output_id: str,
    prompt: str,
    execute_network: bool = False,
    operator_approved: bool = False,
    workflow: dict[str, object] | None = None,
    transport: MediaTransport | None = None,
) -> dict[str, object]:
    descriptors = build_media_runtime_descriptors()
    job = build_media_job(output_id=output_id, prompt=prompt)
    selected = next(
        (row for row in descriptors if output_id in row["supported_outputs"]),
        None,
    )
    if not execute_network:
        return {
            "orchestration_type": "media_runtime_v1",
            "status": "planned" if selected and job["job_allowed"] else "blocked",
            "selected_runtime_id": selected.get("runtime_id") if selected else None,
            "job": job,
            "health_receipts": [],
            "submission_receipt": None,
            "network_call_performed": False,
            "generation_performed": False,
            "next_action": "run_media_health_probe" if selected else "repair_media_job",
        }
    health = [probe_media_runtime(row, transport=transport) for row in descriptors]
    healthy_ids = {row["runtime_id"] for row in health if row["healthy"] is True}
    selected = next(
        (
            row
            for row in descriptors
            if row["runtime_id"] in healthy_ids and output_id in row["supported_outputs"]
        ),
        None,
    )
    submission = None
    if selected is not None:
        submission = submit_media_job(
            selected,
            job=job,
            workflow=workflow or {},
            execute_network=True,
            operator_approved=operator_approved,
            transport=transport,
        )
    status = "submitted" if submission and submission["status"] == "submitted" else "blocked"
    return {
        "orchestration_type": "media_runtime_v1",
        "status": status,
        "selected_runtime_id": selected.get("runtime_id") if selected else None,
        "job": job,
        "health_receipts": health,
        "submission_receipt": submission,
        "network_call_performed": True,
        "generation_performed": bool(submission and submission["generation_performed"]),
        "next_action": "poll_media_job" if status == "submitted" else "repair_media_runtime",
    }


def _submission_receipt(
    job: dict[str, object],
    descriptor: dict[str, object],
    workflow_hash: str,
    *,
    status: str = "blocked",
    next_action: str = "repair_media_submission",
    blockers: list[str] | None = None,
    error_type: str | None = None,
    prompt_id: object = None,
    latency_ms: float = 0.0,
    network_call_performed: bool = False,
    generation_performed: bool = False,
) -> dict[str, object]:
    blockers = list(blockers or [])
    stable = {
        "job_hash": job.get("job_hash"),
        "runtime_id": descriptor.get("runtime_id"),
        "workflow_hash": workflow_hash,
        "status": status,
        "prompt_id": prompt_id,
        "blockers": blockers,
        "error_type": error_type,
    }
    return {
        "receipt_type": "media_runtime_submission",
        "job_id": job.get("job_id"),
        "job_hash": job.get("job_hash"),
        "runtime_id": descriptor.get("runtime_id"),
        "workflow_id": job.get("workflow_id"),
        "workflow_hash": workflow_hash,
        "raw_workflow_persisted": False,
        "prompt_id": prompt_id,
        "status": status,
        "submission_allowed": status in {"planned", "submitted"},
        "network_call_performed": network_call_performed,
        "generation_performed": generation_performed,
        "latency_ms": latency_ms,
        "error_type": error_type,
        "blockers": blockers,
        "receipt_hash": _stable_hash(stable),
        "next_action": next_action,
    }


def _device_summary(response: dict[str, object]) -> list[dict[str, object]]:
    rows = response.get("devices", [])
    if not isinstance(rows, list):
        return []
    return [
        {
            "name": row.get("name"),
            "type": row.get("type"),
            "vram_total": row.get("vram_total"),
            "vram_free": row.get("vram_free"),
        }
        for row in rows
        if isinstance(row, dict)
    ]


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
        raise ValueError("media runtime response must be a JSON object")
    return result


def _validated_local_base_url(value: str) -> str:
    parsed = _validated_local_url(value)
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}"


def _validated_local_url(value: str):
    parsed = urlparse(value)
    if parsed.scheme != "http" or parsed.hostname not in _LOCAL_HOSTS or parsed.port is None:
        raise ValueError("media runtime endpoint must be explicit localhost http with port")
    return parsed


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _text_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
