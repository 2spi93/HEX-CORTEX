from hex_cortex.memory.cortex_operator_ui_wording_polish_plan import CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME


def test_ui_copy_plan_imports() -> None:
    assert CORTEX_OPERATOR_UI_WORDING_POLISH_PLAN_FILENAME.endswith(".jsonl")
