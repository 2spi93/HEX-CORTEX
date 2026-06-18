from hex_cortex.memory.cortex_operator_ui_wording_patch import CORTEX_OPERATOR_UI_WORDING_PATCH_FILENAME


def test_ui_copy_patch_imports() -> None:
    assert CORTEX_OPERATOR_UI_WORDING_PATCH_FILENAME.endswith(".jsonl")
