from hex_cortex.memory.cortex_local_compact_expert_adapter import CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME
from hex_cortex.memory.cortex_local_compact_expert_adapter import CortexLocalCompactExpertAdapterRecord


def test_local_compact_expert_adapter_imports() -> None:
    assert CORTEX_LOCAL_COMPACT_EXPERT_ADAPTER_FILENAME == "cortex-local-compact-expert-adapter.jsonl"
    assert CortexLocalCompactExpertAdapterRecord.__name__ == "CortexLocalCompactExpertAdapterRecord"
