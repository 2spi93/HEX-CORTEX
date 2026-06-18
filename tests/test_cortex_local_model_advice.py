from hex_cortex.memory.cortex_local_model_advice import CORTEX_LOCAL_MODEL_ADVICE_FILENAME


def test_local_model_advice_imports() -> None:
    assert CORTEX_LOCAL_MODEL_ADVICE_FILENAME == "cortex-local-model-advice.jsonl"
