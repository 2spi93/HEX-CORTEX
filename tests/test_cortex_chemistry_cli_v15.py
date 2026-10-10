"""Chemistry CLI supports exact simulations without remote models."""
from __future__ import annotations

import json

import pytest

from hex_cortex.core.cortex_chemistry_cli_v15 import main


def test_chemistry_cli_balances_water_without_model(capsys):
    rc = main([
        "--reactant", "H2", "--reactant", "O2",
        "--product", "H2O", "--approve-simulate", "--pretty",
    ])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert [row["coefficient"] for row in report["balance"]["reactants"]] == [2, 1]
    assert report["simulation_executed"] is False
    assert report["model_called"] is False


def test_chemistry_cli_simulates_limiting_reactant(capsys):
    rc = main([
        "--reactant", "H2", "--reactant", "O2",
        "--product", "H2O", "--amount", "H2=3",
        "--amount", "O2=1", "--approve-simulate", "--pretty",
    ])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["simulation"]["limiting_reactants"] == ["O2"]
    assert report["simulation"]["products_mol"] == {"H2O": "2"}
    assert report["simulation"]["mass_conserved_under_fixed_rounded_weights"] is True
    assert report["laboratory_action_performed"] is False


def test_chemistry_cli_denies_without_approval(capsys):
    rc = main(["--reactant", "H2", "--reactant", "O2", "--product", "H2O"])
    assert rc == 2
    report = json.loads(capsys.readouterr().out)
    assert report["reason"] == "chemistry_operator_approval_required"
    assert report["calculation_performed"] is False


def test_chemistry_cli_rejects_python_injection_without_execution(capsys):
    rc = main([
        "--reactant", "__import__(os)", "--product", "H2O",
        "--approve-simulate",
    ])
    assert rc == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert "__import__" not in json.dumps(report)


def test_chemistry_cli_duplicate_amount_fails_fast():
    with pytest.raises(SystemExit):
        main(["--reactant", "H2", "--product", "O2",
              "--amount", "H2=1", "--amount", "H2=2", "--approve-simulate"])
