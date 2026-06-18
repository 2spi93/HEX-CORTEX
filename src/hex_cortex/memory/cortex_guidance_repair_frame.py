from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, Field

from hex_cortex.memory.cortex_skill_guidance_renderer import (
    CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME,
    CortexSkillGuidanceRendererJsonlStore,
    CortexSkillGuidanceRendererRecord,
)

CORTEX_GUIDANCE_REPAIR_FRAME_FILENAME = "cortex-guidance-repair-frame.jsonl"


class CortexGuidanceRepairFrameRecord(BaseModel):
    repair_id: str = Field(default_factory=lambda: f"cortex_guidance_repair_{uuid4().hex}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    profile_path: str
    source_guidance_id: str | None
    source_guidance_hash: str | None
    source_use_hash: str | None
    source_blockers: list[str]
    repair_status: str
    repair_decision: str
    repair_allowed: bool
    repair_reason: str
    repair_steps: list[str]
    expected_next_state: str
    next_action: str
    blockers: list[str]
    repair_hash: str
    reasons: list[str]


class CortexGuidanceRepairFrameJsonlStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> list[CortexGuidanceRepairFrameRecord]:
        if not self.path.exists():
            return []
        records = []
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    records.append(CortexGuidanceRepairFrameRecord.model_validate_json(line))
                except Exception as exc:  # noqa: BLE001
                    raise ValueError(f"invalid cortex guidance repair frame {line_number}") from exc
        return records

    def save(self, records: list[CortexGuidanceRepairFrameRecord]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for record in records:
                handle.write(f"{record.model_dump_json()}\n")
        return len(records)


def build_cortex_guidance_repair_frame(profile: Path) -> dict[str, object]:
    guidance = _latest_guidance(profile)
    record = _repair_record(profile, guidance)
    path = profile / CORTEX_GUIDANCE_REPAIR_FRAME_FILENAME
    store = CortexGuidanceRepairFrameJsonlStore(path)
    count = store.save([*store.load(), record])
    return {
        "repair_type": "cortex_guidance_repair_frame",
        "profile_path": str(profile),
        "repair_path": str(path),
        "repair_count": count,
        "repair_record": record.model_dump(mode="json"),
    }


def summarize_cortex_guidance_repair_frames(path: Path) -> dict[str, object]:
    records = CortexGuidanceRepairFrameJsonlStore(path).load()
    latest = records[-1] if records else None
    return {
        "inspect_type": "cortex_guidance_repair_frame",
        "path": str(path),
        "exists": path.exists(),
        "total_repair_count": len(records),
        "latest_repair_id": latest.repair_id if latest else None,
        "latest_repair_status": latest.repair_status if latest else None,
        "latest_repair_decision": latest.repair_decision if latest else None,
        "latest_repair_allowed": latest.repair_allowed if latest else None,
        "latest_expected_next_state": latest.expected_next_state if latest else None,
        "latest_next_action": latest.next_action if latest else None,
        "latest_repair_hash": latest.repair_hash if latest else None,
    }


def _latest_guidance(profile: Path) -> CortexSkillGuidanceRendererRecord | None:
    records = CortexSkillGuidanceRendererJsonlStore(
        profile / CORTEX_SKILL_GUIDANCE_RENDERER_FILENAME
    ).load()
    return records[-1] if records else None


def _repair_record(
    profile: Path,
    guidance: CortexSkillGuidanceRendererRecord | None,
) -> CortexGuidanceRepairFrameRecord:
    blockers = _repair_blockers(guidance)
    allowed = not blockers
    status = "ready" if allowed else "blocked"
    decision = "guidance_repair_ready" if allowed else "guidance_repair_blocked"
    next_action = "create_allowed_controlled_skill_use" if allowed else "inspect_guidance_state"
    steps = _steps(allowed)
    reasons = ["blocked_guidance_detected", "safe_repair_path_prepared"] if allowed else blockers
    repair_hash = _hash(
        str(profile),
        guidance.guidance_hash if guidance else "missing_guidance",
        decision,
        next_action,
        *steps,
        *reasons,
    )
    return CortexGuidanceRepairFrameRecord(
        profile_path=str(profile),
        source_guidance_id=guidance.guidance_id if guidance else None,
        source_guidance_hash=guidance.guidance_hash if guidance else None,
        source_use_hash=guidance.source_use_hash if guidance else None,
        source_blockers=guidance.blockers if guidance else [],
        repair_status=status,
        repair_decision=decision,
        repair_allowed=allowed,
        repair_reason="latest guidance is blocked and should be replaced by a non-destructive controlled use" if allowed else "no blocked guidance available for repair",
        repair_steps=steps,
        expected_next_state="skill_guidance_rendered" if allowed else "guidance_state_inspected",
        next_action=next_action,
        blockers=blockers,
        repair_hash=repair_hash,
        reasons=reasons,
    )


def _repair_blockers(guidance: CortexSkillGuidanceRendererRecord | None) -> list[str]:
    if guidance is None:
        return ["missing_skill_guidance"]
    if guidance.guidance_allowed is True:
        return ["guidance_already_allowed"]
    if guidance.guidance_decision != "skill_guidance_blocked":
        return ["guidance_not_blocked"]
    return []


def _steps(allowed: bool) -> list[str]:
    if not allowed:
        return []
    return [
        "Create a new non-destructive controlled skill use.",
        "Render skill guidance again after the allowed use is latest.",
        "Build the guided reasoning frame only after guidance_allowed is true.",
    ]


def _hash(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
