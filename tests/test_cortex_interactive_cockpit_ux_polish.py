from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME
from hex_cortex.memory.cortex_interactive_cockpit_ux_polish import CortexInteractiveCockpitUxPolishRecord


def test_interactive_cockpit_ux_polish_imports() -> None:
    assert CORTEX_INTERACTIVE_COCKPIT_UX_POLISH_FILENAME == "cortex-interactive-cockpit-ux-polish.jsonl"
    assert CortexInteractiveCockpitUxPolishRecord.__name__ == "CortexInteractiveCockpitUxPolishRecord"
