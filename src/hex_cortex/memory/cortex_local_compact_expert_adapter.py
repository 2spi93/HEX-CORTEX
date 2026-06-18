from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_multi_skill_router import (
    CORTEX_MULTI_SKILL_ROUTER_FILENAME,
    CortexMultiSkillRouterJsonlStore,
    CortexMultiSkillRouterRecord,
)

CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME = "cortex-local-compact-expert-adapter.jsonl"


class CortexLocalCompactExpertAdapterRecord(BaseModel):
    adapter_id: str = Field(default_factory=lambda: f"cortex_local_compact_expert_adapter_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_router_id: str | None
    source_router_hash: str | None
    selected_skill_key: str | None
    selected_domain: str | None
    selected_route_score: float = Field(ge=0.0, le=1.0)
    expert_kind: str | None
    adapter_strategy: str | None
    runtime_profile: str | None
    base_model_slot: str | None
    embedding_slot: str | None
    reranker_slot: str | None
    model_policy: str | None
    adapter_status: str
    adapter_decision: str
    adapter_allowed: bool
    next_action: str
    blockers: list[str]
    adapter_hash: str
    reasons: list[str]


class CortexLocalCompactExpertAdapterJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexLocalCompactExpertAdapterRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexLocalCompactExpertAdapterRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex local compact expert adapter {line_number}") from exc
        return records

    def save(self, records: list[CortexLocalCompactExpertAdapterRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_local_compact_expert_adapter(profile: Path) -> dict[str, object]:
    router = _latest_router(profile)
    record = _adapter_record(profile, router)
    path = profile / CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME
    store = CortexLocalCompactExpertAdapterJsonlStore(path)
    current = store.load()
    if record.source_router_hash and any(item.source_router_hash == record.source_router_hash for item in current):
        records: list[CortexLocalCompactExpertAdapterRecord] = []
    else:
        records = [record]
    count = store.save([*current, *records])
    return {
        "adapter_type": "cortex_local_compact_expert_adapter",
        "profile_path": str(profile),
        "adapter_path": str(path),
        "adapter_count": count,
        "adapter_records": [item.model_dump(mode="json") for item in records],
    }


def summarize_cortex_local_compact_expert_adapters(path: Path) -> dict[str, object]:
    records = CortexLocalCompactExpertAdapterJsonlStore(path).load()
    latest = records[-1] if records else None
    allowed = [record for record in records if record.adapter_allowed]
    return {
        "inspect_type": "cortex_local_compact_expert_adapter",
        "path": str(path),
        "exists": path.exists(),
        "total_adapter_count": len(records),
        "allowed_adapter_count": len(allowed),
        "latest_adapter_id": latest.adapter_id if latest else None,
        "latest_adapter_status": latest.adapter_status if latest else None,
        "latest_adapter_decision": latest.adapter_decision if latest else None,
        "latest_adapter_allowed": latest.adapter_allowed if latest else None,
        "latest_selected_skill_key": latest.selected_skill_key if latest else None,
        "latest_expert_kind": latest.expert_kind if latest else None,
        "latest_model_policy": latest.model_policy if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_adapter_hash": latest.adapter_hash if latest else None,
    }


def _latest_router(profile: Path) -> CortexMultiSkillRouterRecord | None:
    records = CortexMultiSkillRouterJsonlStore(profile / CORTEX_MULTI_SKILL_ROUTER_FILENAME).load()
    return records[-1] if records else None


def _adapter_record(profile: Path, router: CortexMultiSkillRouterRecord | None) -> CortexLocalCompactExpertAdapterRecord:
    blockers = _blockers(router)
    allowed = not blockers
    expert_kind = _expert_kind(router.selected_domain if router else None) if allowed else None
    adapter_strategy = "prompt_adapter_then_lora_candidate" if allowed else None
    runtime_profile = "local_cpu_first_small_gpu_optional" if allowed else None
    base_model_slot = _base_model_slot(router.selected_domain if router else None) if allowed else None
    embedding_slot = "local_small_embedding_model" if allowed else None
    reranker_slot = "local_lightweight_reranker_optional" if allowed else None
    model_policy = "local_first_frontier_oracle_fallback" if allowed else None
    status = "ready" if allowed else "blocked"
    decision = "local_compact_expert_adapter_ready" if allowed else "local_compact_expert_adapter_blocked"
    next_action = "prepare_world_model_simulation_slot" if allowed else "repair_local_compact_expert_adapter"
    reasons = ["router_ready", "compact_expert_slot_prepared", "frontier_oracle_kept_as_fallback"] if allowed else blockers
    adapter_hash = _hash(
        str(profile),
        router.router_hash if router else "missing_router",
        router.selected_skill_key if router and router.selected_skill_key else "missing_skill",
        expert_kind or "missing_expert",
        decision,
        next_action,
        *reasons,
    )
    return CortexLocalCompactExpertAdapterRecord(
        profile_path=str(profile),
        source_router_id=router.router_id if router else None,
        source_router_hash=router.router_hash if router else None,
        selected_skill_key=router.selected_skill_key if router else None,
        selected_domain=router.selected_domain if router else None,
        selected_route_score=router.selected_route_score if router else 0.0,
        expert_kind=expert_kind,
        adapter_strategy=adapter_strategy,
        runtime_profile=runtime_profile,
        base_model_slot=base_model_slot,
        embedding_slot=embedding_slot,
        reranker_slot=reranker_slot,
        model_policy=model_policy,
        adapter_status=status,
        adapter_decision=decision,
        adapter_allowed=allowed,
        next_action=next_action,
        blockers=blockers,
        adapter_hash=adapter_hash,
        reasons=reasons,
    )


def _blockers(router: CortexMultiSkillRouterRecord | None) -> list[str]:
    blockers = []
    if router is None:
        return ["missing_multi_skill_router"]
    if router.router_allowed is not True:
        blockers.append("multi_skill_router_not_allowed")
    if router.router_decision != "multi_skill_route_ready":
        blockers.append("multi_skill_router_not_ready")
    if router.next_action != "prepare_local_compact_expert_adapter":
        blockers.append("router_not_waiting_local_adapter")
    if not router.selected_skill_key or not router.selected_domain:
        blockers.append("missing_selected_skill_or_domain")
    if router.selected_route_score < 0.75:
        blockers.append("selected_route_score_below_threshold")
    return blockers


def _expert_kind(domain: str | None) -> str:
    if domain == "architecture":
        return "local_compact_architecture_expert"
    if domain == "code":
        return "local_compact_code_expert"
    if domain == "memory":
        return "local_compact_memory_expert"
    return "local_compact_general_expert"


def _base_model_slot(domain: str | None) -> str:
    if domain == "architecture":
        return "small_instruct_model_architecture_slot"
    if domain == "code":
        return "small_code_model_slot"
    if domain == "memory":
        return "small_retrieval_reasoning_model_slot"
    return "small_general_instruct_model_slot"


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
