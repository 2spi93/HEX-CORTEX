from hex_cortex.memory.cortex_frontier_oracle_fallback import CORTEX_FRONTIER_ORACLE_FALLBACK_FILENAME
from hex_cortex.memory.cortex_frontier_oracle_fallback import CortexFrontierOracleFallbackRecord


def test_frontier_oracle_fallback_imports() -> None:
    assert CORTEX_FRONTIER_ORACLE_FALLBACK_FILENAME == "cortex-frontier-oracle-fallback.jsonl"
    assert CortexFrontierOracleFallbackRecord.__name__ == "CortexFrontierOracleFallbackRecord"
