from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4


def append_research_hypothesis(
    path: Path,
    *,
    statement: str,
    baseline_ref: str,
    evaluator_ref: str,
    created_by: str,
    parent_id: str | None = None,
    budget_units: int = 1,
) -> dict[str, object]:
    for label, value in {
        "statement": statement,
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
        "created_by": created_by,
    }.items():
        if not value.strip():
            raise ValueError(f"{label} must be non-empty")
    if not 1 <= budget_units <= 1000:
        raise ValueError("budget_units out of range")
    rows = read_research_hypotheses(path)
    nodes = {
        str(row["hypothesis_id"]): row
        for row in rows
        if row.get("record_type") == "research_hypothesis_node_v1"
    }
    if parent_id is not None and parent_id not in nodes:
        raise ValueError("parent hypothesis not found")
    depth = 0 if parent_id is None else int(nodes[parent_id]["depth"]) + 1
    record = {
        "record_type": "research_hypothesis_node_v1",
        "hypothesis_id": f"hyp_{uuid4().hex}",
        "parent_id": parent_id,
        "depth": depth,
        "statement": statement,
        "statement_hash": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "baseline_ref": baseline_ref,
        "evaluator_ref": evaluator_ref,
        "created_by": created_by,
        "created_at": datetime.now(UTC).isoformat(),
        "status": "open",
        "budget_units": budget_units,
        "merge_allowed": False,
        "merge_performed": False,
    }
    record["node_hash"] = _stable_hash(record)
    _append_jsonl(path, record)
    return record


def append_research_outcome(
    path: Path,
    *,
    hypothesis_id: str,
    status: str,
    candidate_ref: str | None,
    metric_delta: float | None,
    heldout_passed: bool | None,
    insight_ref: str | None = None,
) -> dict[str, object]:
    if status not in {"running", "validated", "rejected", "pruned"}:
        raise ValueError("outcome status invalid")
    rows = read_research_hypotheses(path)
    nodes = {
        str(row["hypothesis_id"]): row
        for row in rows
        if row.get("record_type") == "research_hypothesis_node_v1"
    }
    node = nodes.get(hypothesis_id)
    if node is None:
        raise ValueError("hypothesis not found")
    merge_allowed = (
        status == "validated"
        and heldout_passed is True
        and isinstance(metric_delta, int | float)
        and float(metric_delta) > 0.0
    )
    outcome = {
        "record_type": "research_hypothesis_outcome_v1",
        "hypothesis_id": hypothesis_id,
        "parent_node_hash": node.get("node_hash"),
        "created_at": datetime.now(UTC).isoformat(),
        "status": status,
        "candidate_ref": candidate_ref,
        "metric_delta": metric_delta,
        "heldout_passed": heldout_passed,
        "insight_ref": insight_ref,
        "merge_allowed": merge_allowed,
        "merge_performed": False,
        "operator_merge_approval_required": True,
    }
    outcome["outcome_hash"] = _stable_hash(outcome)
    _append_jsonl(path, outcome)
    return outcome


def read_research_hypotheses(path: Path) -> list[dict[str, object]]:
    target = path.resolve()
    if not target.exists():
        return []
    rows = []
    for line_number, line in enumerate(target.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid research hypothesis JSONL at line {line_number}") from exc
        if not isinstance(payload, dict):
            raise ValueError(f"research hypothesis record at line {line_number} must be an object")
        rows.append(payload)
    return rows


def project_research_frontier(path: Path) -> dict[str, object]:
    rows = read_research_hypotheses(path)
    nodes = {
        str(row["hypothesis_id"]): dict(row)
        for row in rows
        if row.get("record_type") == "research_hypothesis_node_v1"
    }
    for row in rows:
        if row.get("record_type") != "research_hypothesis_outcome_v1":
            continue
        hypothesis_id = str(row.get("hypothesis_id"))
        if hypothesis_id in nodes:
            nodes[hypothesis_id].update(row)
    frontier = [node for node in nodes.values() if node.get("status") in {"open", "running"}]
    frontier.sort(
        key=lambda node: (
            int(node.get("depth", 0)),
            int(node.get("budget_units", 1)),
            str(node.get("created_at", "")),
        )
    )
    validated = [
        node
        for node in nodes.values()
        if node.get("status") == "validated"
        and node.get("heldout_passed") is True
        and isinstance(node.get("metric_delta"), int | float)
    ]
    validated.sort(key=lambda node: -float(node["metric_delta"]))
    payload = {
        "projection_type": "research_hypothesis_frontier_v1",
        "node_count": len(nodes),
        "frontier_count": len(frontier),
        "frontier": frontier,
        "selected_next_hypothesis_id": frontier[0]["hypothesis_id"] if frontier else None,
        "best_validated_hypothesis_id": validated[0]["hypothesis_id"] if validated else None,
        "best_validated_metric_delta": validated[0]["metric_delta"] if validated else None,
        "merge_performed": False,
        "next_action": "dispatch_selected_hypothesis" if frontier else "review_validated_candidates",
    }
    payload["projection_hash"] = _stable_hash(payload)
    return payload


def _append_jsonl(path: Path, payload: dict[str, object]) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n")


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
