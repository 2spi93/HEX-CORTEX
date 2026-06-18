from hex_cortex.memory.cortex_product_hardening_plan import CORTEX_PRODUCT_HARDENING_PLAN_FILENAME


def test_release_phase_plan_imports() -> None:
    assert CORTEX_PRODUCT_HARDENING_PLAN_FILENAME.endswith(".jsonl")
