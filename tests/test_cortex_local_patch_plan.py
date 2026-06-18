from hex_cortex.memory.cortex_local_patch_plan import CORTEX_LOCAL_PATCH_PLAN_FILENAME
from hex_cortex.memory.cortex_local_patch_plan import CortexLocalPatchPlanRecord


def test_local_patch_plan_imports() -> None:
    assert CORTEX_LOCAL_PATCH_PLAN_FILENAME == "cortex-local-patch-plan.jsonl"
    assert CortexLocalPatchPlanRecord.__name__ == "CortexLocalPatchPlanRecord"
