from __future__ import annotations
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from pydantic import BaseModel, Field
from hex_cortex.memory.cortex_local_patch_plan import CORTEX_LOCAL_PATCH_PLAN_FILENAME, CortexLocalPatchPlanJsonlStore
from hex_cortex.memory.cortex_local_patch_plan_review_gate import CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME, CortexLocalPatchPlanReviewGateJsonlStore
CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME='cortex-local-patch-artifact.jsonl'
class CortexLocalPatchArtifactRecord(BaseModel):
    artifact_id:str=Field(default_factory=lambda:f'cortex_local_patch_artifact_{uuid4().hex}')
    created_at:str=Field(default_factory=lambda:datetime.now(UTC).isoformat())
    profile_path:str; source_review_hash:str|None; source_patch_plan_hash:str|None; target_branch_type:str|None
    artifact_scope:str; artifact_lines:list[str]; verification_commands:list[str]; stop_conditions:list[str]
    artifact_status:str; artifact_decision:str; artifact_allowed:bool; next_action:str; blockers:list[str]; artifact_hash:str; reasons:list[str]
class CortexLocalPatchArtifactJsonlStore:
    def __init__(self,path:str|Path)->None: self.path=Path(path)
    def load(self):
        if not self.path.exists(): return []
        return [CortexLocalPatchArtifactRecord.model_validate_json(x) for x in self.path.read_text(encoding='utf-8').splitlines() if x.strip()]
    def save(self,records): self.path.parent.mkdir(parents=True,exist_ok=True); self.path.write_text(''.join(r.model_dump_json()+'\n' for r in records),encoding='utf-8'); return len(records)
def _h(*p): return hashlib.sha256('|'.join(p).encode()).hexdigest()
def _latest_review(profile):
    rs=CortexLocalPatchPlanReviewGateJsonlStore(profile/CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME).load(); return rs[-1] if rs else None
def _plan(profile,review):
    if review is None: return None
    rs=CortexLocalPatchPlanJsonlStore(profile/CORTEX_LOCAL_PATCH_PLAN_FILENAME).load()
    for r in reversed(rs):
        if r.patch_plan_hash==review.source_patch_plan_hash: return r
    return None
def build_cortex_local_patch_artifact(profile:Path):
    rv=_latest_review(profile); p=_plan(profile,rv); b=[]
    if rv is None: b.append('missing_review')
    elif rv.review_allowed is not True: b.append('review_not_allowed')
    elif rv.next_action!='emit_local_patch_artifact': b.append('review_not_waiting_artifact')
    if p is None: b.append('missing_plan')
    ok=not b; dec='local_patch_artifact_ready' if ok else 'local_patch_artifact_blocked'; na='await_patch_application_receipt' if ok else 'repair_local_patch_artifact'; reasons=['artifact_prepared'] if ok else b
    lines=['# Cortex local patch artifact','# descriptive only, not auto-applied']+[f'PLAN {u.unit_id}: {u.operation} -> {u.file_path}' for u in (p.patch_units if p else [])] if ok else []
    ah=_h(str(profile), rv.review_hash if rv else 'missing', p.patch_plan_hash if p else 'missing', dec, na, *lines, *reasons)
    rec=CortexLocalPatchArtifactRecord(profile_path=str(profile),source_review_hash=rv.review_hash if rv else None,source_patch_plan_hash=p.patch_plan_hash if p else None,target_branch_type=p.target_branch_type if p else None,artifact_scope='text_artifact_only',artifact_lines=lines,verification_commands=list(p.verification_commands) if ok and p else [],stop_conditions=list(p.stop_conditions) if ok and p else [],artifact_status='ready' if ok else 'blocked',artifact_decision=dec,artifact_allowed=ok,next_action=na,blockers=b,artifact_hash=ah,reasons=reasons)
    path=profile/CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME; st=CortexLocalPatchArtifactJsonlStore(path); cur=st.load(); new=[] if rec.source_review_hash and any(x.source_review_hash==rec.source_review_hash for x in cur) else [rec]; count=st.save(cur+new)
    return {'artifact_type':'cortex_local_patch_artifact','artifact_path':str(path),'artifact_count':count,'artifact_records':[x.model_dump(mode='json') for x in new]}
def summarize_cortex_local_patch_artifacts(path:Path):
    rs=CortexLocalPatchArtifactJsonlStore(path).load(); latest=rs[-1] if rs else None; allowed=[r for r in rs if r.artifact_allowed]
    return {'inspect_type':'cortex_local_patch_artifact','path':str(path),'exists':path.exists(),'total_artifact_count':len(rs),'allowed_artifact_count':len(allowed),'latest_artifact_status':latest.artifact_status if latest else None,'latest_artifact_decision':latest.artifact_decision if latest else None,'latest_artifact_allowed':latest.artifact_allowed if latest else None,'latest_next_action':latest.next_action if latest else None,'latest_artifact_hash':latest.artifact_hash if latest else None}
