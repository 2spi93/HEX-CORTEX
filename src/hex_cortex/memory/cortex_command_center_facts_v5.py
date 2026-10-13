"""Verified, minimal, bounded live HEX-CORTEX facts for CPU dialogue.

Inspired by citation-aware retrieval: evidence originates solely from the
*existing* constrained Command Center V1 snapshot and the V4 registry.
This is NOT an agent, RAG over arbitrary files, an MCP execution path, or
an automatic long-term memory promotion. Never incorporate photo text,
receipts' untrusted labels, user-supplied files or secrets in system prompt.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from hex_cortex.memory.cortex_command_center_v1 import snapshot
from hex_cortex.memory.cortex_command_center_v4 import device_capabilities


def _count(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 100_000 else None


def verified_project_brief(root: Path, *, chat_enabled: bool) -> dict:
    snap = snapshot(root)
    vision = snap["vision"]
    spine = snap["spine"]
    sources = [
        {"id": "snapshot", "path": "/api/snapshot",
         "description": "Local V1 diagnostic (vision, spine, harness)"},
        {"id": "devices", "path": "/api/devices/capabilities",
         "description": "V4 real/simulated device registry"},
        {"id": "capabilities", "path": "/api/capabilities",
         "description": "Command Center feature registry"},
    ]
    scene_count = (
        _count(len(vision["scenes"]))
        if vision.get("status") == "operator_receipt_loaded"
        and isinstance(vision.get("scenes"), list)
        else None
    )
    mask_count = (
        _count(vision.get("mask_count"))
        if vision.get("status") == "operator_receipt_loaded"
        else None
    )
    spine_ok = spine.get("status") == "verified_local_spine" and spine.get("integrity") is True
    events = _count(spine.get("events")) if spine_ok else None
    masks_staged = _count(spine.get("visual_predictions")) if spine_ok else None
    devices = device_capabilities()
    assert devices["real_robot_drone_commands_enabled"] is False
    result = {
        "schema": "hex.project_brief.v5",
        "project": "HEX-CORTEX",
        "runtime": "Windows/Linux localhost Command Center; no outside network from chat",
        "chat": {
            "enabled_by_operator": chat_enabled,
            "provider": "Ollama local via existing LocalOllamaBrain and LocalHarness",
            "device_requested": "cpu", "history_max_previous_exchanges": 3,
            "tools_enabled": False, "browser_or_web_search_available": False,
            "command_execution_enabled": False, "workspace_edits_enabled": False,
            "auto_skill_promotion_enabled": False,
        },
        "installed_integrations": {
            "vision": "V40 verified receipt viewer, not automatic photo segmentation",
            "photo": "Manual local image / camera and bbox export, no semantic recognition",
            "spine": "Existing dedicated local visual event ledger, not verified memory of conversations",
            "harness": "LocalHarness V2 bounded repo-manifest read-only probe",
            "code": "Allowlisted source reader, no editing or execution",
            "3d": "CPU mathematical wireframe cube, not real object reconstruction",
            "voice": "Browser speech recognition may invoke external browser-provider service; voluntary",
            "devices": "Robot and drone are simulated only; no physical actuation",
        },
        "evidence": {
            "vision_status": vision.get("status") if vision.get("status") in {
                "operator_receipt_loaded", "not_available", "error"
            } else "unverified",
            "photographic_scenes_with_receipts": scene_count,
            "operator_predicted_masks": mask_count,
            "independent_human_mask_iou_available": False,
            "dedicated_spine_integrity_verified": spine_ok,
            "dedicated_spine_event_count": events,
            "prediction_observation_event_count": masks_staged,
            "world_model_generalization_independently_proven": False,
        },
        "external_devices": {
            "live_robot_or_drone_control": False,
            "paired_phone_remote_control": False,
            "hardware_interlock_verified": False,
        },
        "sources": sources,
        "provenance_note": (
            "Local receipt integrity is not semantic accuracy, human ground truth, "
            "or proof that objects are tracked across video frames."
        ),
        "unavailable": [
            "live Web browsing", "MCP tool execution", "computer control",
            "remote phone pairing", "live drone/robot actuation",
            "general 3D reconstruction", "offline-guaranteed speech recognition",
            "proven world-model generalization", "self-improvement",
        ],
    }
    compact = json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    result["facts_sha256"] = hashlib.sha256(compact.encode("utf-8")).hexdigest()
    return result


def project_system_facts(brief: dict) -> str:
    """Only server-derived controlled fields; no free-form receipt content."""
    evidence = brief["evidence"]
    chat = brief["chat"]
    def value(number: int | None) -> str:
        return str(number) if number is not None else "not verified"
    text = (
        "VERIFIED LOCAL OPERATOR CAPABILITY RECORD (not generic LLM abilities):\n"
        "Product HEX-CORTEX Command Center. Ollama is a CPU-only local Brain, "
        f"operator-enabled={chat['enabled_by_operator']}; "
        "1 model call per approved message, chat history max 3 exchanges.\n"
        "Real operations: LocalHarness repo-manifest read-only probe; "
        "V40 mask preview receipt inspection; V42/V43 visual-only CanonicalSpine "
        "integrity; manual photo/camera bbox JSON & PNG; browser voice with "
        "POTENTIAL browser cloud; allowlisted code reading; CPU math 3D cube; "
        "fictional robot/drone movement simulation. Do not claim automatic "
        "object identification, 3D reconstruction, or physical control.\n"
        f"V40 receipt status={evidence['vision_status']}; "
        f"inspected scenes={value(evidence['photographic_scenes_with_receipts'])}; "
        f"predicted masks={value(evidence['operator_predicted_masks'])}; "
        "human reference IoU=unknown; no proven visual generalization.\n"
        f"Dedicated V42/V43 spine integrity={evidence['dedicated_spine_integrity_verified']}; "
        f"events={value(evidence['dedicated_spine_event_count'])}; "
        f"predicted-object observation events={value(evidence['prediction_observation_event_count'])}.\n"
        "NOT AVAILABLE to this chat: web search, MCP tool use, executing code "
        "or tests, writing code, controlling Windows, external camera/phone "
        "remote control, driving drones/robots, guaranteed offline STT, "
        "promoting skills, or automatically accessing other repositories.\n"
        "Source keys for operator review: [snapshot] /api/snapshot; "
        "[capabilities] /api/capabilities; "
        "[devices] /api/devices/capabilities. "
        "If a user asks what you can do, separate the limited chat Brain "
        "from the broader independently operated Command Center panels. "
        "Treat this record as machine-read state, not proof of correctness. "
        "Never claim an action was performed unless it was.\n"
    )
    if len(text) > 3500:
        raise ValueError("verified facts context unexpectedly large")
    return text
