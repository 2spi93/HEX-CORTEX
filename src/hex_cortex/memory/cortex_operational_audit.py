from __future__ import annotations

import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Iterable

from hex_cortex.memory.cortex_bundle import build_cortex_bundle
from hex_cortex.memory.cortex_comfyui_operational import probe_comfyui
from hex_cortex.memory.cortex_frozen_encoder import build_frozen_encoder_descriptor
from hex_cortex.memory.cortex_frozen_encoder import probe_frozen_encoder_runtime
from hex_cortex.memory.cortex_research_social_credentials import build_citation_pack
from hex_cortex.memory.cortex_runtime_model_orchestration import orchestrate_runtime_models
from hex_cortex.memory.cortex_runtime_probe import probe_cortex_runtime
from hex_cortex.memory.cortex_searxng import audit_searxng_runtime
from hex_cortex.memory.cortex_searxng import build_searxng_searcher
from hex_cortex.memory.cortex_wiring import audit_cortex_wiring

_DEFAULT_RESEARCH_QUERY = "HEX-CORTEX operational readiness"
_MAX_RECEIPT_FILES = 256
_MAX_RECEIPT_BYTES = 2 * 1024 * 1024


def build_operational_audit(
    project_root: Path,
    *,
    execute_network: bool = False,
    include_research: bool = True,
    research_query: str = _DEFAULT_RESEARCH_QUERY,
    comfyui_endpoint: str = "http://127.0.0.1:8188",
    searxng_endpoint: str = "http://127.0.0.1:8888/search",
    model_ref: str = "facebook/dinov2-base",
    model_cache_present: bool | None = None,
    active_registry_path: Path | None = None,
    runtime_fact_overrides: dict[str, bool] | None = None,
    filesystem_receipt: dict[str, object] | None = None,
    runtime_receipt: dict[str, object] | None = None,
    media_receipt: dict[str, object] | None = None,
    research_receipt: dict[str, object] | None = None,
    encoder_receipt: dict[str, object] | None = None,
) -> dict[str, object]:
    root = project_root.resolve()
    overrides = _validate_boolean_facts(runtime_fact_overrides or {})

    filesystem = filesystem_receipt or probe_cortex_runtime(root)
    runtime = runtime_receipt or orchestrate_runtime_models(execute_network=execute_network)
    media = media_receipt or _probe_media(
        endpoint=comfyui_endpoint,
        execute_network=execute_network,
    )
    research = research_receipt or _probe_research(
        endpoint=searxng_endpoint,
        query=research_query,
        execute_network=execute_network and include_research,
    )

    cache_present = (
        detect_huggingface_model_cache(model_ref)
        if model_cache_present is None
        else model_cache_present
    )
    descriptor = build_frozen_encoder_descriptor(model_ref=model_ref, device="auto")
    encoder = encoder_receipt or probe_frozen_encoder_runtime(
        descriptor,
        model_cache_present=cache_present,
    )

    state_root = root / ".hex-cortex"
    active_path = active_registry_path or state_root / "world-model" / "registry" / "active.json"
    active_model = audit_active_world_model(active_path)
    policy_v2 = audit_screen_lab_policy_v2(state_root)
    receipts = list(_iter_receipts(state_root))
    self_correction = audit_self_correction_evidence(receipts)
    remote_api = audit_remote_api_evidence(receipts)
    security = audit_security_evidence(root, receipts)

    facts = dict(filesystem.get("runtime_facts", {}))
    facts.update(_boolean_mapping(runtime.get("runtime_facts")))
    facts.update(
        {
            "media_runtime_available": media.get("healthy") is True,
            "comfyui_endpoint_configured": media.get("healthy") is True,
            "frozen_encoder_runtime_available": encoder.get("runtime_ready") is True,
            "dinov2_model_cached": cache_present,
            "web_search_adapter_configured": research.get("operational_ready") is True,
            "compact_world_model_candidate_available": policy_v2["candidate_found"],
            "active_compact_world_model_available": active_model["active_model_ready"],
            "learned_world_model_available": active_model["active_model_ready"],
            "hermes_adapter_available": _hermes_runtime_available(root),
            "private_or_tunneled_transport_available": _private_transport_certified(state_root),
        }
    )
    facts.update(overrides)

    wiring = audit_cortex_wiring(build_cortex_bundle(), runtime_facts=facts)
    category_blockers = _category_blockers(
        facts=facts,
        wiring=wiring,
        policy_v2=policy_v2,
        self_correction=self_correction,
        remote_api=remote_api,
        security=security,
    )
    categories = {
        name: not blockers
        for name, blockers in category_blockers.items()
    }
    branch_ready = all(
        categories[name]
        for name in (
            "code_ready",
            "runtime_ready",
            "models_ready",
            "research_ready",
            "media_ready",
            "world_model_ready",
            "policy_v2_ready",
            "self_correction_ready",
            "remote_api_ready",
            "security_ready",
        )
    )
    operational_ready = branch_ready and categories["server_ready"]

    payload: dict[str, object] = {
        "audit_type": "hex_cortex_operational_truth_v1",
        "project_root": str(root),
        **categories,
        "branch_ready": branch_ready,
        "operational_ready": operational_ready,
        "runtime_facts": facts,
        "category_blockers": category_blockers,
        "wiring": wiring,
        "filesystem_probe": filesystem,
        "runtime_models": runtime,
        "media_probe": media,
        "encoder_probe": encoder,
        "research_probe": research,
        "active_world_model": active_model,
        "screen_lab_policy_v2": policy_v2,
        "self_correction": self_correction,
        "remote_api": remote_api,
        "security": security,
        "network_call_performed": execute_network,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "next_action": _next_action(category_blockers),
    }
    payload["audit_hash"] = _stable_hash(payload)
    return payload


def write_operational_audit_receipt(path: Path, payload: dict[str, object]) -> dict[str, object]:
    if payload.get("audit_type") != "hex_cortex_operational_truth_v1":
        raise ValueError("operational audit payload type invalid")
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return {
        "receipt_type": "operational_truth_write_v1",
        "written": True,
        "path": str(target),
        "audit_hash": payload.get("audit_hash"),
        "raw_secret_persisted": False,
    }


def detect_huggingface_model_cache(model_ref: str) -> bool:
    if not model_ref.strip() or "/" not in model_ref:
        return False
    cache_name = "models--" + model_ref.replace("/", "--")
    roots: list[Path] = []
    explicit_hub = os.environ.get("HF_HUB_CACHE")
    transformers_cache = os.environ.get("TRANSFORMERS_CACHE")
    hf_home = os.environ.get("HF_HOME")
    if explicit_hub:
        roots.append(Path(explicit_hub))
    if transformers_cache:
        roots.append(Path(transformers_cache))
    if hf_home:
        roots.append(Path(hf_home) / "hub")
    roots.extend(
        [
            Path.home() / ".cache" / "huggingface" / "hub",
            Path.home() / "AppData" / "Local" / "huggingface" / "hub",
        ]
    )
    for root in roots:
        snapshots = root.expanduser() / cache_name / "snapshots"
        try:
            if snapshots.is_dir() and any(child.is_dir() for child in snapshots.iterdir()):
                return True
        except OSError:
            continue
    return False


def audit_active_world_model(active_registry_path: Path) -> dict[str, object]:
    active_path = active_registry_path.resolve()
    blockers: list[str] = []
    try:
        active = json.loads(active_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        active = {}
        blockers.append("active_registry_missing_or_invalid")
    if active and active.get("registry_type") != "active_compact_world_model_v1":
        blockers.append("active_registry_type_invalid")
    root = active_path.parent
    candidate_name = active.get("candidate_file") if isinstance(active, dict) else None
    weights_name = active.get("weights_file") if isinstance(active, dict) else None
    if not _safe_filename(candidate_name):
        blockers.append("active_candidate_filename_invalid")
    if not _safe_filename(weights_name):
        blockers.append("active_weights_filename_invalid")
    candidate_path = root / str(candidate_name) if _safe_filename(candidate_name) else None
    weights_path = root / str(weights_name) if _safe_filename(weights_name) else None
    if candidate_path is not None and not candidate_path.is_file():
        blockers.append("active_candidate_missing")
    if weights_path is not None:
        if not weights_path.is_file():
            blockers.append("active_weights_missing")
        elif _file_hash(weights_path) != active.get("weights_hash"):
            blockers.append("active_weights_hash_mismatch")
    ready = not blockers
    return {
        "audit_type": "active_world_model_runtime_audit_v1",
        "active_registry_path": str(active_path),
        "active_model_ready": ready,
        "candidate_hash": active.get("candidate_hash") if isinstance(active, dict) else None,
        "weights_hash": active.get("weights_hash") if isinstance(active, dict) else None,
        "blockers": sorted(set(blockers)),
        "next_action": "operate_active_world_model" if ready else "promote_or_repair_world_model",
    }


def audit_screen_lab_policy_v2(state_root: Path) -> dict[str, object]:
    candidates: list[tuple[Path, dict[str, object]]] = []
    if state_root.is_dir():
        for path in sorted(state_root.rglob("candidate.json"))[:_MAX_RECEIPT_FILES]:
            payload = _read_json_object(path)
            if payload.get("candidate_type") == "action_discriminative_world_model_candidate_v2":
                candidates.append((path, payload))
    if not candidates:
        return {
            "audit_type": "screen_lab_policy_v2_gate_audit",
            "candidate_found": False,
            "heldout_evaluated": False,
            "policy_gate_passed": False,
            "promotion_allowed": False,
            "clean_rejection": False,
            "blockers": ["screen_lab_policy_v2_candidate_missing"],
            "next_action": "train_screen_lab_policy_v2",
        }
    path, candidate = candidates[-1]
    promotion_allowed = candidate.get("promotion_allowed") is True
    promotion_blockers = candidate.get("promotion_blockers")
    blockers_list = promotion_blockers if isinstance(promotion_blockers, list) else []
    policy_value = candidate.get("policy_gate_passed")
    evaluated = isinstance(policy_value, bool) and isinstance(candidate.get("promotion_allowed"), bool)
    clean_rejection = evaluated and not promotion_allowed and bool(blockers_list)
    ready = evaluated and (promotion_allowed or clean_rejection)
    return {
        "audit_type": "screen_lab_policy_v2_gate_audit",
        "candidate_found": True,
        "candidate_path": str(path),
        "candidate_hash": candidate.get("candidate_hash"),
        "heldout_evaluated": evaluated,
        "policy_gate_passed": policy_value is True,
        "promotion_allowed": promotion_allowed,
        "clean_rejection": clean_rejection,
        "gate_ready": ready,
        "metrics": candidate.get("metrics") if isinstance(candidate.get("metrics"), dict) else {},
        "blockers": [] if ready else ["screen_lab_policy_v2_gate_not_evaluated"],
        "promotion_blockers": blockers_list,
        "next_action": "review_policy_candidate" if ready else "train_screen_lab_policy_v2",
    }


def audit_self_correction_evidence(receipts: Iterable[dict[str, object]]) -> dict[str, object]:
    rows = list(receipts)
    worktree = any(row.get("receipt_type") == "isolated_worktree_create_v1" and row.get("status") == "created" for row in rows)
    patch = any(row.get("receipt_type") == "reviewable_patch_apply_v1" and row.get("status") == "applied" for row in rows)
    checks = any(row.get("receipt_type") == "allowlisted_check_run_v1" and row.get("status") == "passed" for row in rows)
    evaluation = any(row.get("evaluation_type") == "self_correction_candidate_evaluation_v1" and row.get("status") in {"promotable", "rejected"} for row in rows)
    ready = worktree and patch and checks and evaluation
    return {
        "audit_type": "self_correction_field_certification_v1",
        "worktree_created": worktree,
        "patch_hash_verified_and_applied": patch,
        "allowlisted_checks_completed": checks,
        "candidate_evaluated": evaluation,
        "field_certified": ready,
        "blockers": [name for name, value in (
            ("isolated_worktree_evidence_missing", worktree),
            ("reviewable_patch_evidence_missing", patch),
            ("allowlisted_check_evidence_missing", checks),
            ("candidate_evaluation_evidence_missing", evaluation),
        ) if not value],
        "next_action": "retain_field_certificate" if ready else "run_self_correction_field_cycle",
    }


def audit_remote_api_evidence(receipts: Iterable[dict[str, object]]) -> dict[str, object]:
    completed = any(
        row.get("receipt_type") == "coding_model_execution_v1"
        and row.get("provider_id") == "remote_api"
        and row.get("status") == "completed"
        and row.get("model_call_performed") is True
        and row.get("raw_secret_persisted") is False
        and row.get("raw_response_persisted") is False
        for row in receipts
    )
    return {
        "audit_type": "remote_api_smoke_audit_v1",
        "remote_api_smoke_ready": completed,
        "blockers": [] if completed else ["remote_api_smoke_receipt_missing"],
        "next_action": "retain_remote_api_smoke_receipt" if completed else "run_bounded_remote_api_smoke",
    }


def audit_security_evidence(
    project_root: Path,
    receipts: Iterable[dict[str, object]],
) -> dict[str, object]:
    gitignore = _read_text(project_root / ".gitignore")
    env_ignored = any(line.strip() in {".env", "*.env", "**/.env"} for line in gitignore.splitlines())
    secret_scan_configured = any(
        (project_root / path).is_file()
        for path in (".gitleaks.toml", ".github/workflows/secret-scan.yml", ".github/workflows/secrets.yml")
    )
    n8n_rotated = any(
        row.get("receipt_type") == "secret_rotation_v1"
        and row.get("secret_id") == "n8n"
        and row.get("status") == "rotated"
        for row in receipts
    )
    contract_ready = env_ignored
    ready = contract_ready and secret_scan_configured and n8n_rotated
    blockers = []
    if not env_ignored:
        blockers.append("env_ignore_policy_missing")
    if not secret_scan_configured:
        blockers.append("ci_secret_detection_missing")
    if not n8n_rotated:
        blockers.append("n8n_secret_rotation_not_certified")
    return {
        "audit_type": "security_operational_audit_v1",
        "env_ignore_policy_ready": env_ignored,
        "secret_scan_configured": secret_scan_configured,
        "n8n_secret_rotation_certified": n8n_rotated,
        "security_contract_ready": contract_ready,
        "security_operational_ready": ready,
        "blockers": blockers,
        "next_action": "retain_security_certificate" if ready else "close_security_blockers",
    }


def _probe_media(*, endpoint: str, execute_network: bool) -> dict[str, object]:
    if not execute_network:
        return {
            "receipt_type": "comfyui_operational_probe_v1",
            "healthy": False,
            "network_call_performed": False,
            "blockers": ["live_media_probe_not_performed"],
        }
    return probe_comfyui(endpoint, timeout_seconds=1.0)


def _probe_research(*, endpoint: str, query: str, execute_network: bool) -> dict[str, object]:
    if not execute_network:
        return {
            "audit_type": "searxng_live_citation_audit_v1",
            "status": "blocked",
            "operational_ready": False,
            "network_call_performed": False,
            "blockers": ["live_network_search_not_performed"],
        }
    searcher = build_searxng_searcher(endpoint=endpoint, timeout_seconds=3.0)
    return audit_searxng_runtime(searcher(query))


def _category_blockers(
    *,
    facts: dict[str, bool],
    wiring: dict[str, object],
    policy_v2: dict[str, object],
    self_correction: dict[str, object],
    remote_api: dict[str, object],
    security: dict[str, object],
) -> dict[str, list[str]]:
    return {
        "code_ready": _missing(
            (wiring.get("architecture_ready") is True, "architecture_wiring_not_ready"),
            (facts.get("cli_entrypoint_available") is True, "cli_entrypoint_missing"),
            (facts.get("mcp_server_available") is True, "mcp_server_missing"),
        ),
        "runtime_ready": _missing(
            (facts.get("local_model_runtime_available") is True, "local_model_runtime_not_available"),
            (facts.get("mcp_server_available") is True, "mcp_server_not_available"),
            (facts.get("claude_project_configured") is True, "claude_project_not_configured"),
            (facts.get("claude_runtime_available") is True, "claude_runtime_not_available"),
        ),
        "models_ready": _missing(
            (facts.get("local_model_runtime_available") is True, "local_model_runtime_not_available"),
            (facts.get("frozen_encoder_runtime_available") is True, "frozen_encoder_runtime_not_available"),
            (facts.get("dinov2_model_cached") is True, "dinov2_model_not_cached"),
        ),
        "research_ready": _missing(
            (facts.get("web_search_adapter_configured") is True, "searxng_live_citations_not_ready"),
        ),
        "media_ready": _missing(
            (facts.get("media_runtime_available") is True, "comfyui_runtime_not_ready"),
        ),
        "world_model_ready": _missing(
            (facts.get("learned_world_model_available") is True, "active_world_model_not_ready"),
        ),
        "policy_v2_ready": _missing(
            (policy_v2.get("heldout_evaluated") is True, "policy_v2_heldout_not_evaluated"),
            (
                policy_v2.get("promotion_allowed") is True or policy_v2.get("clean_rejection") is True,
                "policy_v2_result_not_reviewable",
            ),
        ),
        "self_correction_ready": _missing(
            (self_correction.get("field_certified") is True, "self_correction_not_field_certified"),
        ),
        "remote_api_ready": _missing(
            (remote_api.get("remote_api_smoke_ready") is True, "remote_api_smoke_not_ready"),
        ),
        "server_ready": _missing(
            (facts.get("service_packaging_available") is True, "server_packaging_not_ready"),
            (facts.get("private_or_tunneled_transport_available") is True, "private_transport_not_ready"),
            (facts.get("hermes_adapter_available") is True, "hermes_runtime_not_ready"),
        ),
        "security_ready": _missing(
            (security.get("security_operational_ready") is True, "security_operational_evidence_not_ready"),
        ),
    }


def _next_action(category_blockers: dict[str, list[str]]) -> str:
    order = (
        ("research_ready", "run_searxng_live_citation_audit"),
        ("policy_v2_ready", "train_and_evaluate_screen_lab_policy_v2"),
        ("media_ready", "start_or_repair_comfyui"),
        ("runtime_ready", "repair_runtime_truth"),
        ("self_correction_ready", "run_self_correction_field_cycle"),
        ("remote_api_ready", "run_bounded_remote_api_smoke"),
        ("security_ready", "close_security_blockers"),
        ("server_ready", "deploy_server_federation"),
    )
    for category, action in order:
        if category_blockers[category]:
            return action
    return "operate_hex_cortex"


def _iter_receipts(state_root: Path) -> Iterable[dict[str, object]]:
    if not state_root.is_dir():
        return
    seen = 0
    for path in sorted(state_root.rglob("*")):
        if seen >= _MAX_RECEIPT_FILES:
            return
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            if path.stat().st_size > _MAX_RECEIPT_BYTES:
                continue
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            continue
        seen += 1
        for raw in lines:
            if not raw.strip():
                continue
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                yield payload


def _hermes_runtime_available(project_root: Path) -> bool:
    configured = (project_root / "deploy" / "server" / "hermes-hex-cortex-mcp.yaml").is_file()
    return configured and shutil.which("hermes") is not None


def _private_transport_certified(state_root: Path) -> bool:
    receipt = _read_json_object(state_root / "server" / "transport-certificate.json")
    return receipt.get("private_or_tunneled_transport_available") is True


def _boolean_mapping(value: object) -> dict[str, bool]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): item
        for key, item in value.items()
        if isinstance(key, str) and isinstance(item, bool)
    }


def _validate_boolean_facts(value: dict[str, bool]) -> dict[str, bool]:
    if not all(isinstance(key, str) and isinstance(item, bool) for key, item in value.items()):
        raise ValueError("runtime fact overrides must be boolean values")
    return dict(value)


def _missing(*checks: tuple[bool, str]) -> list[str]:
    return [blocker for ready, blocker in checks if not ready]


def _safe_filename(value: object) -> bool:
    return isinstance(value, str) and bool(value) and Path(value).name == value


def _read_json_object(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
