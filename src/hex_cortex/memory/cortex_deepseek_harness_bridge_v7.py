"""V7 zero-execution integration boundary for the external DeepSeek Harness.

DSH is third-party pre-stable agent software with real shell/file/network
capabilities. This registry is *not* an executable bridge: it shares only
server-derived, fixed-schema HEX-CORTEX facts and never launches/imports DSH.
Actual agent runs must first be evaluated in an independently isolated VM.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
from pathlib import Path

from hex_cortex.memory.cortex_command_center_facts_v5 import verified_project_brief


_OFFICIAL = "https://github.com/deepseek-ai/deepseek-harness"
_SDK_DOC = "https://github.com/deepseek-ai/deepseek-harness/tree/master/python/sdk"
_SAFETY = "https://github.com/deepseek-ai/deepseek-harness/blob/master/SAFETY.md"


def _sdk_version() -> str | None:
    """Read installed package metadata without importing or running plugins."""
    try:
        name = importlib.metadata.version("deepseek-harness-sdk")
    except importlib.metadata.PackageNotFoundError:
        return None
    # Values from package metadata are untrusted and must remain bounded.
    return name[:80] if name and len(name) <= 80 else None


def deepseek_harness_bridge_status(
    project_root: Path, *, sdk_version: str | None = None,
) -> dict:
    """Truthful opt-in capability map. NO process, network, install or I/O write."""
    project = Path(project_root).resolve(strict=True)
    if not project.is_dir():
        raise ValueError("v7_project_root_invalid")
    brief = verified_project_brief(project, chat_enabled=False)
    sdk = _sdk_version() if sdk_version is None else sdk_version
    if sdk is not None and (not isinstance(sdk, str) or len(sdk) > 80):
        raise ValueError("v7_sdk_version_invalid")
    capabilities = [
        {"capability": "agent_loop_and_sessions", "source": "deepseek_harness",
         "candidate": True, "connected": False, "gate": "isolated_runtime_review"},
        {"capability": "coding_and_tests", "source": "deepseek_harness",
         "candidate": True, "connected": False, "gate": "workspace_snapshot_and_approval"},
        {"capability": "research_and_external_web", "source": "deepseek_harness",
         "candidate": True, "connected": False, "gate": "privacy_and_network_approval"},
        {"capability": "skills_plugins_mcp", "source": "deepseek_harness",
         "candidate": True, "connected": False, "gate": "plugin_allowlist_and_review"},
        {"capability": "session_event_replay", "source": "deepseek_harness",
         "candidate": True, "connected": False, "gate": "evidence_mapping_validation"},
        {"capability": "local_cpu_brain", "source": "hex_cortex",
         "candidate": False, "connected": True, "gate": "per_message_approval"},
        {"capability": "vision_cpu", "source": "hex_cortex",
         "candidate": False, "connected": False, "gate": "V6_server_flag_opt_in"},
        {"capability": "canonical_evidence", "source": "hex_cortex",
         "candidate": False, "connected": bool(
             brief["evidence"]["dedicated_spine_integrity_verified"]
         ), "gate": "data_integrity_not_semantic_truth"},
        {"capability": "remote_robot_drone_actuation", "source": "none",
         "candidate": False, "connected": False, "gate": "forbidden"},
    ]
    facts = {
        "schema": "hex.deepseek_harness_compatibility.v7",
        "status": "read_only_bridge_preflight_no_sdk_started",
        "upstream_repo": _OFFICIAL,
        "upstream_sdk_docs": _SDK_DOC,
        "upstream_safety_notice": _SAFETY,
        "upstream_dev_preview_unstable_api": True,
        "external_sdk_distribution_installed": bool(sdk),
        "external_sdk_distribution_version": sdk,
        "external_runtime_launched": False,
        "installed_sdk_is_not_verified_runtime": True,
        "hex_project": brief["project"],
        "hex_fact_digest": brief["facts_sha256"],
        "hex_vision_evidence_status": brief["evidence"]["vision_status"],
        "hex_visual_spine_verified": brief["evidence"]["dedicated_spine_integrity_verified"],
        "bridge_transport_proposal": "deepseek-harness-sdk/json_rpc_stdio",
        "mode": "read_only_snapshot_no_actuation",
        "capabilities": capabilities,
        "shared_data": [
            "server-derived capability names and statuses",
            "fixed-schema public source keys",
            "hashes and redacted integrity counters",
        ],
        "shared_secrets": False,
        "repository_files_exposed": False,
        "photos_or_voice_exposed": False,
        "executed_tools": [],
        "files_written": False,
        "model_called": False,
        "network_used": False,
        "real_deepseek_integration_attested": False,
        "requires_before_execution": [
            "pin_reviewed_DSH_version_and_dependencies",
            "run_disposable_VM_without_host_repo_mounts",
            "isolate_credentials_and_agent_home",
            "review_DSH_plugins_sandbox_approval_policy",
            "evaluate_tool_execution_in_fixture_repo",
            "audit_output_events_before_importing_to_CanonicalSpine",
        ],
    }
    encoded = json.dumps(facts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    facts["receipt_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return facts
