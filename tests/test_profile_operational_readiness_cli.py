import json

from hex_cortex.memory.profile_operational_readiness_cli import main
from tests.test_profile_operational_readiness import populate_profile


def test_profile_operational_readiness_cli_outputs_json(tmp_path, capsys) -> None:
    profile = tmp_path / "profile"
    populate_profile(profile)

    exit_code = main([str(profile), "--pretty"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["readiness_type"] == "profile_operational_readiness"
    assert payload["verdict"] == "profile_watch"
