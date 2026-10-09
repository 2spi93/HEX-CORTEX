from __future__ import annotations

import pytest

from hex_cortex.memory.cortex_gtixt_offline_bridge import (
    READ_ONLY_CAPABILITIES,
    inspect_gtixt_snapshot,
)


def _snapshot() -> dict[str, object]:
    return {
        "project_id": "GTIXT",
        "snapshot_version": 1,
        "capabilities": {
            "health": {"status": "unknown", "checked_at": "manual export"},
        },
    }


def test_only_seven_categories_approved() -> None:
    assert len(READ_ONLY_CAPABILITIES) == 7
    with pytest.raises(ValueError, match="unsupported"):
        inspect_gtixt_snapshot(_snapshot(), capability="modify_scoring", explicitly_approved=True)


def test_snapshot_needs_operator_approval() -> None:
    with pytest.raises(PermissionError):
        inspect_gtixt_snapshot(_snapshot(), capability="health")


def test_offline_inspection_is_pure_and_has_receipt() -> None:
    snapshot = _snapshot()
    result = inspect_gtixt_snapshot(
        snapshot, capability="health", explicitly_approved=True
    )
    assert result["project_id"] == "GTIXT"
    assert result["read_only"] is True
    assert result["memory_imported"] is False
    assert result["network_call_performed"] is False
    assert result["mutation_performed"] is False
    assert result["snapshot_sha256"]
    assert snapshot == _snapshot()


def test_forged_project_and_credentials_are_rejected() -> None:
    snapshot = _snapshot()
    snapshot["project_id"] = "other"
    with pytest.raises(ValueError, match="provenance"):
        inspect_gtixt_snapshot(snapshot, capability="health", explicitly_approved=True)
    snapshot = _snapshot()
    snapshot["capabilities"]["health"]["password"] = "secret"
    with pytest.raises(ValueError, match="credential"):
        inspect_gtixt_snapshot(snapshot, capability="health", explicitly_approved=True)


def test_unallowlisted_fields_rejected() -> None:
    snapshot = _snapshot()
    snapshot["database_url"] = "not allowed"
    with pytest.raises(ValueError, match="unallowlisted"):
        inspect_gtixt_snapshot(snapshot, capability="health", explicitly_approved=True)
