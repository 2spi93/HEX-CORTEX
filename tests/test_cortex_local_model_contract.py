from hex_cortex.memory.cortex_local_model_backend_adapter_contract import CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME


def test_local_model_contract_imports() -> None:
    assert CORTEX_LOCAL_MODEL_BACKEND_ADAPTER_CONTRACT_FILENAME.endswith(".jsonl")
