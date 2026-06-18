from hex_cortex.memory.cortex_interactive_cockpit_shell import CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME
from hex_cortex.memory.cortex_interactive_cockpit_shell import CortexInteractiveCockpitShellRecord


def test_interactive_cockpit_shell_imports() -> None:
    assert CORTEX_INTERACTIVE_COCKPIT_SHELL_FILENAME == "cortex-interactive-cockpit-shell.jsonl"
    assert CortexInteractiveCockpitShellRecord.__name__ == "CortexInteractiveCockpitShellRecord"
