"""Optional offline GTIXT -> HEX-CORTEX evidence bridge (read-only).

This intentionally does not discover GTIXT accounts, GitHub repositories,
databases, credentials, or network routes. A human supplies an explicitly
exported, non-sensitive snapshot, which is validated against a strict view.
No GTIXT object is changed or incorporated into the HEX cognitive memory.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

READ_ONLY_CAPABILITIES = (
    "health",
    "runtime_summary",
    "blockers",
    "latest_artifacts",
    "evidence_coverage",
    "open_tasks",
    "capability_map",
)


_SENSITIVE_KEY_FRAGMENTS = (
    "token", "apikey", "accesstoken", "refreshtoken", "password", "passwd",
    "secret", "credential", "privatekey", "authorization", "bearer",
    "sessioncookie", "clientsecret",
)


def _validate_export_tree(value: object, *, depth: int = 0, nodes: list[int] | None = None) -> None:
    """Fail closed on nested secrets, deeply recursive or non-JSON exports."""
    if nodes is None:
        nodes = [0]
    nodes[0] += 1
    if depth > 8 or nodes[0] > 256:
        raise ValueError("GTIXT snapshot structure budget exceeded")
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 128:
                raise ValueError("GTIXT snapshot invalid key")
            compact = "".join(char for char in key.casefold() if char.isalnum())
            if any(fragment in compact for fragment in _SENSITIVE_KEY_FRAGMENTS):
                raise ValueError("credential-like key rejected")
            _validate_export_tree(item, depth=depth + 1, nodes=nodes)
    elif isinstance(value, list):
        for item in value:
            _validate_export_tree(item, depth=depth + 1, nodes=nodes)
    elif value is not None and not isinstance(value, str | int | float | bool):
        raise ValueError("GTIXT snapshot contains unsupported value")


def inspect_gtixt_snapshot(
    snapshot: Mapping[str, object],
    *,
    capability: str,
    explicitly_approved: bool = False,
) -> dict[str, object]:
    if capability not in READ_ONLY_CAPABILITIES:
        raise ValueError("unsupported read-only GTIXT capability")
    if not explicitly_approved:
        raise PermissionError("explicit GTIXT snapshot read approval required")
    if snapshot.get("project_id") != "GTIXT":
        raise ValueError("GTIXT project provenance required")
    if set(snapshot) - {"project_id", "snapshot_version", "capabilities"}:
        raise ValueError("snapshot contains unallowlisted fields")
    if snapshot.get("snapshot_version") != 1:
        raise ValueError("unsupported snapshot schema version")
    capabilities = snapshot.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("missing capability map")
    if set(capabilities) - set(READ_ONLY_CAPABILITIES):
        raise ValueError("snapshot contains unapproved capability categories")
    details = capabilities.get(capability)
    if not isinstance(details, dict):
        raise ValueError("requested capability missing or malformed")
    # Deep scan the entire declared export, not just the requested category.
    # Nested arrays and objects must not bypass the project boundary.
    _validate_export_tree(capabilities)
    body = json.dumps(details, sort_keys=True, allow_nan=False)
    if len(body.encode("utf-8")) > 8_192:
        raise ValueError("snapshot exceeds read-only data budget")
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return {
        "project_id": "GTIXT",
        "capability": capability,
        "read_only": True,
        "snapshot_sha256": digest,
        "payload": json.loads(body),
        "memory_imported": False,
        "network_call_performed": False,
        "mutation_performed": False,
    }
