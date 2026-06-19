from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

WORLD_MODEL_REVIEW_FILENAME = "cortex-world-model-review.jsonl"


def append_world_model_review(
    profile: Path,
    *,
    comparison: dict[str, object],
    baseline_receipt_hash: str,
    candidate_receipt_hash: str,
) -> dict[str, object]:
    if comparison.get("comparison_complete") is not True:
        raise ValueError("comparison must be complete")
    if not baseline_receipt_hash or not candidate_receipt_hash:
        raise ValueError("run receipt hashes are required")
    record = {
        "review_id": f"wm_review_{uuid4().hex}",
        "created_at": datetime.now(UTC).isoformat(),
        "comparison_hash": comparison.get("comparison_hash"),
        "baseline_receipt_hash": baseline_receipt_hash,
        "candidate_receipt_hash": candidate_receipt_hash,
        "accepted_for_review": comparison.get("accepted_for_review"),
        "weighted_gain": comparison.get("weighted_gain"),
        "critical_regressions": comparison.get("critical_regressions"),
        "manual_review_required": True,
        "automatic_deployment_allowed": False,
        "rollback_checkpoint_required": True,
        "raw_metrics_persisted": False,
    }
    path = profile / WORLD_MODEL_REVIEW_FILENAME
    rows = _load(path)
    existing = next(
        (row for row in rows if row.get("comparison_hash") == record["comparison_hash"]),
        None,
    )
    if existing is None:
        rows.append(record)
        _write(path, rows)
        selected = record
    else:
        selected = existing
    return {
        "receipt_type": "world_model_review_receipt",
        "path": str(path),
        "receipt_count": len(rows),
        "receipt_records": [selected],
    }


def summarize_world_model_reviews(path: Path) -> dict[str, object]:
    rows = _load(path)
    latest = rows[-1] if rows else None
    return {
        "inspect_type": "world_model_review_receipt",
        "path": str(path),
        "exists": path.exists(),
        "total_review_count": len(rows),
        "latest_accepted_for_review": latest.get("accepted_for_review") if latest else None,
        "latest_weighted_gain": latest.get("weighted_gain") if latest else None,
        "latest_manual_review_required": latest.get("manual_review_required") if latest else None,
    }


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
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
