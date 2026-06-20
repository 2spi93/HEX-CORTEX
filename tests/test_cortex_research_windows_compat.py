from pathlib import Path

from hex_cortex.memory.cortex_research_runtime_cli import build_parser


def test_research_audit_has_safe_default_query() -> None:
    args = build_parser().parse_args(["audit"])

    assert args.command == "audit"
    assert args.query == "official Python documentation"
    assert args.network is False


def test_research_start_script_supports_windows_powershell_51() -> None:
    script = Path("scripts/start_research_stack.ps1").read_text(encoding="utf-8")

    assert "RandomNumberGenerator]::Fill" not in script
    assert "Convert]::ToHexString" not in script
    assert "RandomNumberGenerator]::Create()" in script
    assert "$Random.GetBytes($Bytes)" in script
    assert "BitConverter]::ToString($Bytes)" in script
    assert "Invoke-RestMethod" in script
    assert "SearXNG JSON API is ready" in script
