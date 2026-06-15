import pytest

from hex_cortex.cli import main


def test_cli_rejects_two_memory_pruning_commands(tmp_path) -> None:
    profile = tmp_path / "profile"
    dry_flag = "--prune-memory-profile"
    write_flag = "--apply-" + "memory-pruning-profile"

    with pytest.raises(ValueError, match="only one pruning mode"):
        main([dry_flag, str(profile), write_flag, str(profile)])
