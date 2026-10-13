"""V26 governed local sensory acquisition: image, WAV, code, transcript, telemetry.

All inputs must be operator-supplied; there is NO live capture, ASR, OCR,
object recognition, code execution, device polling, or raw-data persistence.
"""
from __future__ import annotations

import ast
import hashlib
import math
import struct
import wave
from pathlib import Path

from hex_cortex.memory.cortex_sensor_providers import get_cortex_sensor_provider

_MAX_FILE_BYTES = 8 * 1024 * 1024
_MAX_TEXT = 4000
_FIELDS = ("x", "y", "vx", "vy")
_ALLOWED_EXTENSIONS = {"image": {".png"}, "audio": {".wav"}, "code": {".py"}}


def _safe_file(path: Path, root: Path, *, modality: str) -> bytes:
    root = Path(root).resolve(strict=True)
    raw_path = Path(path)
    if raw_path.is_symlink() or not root.is_dir():
        raise ValueError("unsafe_sensor_root_or_symlink")
    resolved = raw_path.resolve(strict=True)
    if not resolved.is_relative_to(root) or resolved.suffix.lower() not in _ALLOWED_EXTENSIONS[modality]:
        raise ValueError("sensor_path_outside_root_or_type_denied")
    if not resolved.is_file() or not 0 < resolved.stat().st_size <= _MAX_FILE_BYTES:
        raise ValueError("sensor_file_size_denied")
    # No entire image is retained after the function returns; no disk write.
    return resolved.read_bytes()


def observe_local_file(
    *, path: Path, root: Path, modality: str, approved: bool = False,
) -> dict[str, object]:
    if not approved:
        raise PermissionError("sensory_file_read_requires_operator_approval")
    if modality not in _ALLOWED_EXTENSIONS:
        raise ValueError("unsupported_sensory_file_modality")
    payload = _safe_file(path, root, modality=modality)
    digest = hashlib.sha256(payload).hexdigest()
    info: dict[str, object]
    if modality == "image":
        # Actual PNG header inspection; no invented object/scene captions.
        if (
            len(payload) < 33 or payload[:8] != b"\x89PNG\r\n\x1a\n"
            or payload[12:16] != b"IHDR"
        ):
            raise ValueError("sensor_invalid_png")
        width, height = struct.unpack(">II", payload[16:24])
        if not (1 <= width <= 8192 and 1 <= height <= 8192):
            raise ValueError("sensor_image_dimensions_out_of_range")
        info = {
            "width_px": width, "height_px": height,
            "recognition_performed": False,
            "visual_semantics_known": False,
            "encoder_used": False,
        }
    elif modality == "audio":
        import io

        try:
            with wave.open(io.BytesIO(payload), "rb") as wav:
                channels = wav.getnchannels()
                frequency = wav.getframerate()
                frames = wav.getnframes()
                seconds = frames / frequency if frequency else 0.0
        except (wave.Error, EOFError, ValueError, ZeroDivisionError) as exc:
            raise ValueError("sensor_invalid_wav") from exc
        if not (1 <= channels <= 2 and 8000 <= frequency <= 192000 and
                0 < seconds <= 600):
            raise ValueError("sensor_audio_constraints_denied")
        info = {
            "channels": channels, "sample_rate_hz": frequency,
            "duration_ms": round(seconds * 1000),
            "transcription_performed": False,
            "speaker_identification_performed": False,
        }
    else:
        try:
            text = payload.decode("utf-8")
            tree = ast.parse(text, filename="<operator_selected_code>")
        except (UnicodeError, SyntaxError, ValueError) as exc:
            raise ValueError("sensor_unparseable_code") from exc
        imports = sorted({
            alias.name.split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            node.module.split(".")[0]
            for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            and node.module is not None
        })
        info = {
            "functions": sum(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                             for n in ast.walk(tree)),
            "classes": sum(isinstance(n, ast.ClassDef) for n in ast.walk(tree)),
            "imports": imports[:64],
            "static_ast_only": True, "code_executed": False,
            "code_safe_to_execute_certified": False,
        }
    return {
        "status": "observed", "modality": modality,
        "origin": "operator_selected_local_file",
        "source_sha256": digest, "byte_count": len(payload),
        "features": info, "raw_input_saved": False,
        "files_written": False, "external_provider_called": False,
        "device_actuation_performed": False,
    }


def observe_transcript(*, text: str, approved: bool = False) -> dict[str, object]:
    if not approved:
        raise PermissionError("transcript_requires_operator_approval")
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= _MAX_TEXT:
        raise ValueError("transcript_invalid")
    provider = get_cortex_sensor_provider("local_transcript")
    if provider["capability_id"] != "voice_input":
        raise ValueError("transcript_provider_not_registered")
    return {
        "status": "observed", "modality": "transcript",
        "origin": "operator_supplied_text",
        "source_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "features": {
            "text_chars": len(text),
            "speech_recognition_performed": False,
            "intent_inferred": False,
        },
        "raw_input_saved": False, "files_written": False,
        "microphone_accessed": False,
    }


def observe_telemetry(
    *, state: dict[str, float], approved: bool = False,
) -> dict[str, object]:
    if not approved:
        raise PermissionError("telemetry_requires_operator_approval")
    if not isinstance(state, dict) or set(state) != set(_FIELDS):
        raise ValueError("telemetry_fields_invalid")
    for field in _FIELDS:
        value = state[field]
        if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
            raise ValueError("telemetry_value_nonfinite")
        if abs(value) > 1_000_000:
            raise ValueError("telemetry_value_out_of_bounds")
    canonical = {k: float(state[k]) for k in _FIELDS}
    return {
        "status": "observed", "modality": "telemetry",
        "origin": "operator_supplied_simulation_state",
        "source_sha256": hashlib.sha256(repr(tuple(sorted(canonical.items()))).encode()).hexdigest(),
        "features": {
            "state": canonical, "position_unit": "m",
            "velocity_unit": "m/s", "measurement_calibrated": False,
        },
        "raw_input_saved": False, "files_written": False,
        "hardware_polled": False,
    }
