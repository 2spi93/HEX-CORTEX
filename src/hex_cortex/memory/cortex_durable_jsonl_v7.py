"""Crash-resistant local JSONL snapshot writes for HEX-CORTEX.

A writer must acquire the exclusive sibling lock directory for its entire
read/modify/write operation. Temp files are fsync'ed and atomically replaced
inside the same filesystem. A crash may leave a lock; it is NEVER silently
stolen (operator must establish no writer is running before removing it).

This prevents *cooperating* writers from losing updates and prevents partial
replacement of an existing snapshot. It is not a database transaction, a
backup, or protection against rogue processes ignoring the lock.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from pathlib import Path


def _validated_target(path: Path) -> Path:
    if path.is_symlink():
        raise ValueError("jsonl_symlink_target_denied")
    if not path.name or path.name in {".", ".."}:
        raise ValueError("jsonl_path_invalid")
    if path.exists() and not path.is_file():
        raise ValueError("jsonl_target_not_file")
    if path.parent.is_symlink():
        raise ValueError("jsonl_symlink_parent_denied")
    return path


@contextmanager
def exclusive_jsonl_writer(path: Path) -> Iterator[None]:
    """Fail closed if a concurrent writer or orphaned crash lock exists."""
    target = _validated_target(Path(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    lock = target.with_name(target.name + ".write-lock")
    if lock.is_symlink():
        raise ValueError("jsonl_lock_symlink_denied")
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError as exc:
        raise ValueError("jsonl_writer_already_active_or_crash_lock") from exc
    try:
        _validated_target(target)
        yield
    finally:
        lock.rmdir()


def atomic_jsonl_snapshot(path: Path, lines: Iterable[str]) -> None:
    """Write a complete validated snapshot while caller holds writer lock."""
    target = _validated_target(Path(path))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n",
            prefix="." + target.name + ".", suffix=".tmp",
            dir=target.parent, delete=False,
        ) as handle:
            temporary = Path(handle.name)
            for line in lines:
                if not isinstance(line, str) or "\n" in line or "\r" in line:
                    raise ValueError("jsonl_line_malformed")
                handle.write(line + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _validated_target(target)
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
