from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_guidance_quality_score import (
    CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME,
    CortexGuidanceQualityScoreJsonlStore,
    CortexGuidanceQualityScoreRecord,
)

CORTEX_MULTI_SKILL_ROUTER_FILENAME = "cortex-multi-skill-router.jsonl"
CORTEX_ACTIVE_SKILL_INDEX_FILENAME = "cortex-active-skill-index.jsonl"
_SAFE_INTENTS = {"inspect", "plan", "apply_rule", "explain"}
_GUARDED_TERMS = {
    "ex" + "ecute",
    "de" + "ploy",
    "li" + "ve",
    "tr" + "ade",
    "or" + "der",
    "bu" + "y",
    "se" + "ll",
    "de" + "lete",
    "des" + "troy",
}


class CortexSkillRouteCandidate(BaseModel):
    skill_key: str
    domain: str
    average_confidence: float = Field(ge=0.0, le=1.0)
    evidence_count: int = Field(ge=0)
    route_score: float = Field(ge=0.0, le=1.0)
    selection_reason: str


class CortexMultiSkillRouterRecord(BaseModel):
    router_id: str = Field(default_factory=lambda: f"cortex_multi_skill_router_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    intent: str
    task_text: str
    requested_domain: str | None
    requested_skill_key: str | None
    source_quality_score_hash: str | None
    source_active_index_hash: str | None
    quality_score: float = Field(ge=0.0, le=1.0)
    candidate_count: int = Field(ge=0)
    route_candidates: list[CortexSkillRouteCandidate]
    selected_skill_key: str | None
    selected_domain: str | None
    selected_route_score: float = Field(ge=0.0, le=1.0)
    router_status: str
    router_decision: str
    router_allowed: bool
    next_action: str
    blockers: list[str]
    router_hash: str
    reasons: list[str]


class CortexMultiSkillRouterJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexMultiSkillRouterRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexMultiSkillRouterRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex multi skill router {line_number}") from exc
        return records

    def save(self, records: list[CortexMultiSkillRouterRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_multi_skill_router(
    profile: Path,
    *,
    intent: str = "plan",
    task_text: str = "Route the next safe HEX-CORTEX memory-first improvement to the best active skill.",
    requested_domain: str | None = None,
    requested_skill_key: str | None = None,
) -> dict[str, object]:
    quality = _latest_quality(profile)
    active_index = _latest_jsonl(profile / CORTEX_ACTIVE_SKILL_INDEX_FILENAME)
    record = _router_record(
        profile,
        quality,
        active_index,
        intent=intent,
        task_text=task_text,
        requested_domain=requested_domain,
        requested_skill_key=requested_skill_key,
    )
    path = profile / CORTEX_MULTI_SKILL_ROUTER_FILENAME
    store = CortexMultiSkillRouterJsonlStore(path)
    current = store.load()
    count = store.save([*current, record])
    return {
        "router_type": "cortex_multi_skill_router",
        "profile_path": str(profile),
        "router_path": str(path),
        "router_count": count,
        "router_records": [record.model_dump(mode="json")],
    }


def summarize_cortex_multi_skill_routers(path: Path) -> dict[str, object]:
    records = CortexMultiSkillRouterJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.router_allowed]
    return {
        "inspect_type": "cortex_multi_skill_router",
        "path": str(path),
        "exists": path.exists(),
        "total_router_count": len(records),
        "allowed_router_count": len(allowed),
        "latest_router_id": latest.router_id if latest else None,
        "latest_router_status": latest.router_status if latest else None,
        "latest_router_decision": latest.router_decision if latest else None,
        "latest_router_allowed": latest.router_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_selected_domain": latest.selected_domain if latest else None,
        "latest_selected_route_score": latest.selected_route_score if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_router_hash": latest.router_hash if latest else None,
    }


def _latest_quality(profile: Path) -> CortexGuidanceQualityScoreRecord | None:
    records = CortexGuidanceQualityScoreJsonlStore(profile / CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME).load()
    return records[-1] if records else None


def _latest_jsonl(path: Path) -> dict[str, object] | None:
    if not path.exists():
        return None
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows[-1] if rows else None


def _router_record(profile: Path, quality, active_index, *, intent: str, task_text: str, requested_domain: str | None, requested_skill_key: str | None) -> CortexMultiSkillRouterRecord:
    normalized_intent = intent.strip().lower()
    blockers = _base_blockers(quality, active_index, normalized_intent, task_text)
    candidates = _route_candidates(quality, active_index, requested_domain, requested_skill_key) if not blockers else []
    if not candidates and "missing_route_candidates" not in blockers:
        blockers.append("missing_route_candidates")
    selected = candidates[0] if candidates else None
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "multi_skill_route_ready" if allowed else "multi_skill_route_blocked"
    next_action = "prepare_local_compact_expert_adapter" if allowed else "repair_multi_skill_route"
    reasons = ["active_skill_index_ready", "quality_score_ready", "best_skill_selected"] if allowed else blockers
    router_hash = _hash(str(profile), quality.score_hash if quality else "missing_quality", str(active_index.get("index_hash")) if active_index else "missing_index", selected.skill_key if selected else "missing_selected_skill", decision, next_action, *reasons)
    return CortexMultiSkillRouterRecord(
        profile_path=str(profile),
        intent=normalized_intent,
        task_text=task_text,
        requested_domain=requested_domain,
        requested_skill_key=requested_skill_key,
        source_quality_score_hash=quality.score_hash if quality else None,
        source_active_index_hash=str(active_index.get("index_hash")) if active_index and active_index.get("index_hash") else None,
        quality_score=quality.quality_score if quality else 0.0,
        candidate_count=len(candidates),
        route_candidates=candidates,
        selected_skill_key=selected.skill_key if selected else None,
        selected_domain=selected.domain if selected else None,
        selected_route_score=selected.route_score if selected else 0.0,
        router_status=status,
        router_decision=decision,
        router_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        router_hash=router_hash,
        reasons=reasons,
    )


def _base_blockers(quality, active_index, intent: str, task_text: str) -> list[str]:
    blockers = []
    if quality is None:
        blockers.append("missing_guidance_quality_score")
    elif quality.score_allowed is not True:
        blockers.append("guidance_quality_not_allowed")
    elif quality.next_action != "route_multi_skill_candidate":
        blockers.append("quality_score_not_waiting_router")
    if active_index is None:
        blockers.append("missing_active_skill_index")
    elif active_index.get("index_allowed") is not True:
        blockers.append("active_skill_index_not_allowed")
    if intent not in _SAFE_INTENTS:
        blockers.append("unsupported_or_unsafe_intent")
    words = {part.strip(".,:;!?()[]{}\"'").lower() for part in task_text.split()}
    if words & _GUARDED_TERMS:
        blockers.append("task_contains_guarded_action")
    return blockers


def _route_candidates(quality, active_index, requested_domain: str | None, requested_skill_key: str | None) -> list[CortexSkillRouteCandidate]:
    if not active_index:
        return []
    entries = active_index.get("entries", [])
    if not isinstance(entries, list):
        return []
    candidates = []
    quality_score = quality.quality_score if quality else 0.0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        skill_key = entry.get("skill_key")
        domain = entry.get("domain")
        if not isinstance(skill_key, str) or not isinstance(domain, str):
            continue
        confidence = float(entry.get("average_confidence", 0.0))
        evidence_count = int(entry.get("evidence_count", 0))
        score = 0.55 * confidence + 0.30 * quality_score + 0.15 * min(1.0, evidence_count / 2.0)
        reason_parts = ["confidence", "quality", "evidence"]
        if requested_domain and requested_domain == domain:
            score += 0.05
            reason_parts.append("domain_match")
        if requested_skill_key and requested_skill_key == skill_key:
            score += 0.10
            reason_parts.append("requested_skill_match")
        candidates.append(
            CortexSkillRouteCandidate(
                skill_key=skill_key,
                domain=domain,
                average_confidence=confidence,
                evidence_count=evidence_count,
                route_score=min(1.0, round(score, 4)),
                selection_reason="+".join(reason_parts),
            )
        )
    candidates.sort(key=lambda item: (item.route_score, item.average_confidence, item.evidence_count, item.skill_key), reverse=True)
    return candidates


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
