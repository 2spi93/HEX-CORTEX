"""PowerShell-compatible exact mathematics command without cloud inference."""
from __future__ import annotations

import json

from hex_cortex.core.cortex_exact_math_cli_v13 import main


def test_cli_denies_without_explicit_authorization(capsys):
    assert main(["--expression", "1 / 3 + 1 / 6"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["calculation_performed"] is False


def test_cli_exact_arithmetic_with_approval(capsys):
    assert main(["--expression", "1 / 3 + 1 / 6", "--approve-calculate", "--pretty"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["numerator"] == 1
    assert report["denominator"] == 2
    assert report["independent_traversal_agrees"] is True
    assert report["model_used"] is False


def test_cli_rejects_python_injection(capsys):
    assert main(["--expression", '__import__("os")',
                 "--approve-calculate"]) == 2
    report = json.loads(capsys.readouterr().out)
    assert report["status"] == "blocked"
    assert report["calculation_performed"] is False
