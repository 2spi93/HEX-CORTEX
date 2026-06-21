import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_gpu_probe import build_snapshot_from_sources
from hex_cortex.memory.cortex_gpu_probe_cli import main


def _ps(*sizes_mb: float) -> dict[str, object]:
    return {"models": [{"name": f"m{i}", "size_vram": int(s * 1024 * 1024)} for i, s in enumerate(sizes_mb)]}


def test_idle_snapshot() -> None:
    snap = build_snapshot_from_sources(_ps(), dedicated_usage_mb=470.0)
    assert snap["vram_total_mb"] == 12288.0
    assert snap["vram_used_mb"] == 470.0
    assert snap["loaded_model_count"] == 0
    assert snap["big_model_loaded"] is False


def test_small_model_resident() -> None:
    snap = build_snapshot_from_sources(_ps(4500.0), dedicated_usage_mb=4800.0)
    assert snap["loaded_model_count"] == 1
    assert snap["big_model_loaded"] is False
    # Measured dedicated usage (4800) exceeds Ollama attribution (4500) -> use it.
    assert snap["vram_used_mb"] == 4800.0


def test_large_model_detected() -> None:
    snap = build_snapshot_from_sources(_ps(9500.0))
    assert snap["big_model_loaded"] is True
    # No measured counter -> fall back to Ollama attribution.
    assert round(snap["vram_used_mb"]) == 9500


def test_used_never_exceeds_total() -> None:
    snap = build_snapshot_from_sources(_ps(), dedicated_usage_mb=999999.0)
    assert snap["vram_used_mb"] == snap["vram_total_mb"]


def test_invalid_sources_rejected() -> None:
    with pytest.raises(ValueError):
        build_snapshot_from_sources([])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        build_snapshot_from_sources({"models": 5})
    with pytest.raises(ValueError):
        build_snapshot_from_sources(_ps(), vram_total_mb=0.0)


def test_cli_admits_small_on_idle(tmp_path: Path, capsys) -> None:
    ps = tmp_path / "ps.json"
    ps.write_text(json.dumps(_ps()), encoding="utf-8")
    code = main(["--ollama-ps", str(ps), "--dedicated-mb", "470", "--tier", "small"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["decision"]["action"] == "admit"


def test_cli_defers_and_flags_unload_when_vram_critical(tmp_path: Path, capsys) -> None:
    ps = tmp_path / "ps.json"
    ps.write_text(json.dumps(_ps()), encoding="utf-8")
    # 11500 / 12288 ~= 0.936 >= critical 0.92 -> defer + unload.
    code = main(["--ollama-ps", str(ps), "--dedicated-mb", "11500", "--tier", "large"])
    out = json.loads(capsys.readouterr().out)
    assert code == 4
    assert out["decision"]["action"] == "defer"
    assert out["decision"]["recommend_unload_idle"] is True


def test_cli_handles_bad_file(tmp_path: Path, capsys) -> None:
    bad = tmp_path / "bad.json"
    bad.write_text("[1,2,3]", encoding="utf-8")
    code = main(["--ollama-ps", str(bad)])
    out = json.loads(capsys.readouterr().out)
    assert code == 2
    assert out["status"] == "blocked"
