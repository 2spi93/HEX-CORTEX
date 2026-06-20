from __future__ import annotations

import hashlib
import json
from pathlib import Path

_DEFAULT_MAX_FILES = 4096
_DEFAULT_MAX_BYTES = 2 * 1024 * 1024
_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "headers",
    "raw_prompt",
    "raw_response",
    "secret_value",
    "volatile_result_text",
}


def reconcile_evidence_receipts(
    *,
    state_root: Path,
    output_path: Path | None = None,
    max_files: int = _DEFAULT_MAX_FILES,
    max_bytes: int = _DEFAULT_MAX_BYTES,
) -> dict[str, object]:
    root = state_root.resolve()
    receipts_root = root / "receipts"
    target = (
        output_path.resolve()
        if output_path is not None
        else (receipts_root / "00-canonical-evidence.jsonl").resolve()
    )
    if max_files < 1 or max_files > 100_000:
        return _blocked("max_files_out_of_range")
    if max_bytes < 1024 or max_bytes > 64 * 1024 * 1024:
        return _blocked("max_bytes_out_of_range")
    if not receipts_root.is_dir():
        return _blocked("receipts_root_missing")
    if not target.is_relative_to(root):
        return _blocked("output_path_outside_state_root")

    records: list[dict[str, object]] = []
    source_files = 0
    skipped_files = 0
    for path in sorted(receipts_root.rglob("*")):
        if source_files >= max_files:
            break
        if path.resolve() == target:
            continue
        if not path.is_file() or path.suffix.lower() not in {".json", ".jsonl"}:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            skipped_files += 1
            continue
        if size > max_bytes:
            skipped_files += 1
            continue
        source_files += 1
        records.extend(_read_records(path))

    unique: dict[str, dict[str, object]] = {}
    for record in records:
        sanitized = sanitize_evidence_record(record)
        encoded = _canonical_json(sanitized)
        unique[hashlib.sha256(encoded.encode("utf-8")).hexdigest()] = sanitized

    target.parent.mkdir(parents=True, exist_ok=True)
    lines = [_canonical_json(unique[key]) for key in sorted(unique)]
    target.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    payload = {
        "receipt_type": "canonical_evidence_reconciliation_v1",
        "status": "reconciled",
        "state_root": str(root),
        "receipts_root": str(receipts_root),
        "output_path": str(target),
        "source_file_count": source_files,
        "skipped_file_count": skipped_files,
        "record_count": len(lines),
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "blockers": [],
        "next_action": "rerun_operational_audit",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def append_canonical_evidence(
    *,
    output_path: Path,
    record: dict[str, object],
) -> dict[str, object]:
    target = output_path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    sanitized = sanitize_evidence_record(record)
    line = _canonical_json(sanitized)
    line_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()

    existing_hashes: set[str] = set()
    if target.is_file():
        try:
            for raw in target.read_text(encoding="utf-8").splitlines():
                if raw.strip():
                    existing_hashes.add(hashlib.sha256(raw.encode("utf-8")).hexdigest())
        except (OSError, UnicodeError):
            return _blocked("canonical_evidence_read_failed")
    appended = line_hash not in existing_hashes
    if appended:
        with target.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(line + "\n")
    payload = {
        "receipt_type": "canonical_evidence_append_v1",
        "status": "appended" if appended else "already_present",
        "output_path": str(target),
        "record_hash": line_hash,
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "blockers": [],
        "next_action": "rerun_operational_audit",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def sanitize_evidence_record(record: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    removed: list[str] = []
    for key, value in record.items():
        normalized = key.lower()
        if normalized in _SENSITIVE_KEYS:
            removed.append(key)
            continue
        sanitized[key] = _sanitize_value(value)
    if removed:
        sanitized["reconciled_sensitive_fields_removed"] = sorted(removed)
    return sanitized


def _sanitize_value(value: object) -> object:
    if isinstance(value, dict):
        return sanitize_evidence_record({str(key): item for key, item in value.items()})
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def _read_records(path: Path) -> list[dict[str, object]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return []
    if path.suffix.lower() == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return []
        if isinstance(payload, dict):
            return [payload]
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        return []

    records: list[dict[str, object]] = []
    for raw in text.splitlines():
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            records.append(payload)
    return records


def _canonical_json(payload: dict[str, object]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _blocked(blocker: str) -> dict[str, object]:
    payload = {
        "receipt_type": "canonical_evidence_reconciliation_v1",
        "status": "blocked",
        "raw_prompt_persisted": False,
        "raw_response_persisted": False,
        "raw_secret_persisted": False,
        "blockers": [blocker],
        "next_action": "repair_evidence_reconciliation",
    }
    payload["receipt_hash"] = _stable_hash(payload)
    return payload


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
