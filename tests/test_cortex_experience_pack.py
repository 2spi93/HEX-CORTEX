from hex_cortex.memory.cortex_experience_pack import CORTEX_EXPERIENCE_PACK_FILENAME


def test_experience_pack_marker_imports() -> None:
    assert CORTEX_EXPERIENCE_PACK_FILENAME == "cortex-experience-pack.jsonl"
