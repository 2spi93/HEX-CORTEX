from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

CORTEX_TRANSITION_FILENAME = "cortex-transition.jsonl"


def build_cortex_transition(
    profile: Path,
    *,
    current_state: dict[str, object],
    action_context: dict[str, object],
    horizon_steps: int = 1,
) -> dict[str, object]:
    blockers = _blockers(current_state, action_context, horizon_steps)
    allowed = not blockers
    current_capabilities = _string_list(current_state.get("capabilities"))
    expected_capabilities = _string_list(
        action_context.get("expected_capabilities")
    )
    predicted_capabilities = sorted(
        set(current_capabilities).union(expected_capabilities)
    )
    current_confidence = _number(
        current_state.get("average_confidence"),
        default=0.0,
    )
    confidence_delta = _number(
        action_context.get("confidence_delta"),
        default=0.0,
    )
    predicted_confidence = round(
        min(1.0, max(0.0, current_confidence + confidence_delta)),
        4,
    )
    action_id = _text(action_context.get("action_id"))
    context_hash = _stable_hash(action_context)
    predicted_state_hash = _hash(
        str(profile),
        str(current_state.get("state_hash")),
        context_hash,
        str(horizon_steps),
        *predicted_capabilities,
        str(predicted_confidence),
        *blockers,
    )
    transition_hash = _hash(
        str(current_state.get("state_hash")),
        context_hash,
        predicted_state_hash,
        *blockers,
    )
    record = {
        "transition_id": f"cortex_transition_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "profile_path": str(profile),
        "transition_status": "ready" if allowed else "blocked",
        "transition_allowed": allowed,
        "transition_basis": "deterministic_contract_v1",
        "source_state_hash": current_state.get("state_hash"),
        "action_id": action_id,
        "action_context_hash": context_hash,
        "horizon_steps": horizon_steps,
        "predicted_capabilities": predicted_capabilities,
        "predicted_average_confidence": predicted_confidence,
        "predicted_state_hash": predicted_state_hash,
        "model_call_performed": False,
        "network_call_performed": False,
        "raw_state_persisted": False,
        "next_action": (
            "compare_observed_state"
            if allowed
            else "repair_transition_prediction"
        ),
        "blockers": blockers,
        "transition_hash": transition_hash,
    }
    path = profile / CORTEX_TRANSITION_FILENAME
    rows = _load(path)
    if not any(row.get("transition_hash") == transition_hash for row in rows):
        rows.append(record)
    _write(path, rows)
    return {
        "transition_type": "cortex_transition_prediction",
        "transition_path": str(path),
        "transition_count": len(rows),
        "transition_records": [record],
    }


def summarize_cortex_transitions(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "cortex_transition_prediction",
        "path": str(path),
        "exists": path.exists(),
        "total_transition_count": len(rows),
        "latest_transition_allowed": (
            latest.get("transition_allowed") if latest else None
        ),
        "latest_action_id": latest.get("action_id") if latest else None,
        "latest_horizon_steps": (
            latest.get("horizon_steps") if latest else None
        ),
        "latest_next_action": (
            latest.get("next_action") if latest else None
        ),
    }


def _blockers(
    current_state: dict[str, object],
    action_context: dict[str, object],
    horizon_steps: int,
) -> list[str]:
    blockers = []
    if current_state.get("state_allowed") is not True:
        blockers.append("current_state_not_allowed")
    if not _text(current_state.get("state_hash")):
        blockers.append("missing_source_state_hash")
    if not _text(action_context.get("action_id")):
        blockers.append("missing_action_id")
    if horizon_steps < 1 or horizon_steps > 32:
        blockers.append("horizon_steps_out_of_range")
    confidence_delta = action_context.get("confidence_delta", 0.0)
    if not isinstance(confidence_delta, int | float):
        blockers.append("confidence_delta_not_numeric")
    expected = action_context.get("expected_capabilities", [])
    if not isinstance(expected, list) or not all(
        isinstance(item, str) for item in expected
    ):
        blockers.append("expected_capabilities_invalid")
    return blockers


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _number(value: object, *, default: float) -> float:
    return float(value) if isinstance(value, int | float) else default


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _stable_hash(payload: dict[str, object]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()


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
    text = "".join(
        json.dumps(row, sort_keys=True) + "\n"
        for row in rows
    )
    path.write_text(text, encoding="utf-8")


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
