from hex_cortex.memory.cortex_local_patch_plan_review_gate import CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME
from hex_cortex.memory.cortex_local_patch_artifact import CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME

def test_tail_rail_imports() -> None:
    assert CORTEX_LOCAL_PATCH_PLAN_REVIEW_GATE_FILENAME.endswith('.jsonl')
    assert CORTEX_LOCAL_PATCH_ARTIFACT_FILENAME.endswith('.jsonl')
