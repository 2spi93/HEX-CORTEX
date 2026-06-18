from __future__ import annotations
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, Field
from hex_cortex.memory.cortex_local_patch_plan import CORTEX_LOCAL_PATCH_PLAN_FILENAME, CortexLocalPatchPlanJsonlStore
CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME='cortex-local-patch-plan-review-gate.jsonl'
class CortexLocalPatchPlanReviewGateRecord(BaseModel):
    review_id:str=Field(default_factory=lambda:f'cortex_local_patch_plan_review_gate_{uuid4().hex}')
    created_at:str=Field(default_factory=lambda:datetime.now(UTC).isoformat())
    profile_path:str; source_patch_plan_hash:str|None; target_branch_type:str|None
    reviewed_patch_unit_count:int=Field(ge=0); reviewed_command_count:int=Field(ge=0)
    unit_verdict:str; command_verdict:str; safety_verdict:str; lineage_verdict:str
    review_status:str; review_decision:str; review_allowed:bool; next_action:str
    blockers:list[str]; review_hash:str; reasons:list[str]
class CortexLocalPatchPlanReviewGateJsonlStore:
    def __init__(self,path:str|Path)->None: self.path=Path(path)
    def load(self):
        if not self.path.exists(): return []
        return [CortexLocalPatchPlanReviewGateRecord.model_validate_json(x) for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip()]
    def save(self,records):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.path.write_text(''.join(r.model_dump_json()+'\n' for r in records),encoding='utf-8'); return len(records)
def _h(*p): return hashlib.sha256('|'.join(p).encode()).hexdigest()
def _latest(profile):
    rs=CortexLocalPatchPlanJsonlStore(profile/CORTEX_LOCAL_PATCH_PLAN_FILENAME).load(); return rs[-1] if rs else None
def _blockers(p):
    if p is None: return ['missing_local_patch_plan']
    b=[]
    if p.patch_plan_allowed is not True: b.append('local_patch_plan_not_allowed')
    if p.patch_plan_decision!='local_patch_plan_ready': b.append('local_patch_plan_not_ready')
    if p.next_action!='await_local_patch_plan_review': b.append('patch_plan_not_waiting_review')
    if p.patch_scope!='local_plan_only': b.append('patch_scope_invalid')
    if not p.patch_units: b.append('missing_patch_units')
    if not p.verification_commands or 'python -m pytest' not in p.verification_commands: b.append('missing_verification_commands')
    if not p.safety_constraints or not p.stop_conditions: b.append('missing_safety_or_stop_conditions')
    if not all([p.source_materialization_review_hash,p.source_materialization_hash,p.source_packet_hash,p.source_plan_hash]): b.append('missing_source_lineage')
    return b
def build_cortex_local_patch_plan_review_gate(profile:Path):
    p=_latest(profile); b=_blockers(p); ok=not b
    dec='local_patch_plan_review_ready' if ok else 'local_patch_plan_review_blocked'; na='emit_local_patch_artifact' if ok else 'repair_local_patch_plan'
    reasons=['patch_units_reviewed','local_patch_plan_review_ready'] if ok else b
    rh=_h(str(profile), p.patch_plan_hash if p else 'missing', dec, na, *reasons)
    rec=CortexLocalPatchPlanReviewGateRecord(profile_path=str(profile),source_patch_plan_hash=p.patch_plan_hash if p else None,target_branch_type=p.target_branch_type if p else None,reviewed_patch_unit_count=len(p.patch_units) if p else 0,reviewed_command_count=len(p.verification_commands) if p else 0,unit_verdict='patch_units_ready' if p and p.patch_units else 'patch_units_missing',command_verdict='verification_commands_ready' if p and 'python -m pytest' in p.verification_commands else 'verification_commands_missing',safety_verdict='safety_ready' if p and p.safety_constraints and p.stop_conditions else 'safety_missing',lineage_verdict='lineage_present' if p and all([p.source_materialization_review_hash,p.source_materialization_hash,p.source_packet_hash,p.source_plan_hash]) else 'lineage_missing',review_status='ready' if ok else 'blocked',review_decision=dec,review_allowed=ok,next_action=na,blockers=b,review_hash=rh,reasons=reasons)
    path=profile/CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME; st=CortexLocalPatchPlanReviewGateJsonlStore(path); cur=st.load(); new=[] if rec.source_patch_plan_hash and any(x.source_patch_plan_hash==rec.source_patch_plan_hash for x in cur) else [rec]; count=st.save(cur+new)
    return {'review_type':'cortex_local_patch_plan_review_gate','profile_path':str(profile),'review_path':str(path),'review_count':count,'review_records':[x.model_dump(mode='json') for x in new]}
def summarize_cortex_local_patch_plan_review_gates(path:Path):
    rs=CortexLocalPatchPlanReviewGateJsonlStore(path).load(); latest=rs[-1] if rs else None; allowed=[r for r in rs if r.review_allowed]
    return {'inspect_type':'cortex_local_patch_plan_review_gate','path':str(path),'exists':path.exists(),'total_review_count':len(rs),'allowed_review_count':len(allowed),'latest_review_status':latest.review_status if latest else None,'latest_review_decision':latest.review_decision if latest else None,'latest_review_allowed':latest.review_allowed if latest else None,'latest_next_action':latest.next_action if latest else None,'latest_review_hash':latest.review_hash if latest else None}
