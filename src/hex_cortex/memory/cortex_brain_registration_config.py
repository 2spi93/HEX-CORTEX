from __future__ import annotations

import json
from pathlib import Path

_MARKER = "REPLACE_WITH_ME"


def build_registration_template(platform_name: str) -> dict[str, object]:
    key = platform_name.strip().lower()
    if key == "windows":
        values = ("windows-coding-primary", "windows.ollama", "windows-primary", "local")
    elif key in {"kali", "linux"}:
        values = ("kali-research-primary", "kali.ollama", "kali-primary", "private_remote")
    else:
        raise ValueError("platform_name must be windows, kali, or linux")
    brain_id, runtime_id, node_id, provider_scope = values
    return {
        "config_type": "cognitive_brain_registration_config_v1",
        "brain_id": brain_id,
        "model_id": _MARKER,
        "model_family": _MARKER,
        "runtime_id": runtime_id,
        "node_id": node_id,
        "provider_scope": provider_scope,
        "domain_scores": {"coding": None, "research": None, "general": None},
        "reliability_score": None,
        "latency_ms": None,
        "normalized_cost": 0.0,
        "baseline_hash": _MARKER,
        "parameter_class": "unknown",
        "quantization": "unknown",
        "available": True,
        "operator_approved": False,
    }


def write_registration_template(
    path: Path,
    *,
    platform_name: str,
    overwrite: bool = False,
) -> dict[str, object]:
    target = path.resolve()
    if target.exists() and not overwrite:
        raise ValueError("brain config already exists")
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_registration_template(platform_name)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "status": "written",
        "config_path": str(target),
        "next_action": "edit_measured_values_then_register_file",
    }


def load_registration_config(path: Path) -> dict[str, object]:
    target = path.resolve()
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("brain config is unreadable or invalid JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("brain config must be a JSON object")
    if payload.get("config_type") != "cognitive_brain_registration_config_v1":
        raise ValueError("brain config type invalid")

    required_strings = (
        "brain_id",
        "model_id",
        "model_family",
        "runtime_id",
        "node_id",
        "provider_scope",
        "baseline_hash",
        "parameter_class",
        "quantization",
    )
    for field in required_strings:
        value = payload.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"brain config field missing: {field}")
        if value.strip() == _MARKER or value.strip().startswith("<"):
            raise ValueError(f"brain config placeholder not replaced: {field}")

    scores = payload.get("domain_scores")
    if not isinstance(scores, dict) or not scores:
        raise ValueError("brain config domain_scores invalid")
    if not all(
        isinstance(name, str)
        and name.strip()
        and isinstance(value, int | float)
        and 0.0 <= float(value) <= 1.0
        for name, value in scores.items()
    ):
        raise ValueError("brain config domain_scores must contain numbers from 0 to 1")

    for field in ("reliability_score", "normalized_cost"):
        value = payload.get(field)
        if not isinstance(value, int | float) or not 0.0 <= float(value) <= 1.0:
            raise ValueError(f"brain config {field} must be a number from 0 to 1")
    latency = payload.get("latency_ms")
    if not isinstance(latency, int | float) or not 0.0 <= float(latency) <= 3_600_000.0:
        raise ValueError("brain config latency_ms must be a non-negative number")
    baseline_hash = str(payload["baseline_hash"])
    if len(baseline_hash) != 64:
        raise ValueError("brain config baseline_hash must be 64 hexadecimal characters")
    try:
        int(baseline_hash, 16)
    except ValueError as exc:
        raise ValueError("brain config baseline_hash must be 64 hexadecimal characters") from exc
    if payload.get("operator_approved") is not True:
        raise ValueError("brain config operator_approved must be true")
    if not isinstance(payload.get("available", True), bool):
        raise ValueError("brain config available must be boolean")
    return payload
