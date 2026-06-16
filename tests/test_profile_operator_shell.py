from hex_cortex.memory.profile_operator_control_cli import main


def test_operator_shell_exit_code(tmp_path, capsys) -> None:
    exit_code = main([str(tmp_path / "profile"), "--strict-exit"])
    capsys.readouterr()

    assert exit_code == 20
