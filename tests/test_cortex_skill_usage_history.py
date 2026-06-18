from hex_cortex.memory.cortex_skill_usage_history import CORTEX_SKILL_USAGE_HISTORY_FILENAME
from hex_cortex.memory.cortex_skill_usage_history import CortexSkillUsageHistoryRecord


def test_skill_usage_history_imports() -> None:
    assert CORTEX_SKILL_USAGE_HISTORY_FILENAME == "cortex-skill-usage-history.jsonl"
    assert CortexSkillUsageHistoryRecord.__name__ == "CortexSkillUsageHistoryRecord"
