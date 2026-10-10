"""Operator PhysicsCell CLI exact SI calculations and consent gate."""
from __future__ import annotations

import json

from hex_cortex.core.cortex_physics_cli_v14 import main


def test_force_cli_exact_and_units(capsys):
    code = main(["--law", "force", "--mass", "3",
                 "--acceleration", "2/3", "--approve-calculate", "--pretty"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert report["numerator"] == 2
    assert report["denominator"] == 1
    assert report["unit"] == "N"
    assert report["model_used"] is False
    assert report["hardware_actuation_allowed"] is False


def test_cli_no_approval_blocks_even_valid_request(capsys):
    assert main(["--law", "speed", "--distance", "100",
                 "--duration", "10"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "physics_operator_approval_required"


def test_cli_refuses_extra_parameter(capsys):
    assert main(["--law", "force", "--mass", "2", "--acceleration", "3",
                 "--distance", "10", "--approve-calculate"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "physics_operand_names_mismatch"


def test_cli_refuses_invalid_expression(capsys):
    assert main(["--law", "force", "--mass", "__import__('os')",
                 "--acceleration", "2", "--approve-calculate"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "physics_numeric_expression_rejected"
