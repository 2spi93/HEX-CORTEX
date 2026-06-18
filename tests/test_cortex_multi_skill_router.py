from hex_cortex.memory.cortex_multi_skill_router import CORTEX_MULTI_SKILL_ROUTER_FILENAME
from hex_cortex.memory.cortex_multi_skill_router import CortexMultiSkillRouterRecord


def test_multi_skill_router_imports() -> None:
    assert CORTEX_MULTI_SKILL_ROUTER_FILENAME == "cortex-multi-skill-router.jsonl"
    assert CortexMultiSkillRouterRecord.__name__ == "CortexMultiSkillRouterRecord"
