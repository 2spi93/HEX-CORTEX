from hex_cortex.memory.cortex_guidance_quality_score import CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME
from hex_cortex.memory.cortex_guidance_quality_score import CortexGuidanceQualityScoreRecord


def test_guidance_quality_score_imports() -> None:
    assert CORTEX_GUIDANCE_QUALITY_SCORE_FILENAME == "cortex-guidance-quality-score.jsonl"
    assert CortexGuidanceQualityScoreRecord.__name__ == "CortexGuidanceQualityScoreRecord"
