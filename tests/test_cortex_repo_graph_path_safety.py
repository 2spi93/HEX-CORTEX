from pathlib import Path

import pytest

from hex_cortex.memory.cortex_repo_graph import summarize_module_contract


def test_module_contract_rejects_path_outside_repository(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def secret():\n    return 1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="escapes repository root"):
        summarize_module_contract(root, "../outside.py")
