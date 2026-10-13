"""Real header/AST/WAV parsing, opt-in paths, no raw-media persistence."""
from __future__ import annotations

import struct
import wave
from pathlib import Path

import pytest

from hex_cortex.memory.cortex_universal_sensing_v26 import (
    observe_local_file, observe_telemetry, observe_transcript,
)


def test_operator_selected_png_reads_actual_dimensions(tmp_path: Path) -> None:
    path = tmp_path / "image.png"
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR"
        + struct.pack(">II", 32, 24) + b"\x08\x02\x00\x00\x00"
        + b"\x00\x00\x00\x00"
    )
    observation = observe_local_file(
        path=path, root=tmp_path, modality="image", approved=True
    )
    assert observation["features"]["width_px"] == 32
    assert observation["features"]["height_px"] == 24
    assert observation["features"]["recognition_performed"] is False
    assert observation["raw_input_saved"] is False
    assert observation["source_sha256"]


def test_code_analysis_is_ast_only_and_no_import_execution(tmp_path: Path) -> None:
    file = tmp_path / "program.py"
    file.write_text("import os\nclass A:\n    pass\ndef task():\n    return 3\n", encoding="utf-8")
    found = observe_local_file(
        path=file, root=tmp_path, modality="code", approved=True
    )
    assert found["features"]["classes"] == 1
    assert found["features"]["functions"] == 1
    assert found["features"]["imports"] == ["os"]
    assert found["features"]["code_executed"] is False
    assert found["features"]["code_safe_to_execute_certified"] is False


def test_wav_header_reports_duration_without_transcription(tmp_path: Path) -> None:
    path = tmp_path / "voice.wav"
    with wave.open(str(path), "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        file.writeframes(b"\x00\x00" * 1600)
    found = observe_local_file(
        path=path, root=tmp_path, modality="audio", approved=True
    )
    assert found["features"]["duration_ms"] == 100
    assert found["features"]["transcription_performed"] is False
    assert found["files_written"] is False


def test_transcript_and_telemetry_require_operator_approval() -> None:
    with pytest.raises(PermissionError):
        observe_transcript(text="hello")
    with pytest.raises(PermissionError):
        observe_telemetry(state={"x": 0, "y": 0, "vx": 1, "vy": 1})
    t = observe_transcript(text="simulate object motion", approved=True)
    s = observe_telemetry(
        state={"x": 1, "y": 2, "vx": 3, "vy": 4}, approved=True
    )
    assert t["features"]["speech_recognition_performed"] is False
    assert s["features"]["measurement_calibrated"] is False
    assert t["source_sha256"] and s["source_sha256"]


def test_file_read_refused_without_approval_or_outside_root(tmp_path: Path) -> None:
    path = tmp_path / "script.py"
    path.write_text("print(1)", encoding="utf-8")
    with pytest.raises(PermissionError):
        observe_local_file(
            path=path, root=tmp_path, modality="code",
        )
    other = tmp_path / "inside"
    other.mkdir()
    with pytest.raises(ValueError, match="sensor_path_outside_root_or_type_denied"):
        observe_local_file(path=path, root=other, modality="code", approved=True)


@pytest.mark.parametrize("state", [
    {"x": 0, "y": 0, "vx": float("nan"), "vy": 0},
    {"x": 0, "y": 0, "vx": True, "vy": 0},
    {"x": 0, "y": 0, "vx": 0},
])
def test_bad_telemetry_refused(state: dict[str, float]) -> None:
    with pytest.raises(ValueError):
        observe_telemetry(state=state, approved=True)
