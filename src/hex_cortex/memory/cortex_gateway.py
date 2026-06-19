from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from uuid import uuid4

from hex_cortex.memory.cortex_policy import CortexMode

CORTEX_GATEWAY_FILENAME = "cortex-gateway.jsonl"
AdapterHandler = Callable[[dict[str, object]], dict[str, object]]


@dataclass(frozen=True)
class CortexAdapter:
    name: str
    lane: str
    handler: AdapterHandler
    description: str
    requires_operator: bool = False
    network_capable: bool = False
    local_process_capable: bool = False
    auto_safe_capable: bool = False
    timeout_seconds: float = 8.0


def build_cortex_adapter_registry(
    *adapters: CortexAdapter,
) -> dict[str, CortexAdapter]:
    registry: dict[str, CortexAdapter] = {}
    for adapter in adapters:
        if not adapter.name.strip():
            raise ValueError("adapter name must be non-empty")
        if adapter.name in registry:
            raise ValueError(f"duplicate adapter: {adapter.name}")
        if adapter.timeout_seconds <= 0 or adapter.timeout_seconds > 30:
            raise ValueError("adapter timeout_seconds must be in (0, 30]")
        registry[adapter.name] = adapter
    return registry


def list_cortex_adapters(
    adapter_registry: dict[str, CortexAdapter],
) -> list[dict[str, object]]:
    return [
        {
            "name": adapter.name,
            "lane": adapter.lane,
            "description": adapter.description,
            "requires_operator": adapter.requires_operator,
            "network_capable": adapter.network_capable,
            "local_process_capable": adapter.local_process_capable,
            "auto_safe_capable": adapter.auto_safe_capable,
            "timeout_seconds": adapter.timeout_seconds,
            "handler_exposed": False,
        }
        for adapter in sorted(adapter_registry.values(), key=lambda item: item.name)
    ]


def run_cortex_adapter_gateway(
    profile: Path,
    *,
    route_record: dict[str, object],
    adapter_receipt: dict[str, object],
    adapter_name: str,
    adapter_registry: dict[str, CortexAdapter],
    request: dict[str, object],
    execution_mode: str = "dry_run",
    policy_mode: CortexMode = CortexMode.MANUAL,
    operator_approved: bool = False,
    trusted_plan: bool = False,
    network_allowed: bool = False,
    local_process_allowed: bool = False,
    secret_refs: dict[str, str] | None = None,
    idempotency_key: str | None = None,
) -> dict[str, object]:
    adapter = adapter_registry.get(adapter_name)
    request_hash = _stable_hash(request)
    receipt_hash = _receipt_hash(adapter_receipt)
    secret_names = sorted((secret_refs or {}).keys())
    blockers = _gateway_blockers(
        route_record=route_record,
        adapter_receipt=adapter_receipt,
        adapter=adapter,
        adapter_name=adapter_name,
        execution_mode=execution_mode,
        policy_mode=policy_mode,
        operator_approved=operator_approved,
        trusted_plan=trusted_plan,
        network_allowed=network_allowed,
        local_process_allowed=local_process_allowed,
        idempotency_key=idempotency_key,
    )
    allowed = not blockers
    gateway_hash = _hash(
        str(profile),
        str(route_record.get("route_hash")),
        receipt_hash,
        adapter_name,
        request_hash,
        execution_mode,
        policy_mode.value,
        str(operator_approved),
        str(trusted_plan),
        str(network_allowed),
        str(local_process_allowed),
        str(idempotency_key),
        *secret_names,
        *blockers,
    )
    path = profile / CORTEX_GATEWAY_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("gateway_hash") == gateway_hash),
        None,
    )
    if existing is not None:
        return {
            "gateway_type": "cortex_adapter_gateway",
            "gateway_path": str(path),
            "gateway_count": len(rows),
            "gateway_records": [existing],
        }

    started_at = monotonic()
    observed: dict[str, object] = {}
    handler_error: str | None = None
    execution_performed = False
    if allowed and execution_mode == "execute" and adapter is not None:
        execution_performed = True
        try:
            observed = adapter.handler(dict(request))
            if not isinstance(observed, dict):
                observed = {"status": "blocked", "summary": "adapter returned non-dict"}
                handler_error = "adapter_result_not_dict"
        except Exception as exc:  # noqa: BLE001 - receipt captures adapter failure.
            handler_error = type(exc).__name__
            observed = {"status": "blocked", "summary": "adapter raised"}
    elapsed_ms = round((monotonic() - started_at) * 1000, 3)
    observed_hash = _stable_hash(observed) if observed else None
    result_summary = _summarize_result(observed, handler_error)
    completed = (
        execution_performed
        and handler_error is None
        and result_summary.get("status") not in {"blocked", "error"}
    )
    record = {
        "gateway_id": f"cortex_gateway_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "gateway_status": "ready" if allowed else "blocked",
        "gateway_allowed": allowed,
        "execution_mode": execution_mode,
        "policy_mode": policy_mode.value,
        "route_hash": route_record.get("route_hash"),
        "adapter_receipt_hash": receipt_hash,
        "adapter_name": adapter_name,
        "adapter_lane": adapter.lane if adapter else None,
        "request_hash": request_hash,
        "idempotency_key_hash": (
            _hash(idempotency_key) if idempotency_key else None
        ),
        "secret_ref_names": secret_names,
        "secret_values_persisted": False,
        "raw_request_persisted": False,
        "raw_result_persisted": False,
        "operator_approved": operator_approved,
        "trusted_plan": trusted_plan,
        "network_allowed": network_allowed,
        "local_process_allowed": local_process_allowed,
        "execution_performed": execution_performed,
        "execution_completed": completed,
        "network_call_performed": (
            bool(observed.get("network_call_performed")) if observed else False
        ),
        "local_process_started": (
            bool(observed.get("local_process_started")) if observed else False
        ),
        "external_effect_performed": (
            bool(observed.get("external_effect_performed")) if observed else False
        ),
        "elapsed_ms": elapsed_ms,
        "timeout_seconds": adapter.timeout_seconds if adapter else None,
        "result_summary": result_summary,
        "observed_hash": observed_hash,
        "next_action": _next_action(
            allowed=allowed,
            execution_mode=execution_mode,
            completed=completed,
            handler_error=handler_error,
        ),
        "blockers": blockers,
        "gateway_hash": gateway_hash,
    }
    rows.append(record)
    _write(path, rows)
    return {
        "gateway_type": "cortex_adapter_gateway",
        "gateway_path": str(path),
        "gateway_count": len(rows),
        "gateway_records": [record],
    }


def summarize_cortex_gateway(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_adapter_gateway",
        "path": str(path),
        "exists": path.exists(),
        "total_gateway_count": len(rows),
        "latest_gateway_allowed": (
            latest.get("gateway_allowed") if latest else None
        ),
        "latest_adapter_name": latest.get("adapter_name") if latest else None,
        "latest_execution_performed": (
            latest.get("execution_performed") if latest else None
        ),
        "latest_execution_completed": (
            latest.get("execution_completed") if latest else None
        ),
        "latest_next_action": latest.get("next_action") if latest else None,
    }


def _gateway_blockers(
    *,
    route_record: dict[str, object],
    adapter_receipt: dict[str, object],
    adapter: CortexAdapter | None,
    adapter_name: str,
    execution_mode: str,
    policy_mode: CortexMode,
    operator_approved: bool,
    trusted_plan: bool,
    network_allowed: bool,
    local_process_allowed: bool,
    idempotency_key: str | None,
) -> list[str]:
    blockers = []
    if route_record.get("route_allowed") is not True:
        blockers.append("route_not_allowed")
    route_lane = route_record.get("lane")
    if not isinstance(route_lane, str):
        blockers.append("route_lane_missing")
    if not _receipt_allowed(adapter_receipt):
        blockers.append("adapter_receipt_not_allowed")
    if adapter is None:
        blockers.append("adapter_not_registered")
    elif isinstance(route_lane, str) and adapter.lane != route_lane:
        blockers.append("adapter_lane_mismatch")
    if execution_mode not in {"dry_run", "execute"}:
        blockers.append("execution_mode_invalid")
    if not adapter_name.strip():
        blockers.append("adapter_name_missing")
    if idempotency_key is not None and not idempotency_key.strip():
        blockers.append("idempotency_key_invalid")
    if execution_mode == "execute" and adapter is not None:
        if policy_mode is CortexMode.MANUAL and not operator_approved:
            blockers.append("manual_execution_requires_operator")
        if policy_mode is CortexMode.ASSISTED:
            if adapter.requires_operator:
                blockers.append("assisted_blocks_operator_adapter")
            if adapter.network_capable or adapter.local_process_capable:
                blockers.append("assisted_blocks_effect_adapter")
        if policy_mode is CortexMode.AUTO_SAFE:
            if not trusted_plan:
                blockers.append("auto_safe_requires_trusted_plan")
            if not adapter.auto_safe_capable:
                blockers.append("adapter_not_auto_safe_capable")
        if adapter.requires_operator and not (operator_approved or trusted_plan):
            blockers.append("adapter_requires_operator_or_trusted_plan")
        if adapter.network_capable and not network_allowed:
            blockers.append("network_permission_required")
        if adapter.local_process_capable and not local_process_allowed:
            blockers.append("local_process_permission_required")
    return blockers


def _receipt_allowed(receipt: dict[str, object]) -> bool:
    allowed_keys = (
        "media_receipt_allowed",
        "account_allowed",
        "lane_allowed",
        "encode_allowed",
        "b_allowed",
        "c_allowed",
    )
    return any(receipt.get(key) is True for key in allowed_keys)


def _receipt_hash(receipt: dict[str, object]) -> str:
    hash_keys = (
        "media_receipt_hash",
        "account_receipt_hash",
        "lane_receipt_hash",
        "encode_receipt_hash",
        "b_hash",
        "c_hash",
    )
    for key in hash_keys:
        value = receipt.get(key)
        if isinstance(value, str) and value:
            return value
    return _stable_hash(receipt)


def _summarize_result(
    observed: dict[str, object],
    handler_error: str | None,
) -> dict[str, object]:
    if handler_error:
        return {
            "status": "blocked",
            "error_type": handler_error,
            "schema_keys": sorted(str(key) for key in observed),
        }
    if not observed:
        return {"status": "not_run", "schema_keys": []}
    status = observed.get("status")
    summary = observed.get("summary")
    return {
        "status": status if isinstance(status, str) else "ok",
        "summary_length": len(summary) if isinstance(summary, str) else 0,
        "schema_keys": sorted(str(key) for key in observed),
    }


def _next_action(
    *,
    allowed: bool,
    execution_mode: str,
    completed: bool,
    handler_error: str | None,
) -> str:
    if not allowed:
        return "repair_gateway_contract"
    if execution_mode == "dry_run":
        return "execute_registered_adapter"
    if handler_error or not completed:
        return "repair_adapter_execution"
    return "inspect_gateway_result"


def _load(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(content, encoding="utf-8")


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
