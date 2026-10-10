"""Read-only, locally grounded provenance for the V16 science knowledge router.

A source manifest and source bytes are both OPERATOR-PROVIDED. Rechecking
bytes and structured claims prevents accidental corruption/substitution but
DOES NOT authenticate a real-world publisher or prove scientific truth.
No network, import of downloaded code, filesystem mutation or device access.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from pathlib import Path

from pydantic import ValidationError

from hex_cortex.core.cortex_scientific_knowledge_v16 import EvidenceRecord

_MAX_SOURCE_BYTES = 16_384
_MAX_MANIFEST_BYTES = 65_536
_MAX_RECORDS = 32


class LocalEvidenceRefusal(ValueError):
    """Non-sensitive, stable reason code for failed scientific evidence reads."""


def expected_scientific_source_bytes(record: EvidenceRecord) -> bytes:
    """Canonical local source witness, omitting only its own SHA-256 to avoid a cycle."""
    payload = {
        "source_document_type": "hex_cortex_scientific_source_v17",
        "record": record.model_dump(mode="json", exclude={"source_digest_sha256"}),
    }
    return (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _read_regular_file(path: Path, *, max_bytes: int) -> bytes:
    """Reject symlinks and nonregular sources and read a strict bounded buffer."""
    if path.is_symlink():
        raise LocalEvidenceRefusal("local_evidence_symlink_denied")
    if not path.is_file():
        raise LocalEvidenceRefusal("local_evidence_regular_file_required")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        fd = os.open(path, flags)
        try:
            if not stat.S_ISREG(os.fstat(fd).st_mode):
                raise LocalEvidenceRefusal("local_evidence_regular_file_required")
            data = os.read(fd, max_bytes + 1)
        finally:
            os.close(fd)
    except OSError as exc:
        raise LocalEvidenceRefusal("local_evidence_read_failed") from exc
    if len(data) > max_bytes:
        raise LocalEvidenceRefusal("local_evidence_bytes_budget_exceeded")
    return data


def load_local_scientific_manifest(path: Path, *, approved: bool = False) -> list[EvidenceRecord]:
    """Read a bounded JSON array only after explicit operator permission."""
    if not approved:
        raise LocalEvidenceRefusal("local_evidence_read_approval_required")
    blob = _read_regular_file(Path(path), max_bytes=_MAX_MANIFEST_BYTES)
    try:
        items = json.loads(blob)
    except (UnicodeDecodeError, ValueError) as exc:
        raise LocalEvidenceRefusal("local_evidence_manifest_invalid") from exc
    if not isinstance(items, list) or len(items) > _MAX_RECORDS:
        raise LocalEvidenceRefusal("local_evidence_manifest_size_invalid")
    try:
        return [EvidenceRecord.model_validate(item) for item in items]
    except (ValidationError, ValueError, TypeError) as exc:
        raise LocalEvidenceRefusal("local_evidence_manifest_records_invalid") from exc


class LocalScientificEvidenceVerifier:
    """Local byte/claim verifier; trusted host selects the allowed directory.

    This does not establish source independence or authenticate publisher
    identity. A malicious user can create two mutually consistent forged
    files. Treat as *reproducible data lineage*, NOT validated science.
    """

    def __init__(self, source_directory: Path, *, operator_approved: bool = False) -> None:
        self.source_directory = Path(source_directory)
        self.operator_approved = operator_approved

    def verify_source(self, record: EvidenceRecord) -> bool:
        if not self.operator_approved:
            return False
        root = self.source_directory
        if root.is_symlink() or not root.is_dir():
            return False
        # The EvidenceRecord source_id grammar excludes / and backslashes.
        # The source file is the sole read target; no URL is opened.
        if not isinstance(record, EvidenceRecord):
            return False
        # A BaseModel.model_copy(update=...) bypasses Pydantic validation.
        # Recheck at the filesystem trust boundary, including Windows ADS.
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,95}", record.source_id):
            return False
        target = root / (record.source_id + ".json")
        try:
            raw = _read_regular_file(target, max_bytes=_MAX_SOURCE_BYTES)
            if hashlib.sha256(raw).hexdigest() != record.source_digest_sha256:
                return False
            if raw != expected_scientific_source_bytes(record):
                return False
        except (OSError, ValueError, TypeError):
            return False
        return True
