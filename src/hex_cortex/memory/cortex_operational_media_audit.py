from __future__ import annotations

import json
from pathlib import Path

from hex_cortex.memory.cortex_comfyui_operational import validate_api_workflow
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor


def audit_operational_media_encoder(project_root: Path) -> dict[str, object]:
    root = project_root.resolve()
    memory_root = root / "src" / "hex_cortex" / "memory"
    workflow_root = root / "workflows" / "comfyui"
    workflow_path = workflow_root / "txt2img_basic_api_v1.workflow.json"
    profile_path = workflow_root / "txt2img_basic_api_v1.profile.json"
    files = {
        "comfyui_operational_gateway": memory_root / "cortex_comfyui_operational.py",
        "frozen_encoder_adapter": memory_root / "cortex_frozen_encoder.py",
        "operational_cli": memory_root / "cortex_operational_media_cli.py",
        "txt2img_workflow_template": workflow_path,
        "txt2img_homologation_profile": profile_path,
    }
    facts = {name: path.is_file() for name, path in files.items()}
    blockers = [f"{name}_missing" for name, available in facts.items() if not available]
    workflow_validation: dict[str, object] | None = None
    profile_valid = False
    if workflow_path.is_file():
        try:
            payload = json.loads(workflow_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                workflow_validation = validate_api_workflow(
                    payload,
                    allow_placeholders=True,
                )
            else:
                blockers.append("txt2img_workflow_not_object")
        except (OSError, json.JSONDecodeError):
            blockers.append("txt2img_workflow_invalid_json")
    if profile_path.is_file():
        try:
            profile = json.loads(profile_path.read_text(encoding="utf-8"))
            profile_valid = (
                isinstance(profile, dict)
                and profile.get("review_status") == "approved_template"
                and isinstance(profile.get("bindings"), dict)
                and bool(profile["bindings"])
            )
        except (OSError, json.JSONDecodeError):
            profile_valid = False
        if not profile_valid:
            blockers.append("txt2img_profile_invalid")
    if workflow_validation is not None and workflow_validation["workflow_valid"] is not True:
        blockers.extend(workflow_validation["blockers"])
    descriptor = build_frozen_encoder_descriptor()
    if descriptor["descriptor_allowed"] is not True:
        blockers.extend(descriptor["blockers"])
    blockers = sorted(set(blockers))
    architecture_ready = not blockers
    return {
        "audit_type": "operational_comfyui_frozen_encoder_v1",
        "project_root": str(root),
        "architecture_ready": architecture_ready,
        "operational_ready": False,
        "runtime_facts": facts,
        "workflow_validation": workflow_validation,
        "profile_valid": profile_valid,
        "encoder_descriptor": descriptor,
        "network_probe_performed": False,
        "model_call_performed": False,
        "blockers": blockers,
        "next_action": (
            "probe_local_comfyui_and_encoder_cache"
            if architecture_ready
            else "repair_operational_media_package"
        ),
    }
