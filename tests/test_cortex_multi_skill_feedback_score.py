from hex_cortex.memory.cortex_multi_skill_feedback_score import CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME
from hex_cortex.memory.cortex_multi_skill_feedback_score import CortexMultiSkillFeedbackScoreRecord


def test_multi_skill_feedback_score_imports() -> None:
    assert CORTEX_MULTI_SKILL_FEEDBACK_SCORE_FILENAME == "cortex-multi-skill-feedback-score.jsonl"
    assert CortexMultiSkillFeedbackScoreRecord.__name__ == "CortexMultiSkillFeedbackScoreRecord"
