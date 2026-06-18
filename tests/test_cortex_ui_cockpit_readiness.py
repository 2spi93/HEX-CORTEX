from hex_cortex.memory.cortex_ui_cockpit_readiness import CORTEX_UI_COCKPIT_READINESS_FILENAME
from hex_cortex.memory.cortex_ui_cockpit_readiness import CortexUiCockpitReadinessRecord


def test_ui_cockpit_readiness_imports() -> None:
    assert CORTEX_UI_COCKPIT_READINESS_FILENAME == "cortex-ui-cockpit-readiness.jsonl"
    assert CortexUiCockpitReadinessRecord.__name__ == "CortexUiCockpitReadinessRecord"
