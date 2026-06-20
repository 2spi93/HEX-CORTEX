from __future__ import annotations

import json
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_brain_registration_config import build_registration_template
from hex_cortex.memory.cortex_brain_registration_config import load_registration_config
from hex_cortex.memory.cortex_brain_registration_config import write_registration_template


def test_windows_template_avoids_shell_placeholders() -> None:
    payload = build_registration_template("windows")

    assert payload["brain_id"] == "windows-coding-primary"
    assert payload["runtime_id"] == "windows.ollama"
    assert payload["provider_scope"] == "local"
    assert payload["reliability_score"] is None
    assert payload["model_id"] == "REPLACE_WITH_ME"


def test_kali_template_uses_private_remote_scope() -> None:
    payload = build_registration_template("kali")

    assert payload["brain_id"] == "kali-research-primary"
    assert payload["runtime_id"] == "kali.ollama"
    assert payload["provider_scope"] == "private_remote"


def test_template_writer_refuses_accidental_overwrite(tmp_path: Path) -> None:
    target = tmp_path / "brain.json"
    first = write_registration_template(target, platform_name="windows")

    assert first["status"] == "written"
    with pytest.raises(ValueError, match="already exists"):
        write_registration_template(target, platform_name="windows")


def test_loader_rejects_unreplaced_values(tmp_path: Path) -> None:
    target = tmp_path / "brain.json"
    write_registration_template(target, platform_name="windows")

    with pytest.raises(ValueError, match="placeholder not replaced"):
        load_registration_config(target)


def test_loader_accepts_measured_approved_config(tmp_path: Path) -> None:
    target = tmp_path / "brain.json"
    payload = build_registration_template("windows")
    payload.update(
        {
            "model_id": "qwen2.5-coder:7b",
            "model_family": "qwen2.5-coder",
            "domain_scores": {"coding": 0.82, "research": 0.61, "general": 0.71},
            "reliability_score": 0.91,
            "latency_ms": 845.0,
            "baseline_hash": "a" * 64,
            "parameter_class": "7b",
            "quantization": "q4_k_m",
            "operator_approved": True,
        }
    )
    target.write_text(json.dumps(payload), encoding="utf-8")

    loaded = load_registration_config(target)

    assert loaded["model_id"] == "qwen2.5-coder:7b"
    assert loaded["operator_approved"] is True
    assert loaded["domain_scores"]["coding"] == 0.82
