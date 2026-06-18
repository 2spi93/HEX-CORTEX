from hex_cortex.memory.cortex_ui_cockpit_builder import CORTEX_UI_COCKPIT_BUILD_FILENAME
from hex_cortex.memory.cortex_ui_cockpit_builder import CortexUiCockpitBuildRecord


def test_ui_cockpit_builder_imports() -> None:
    assert CORTEX_UI_COCKPIT_BUILD_FILENAME == "cortex-ui-cockpit-build.jsonl"
    assert CortexUiCockpitBuildRecord.__name__ == "CortexUiCockpitBuildRecord"
