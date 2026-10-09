"""Opt-in local MCP Skills catalog backed by approved portable SKILL.md files.

Only the explicitly configured local directory is published. No scripts are
executed, no symlinks are followed, no trust/approval is inferred from a digest.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_ALLOWED_SUFFIXES = {".md", ".txt", ".json"}
_MAX_BYTES = 16_777_216
_MAX_FILES = 512


def _parse_frontmatter(content: str) -> dict[str, object]:
    lines = content.splitlines()
    if not lines or lines[0] != "---":
        raise ValueError("skill requires YAML frontmatter")
    try:
        stop = lines.index("---", 1)
    except ValueError as exc:
        raise ValueError("unterminated skill frontmatter") from exc
    metadata: dict[str, object] = {}
    for line in lines[1:stop]:
        key, separator, raw = line.partition(":")
        if not separator or not key or key in metadata:
            raise ValueError("invalid skill frontmatter")
        raw = raw.strip()
        if raw.startswith('"'):
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError("invalid quoted frontmatter") from exc
        else:
            if not raw or raw.startswith(("[", "{", "|", ">")):
                raise ValueError("unsupported complex frontmatter")
            value = raw
        if not isinstance(value, str):
            raise ValueError("frontmatter scalars must be strings")
        metadata[key] = value
    if not _NAME.fullmatch(str(metadata.get("name", ""))):
        raise ValueError("invalid skill name")
    if not str(metadata.get("description", "")).strip():
        raise ValueError("skill description required")
    return metadata


class LocalSkillCatalog:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        if not root.is_dir() or root.is_symlink():
            raise ValueError("skill directory is missing or linked")

    def _skill(self, directory: Path) -> dict[str, object]:
        if directory.is_symlink() or not directory.is_dir() or not _NAME.fullmatch(directory.name):
            raise ValueError("unsafe skill directory")
        if not directory.resolve().is_relative_to(self.root):
            raise ValueError("skill escapes catalog")
        entry_path = directory / "SKILL.md"
        if entry_path.is_symlink() or not entry_path.is_file():
            raise ValueError("no safe SKILL.md")
        entry_bytes = entry_path.read_bytes()
        if len(entry_bytes) > _MAX_BYTES:
            raise ValueError("skill exceeds total size limit")
        frontmatter = _parse_frontmatter(entry_bytes.decode("utf-8"))
        if frontmatter["name"] != directory.name:
            raise ValueError("frontmatter name differs from directory")
        resources: list[dict[str, object]] = []
        total_bytes = 0
        files = sorted(path for path in directory.rglob("*") if path.is_file() or path.is_symlink())
        if len(files) > _MAX_FILES:
            raise ValueError("skill contains too many resources")
        for path in files:
            if path.is_symlink() or not path.resolve().is_relative_to(directory.resolve()):
                raise ValueError("skill resource symlink or escape")
            if path.suffix not in _ALLOWED_SUFFIXES:
                raise ValueError("non-document skill resource blocked")
            payload = path.read_bytes()
            total_bytes += len(payload)
            if total_bytes > _MAX_BYTES:
                raise ValueError("skill resources exceed limit")
            relative = path.relative_to(self.root).as_posix()
            resources.append({
                "uri": "skill://" + relative,
                "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
            })
        uri = f"skill://{directory.name}/SKILL.md"
        return {"uri": uri, "frontmatter": frontmatter, "resources": resources}

    def all(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for directory in sorted(self.root.iterdir()):
            if directory.is_symlink():
                raise ValueError("linked skill directories are blocked")
            if directory.is_dir():
                result.append(self._skill(directory))
        return result

    def get(self, uri: str) -> dict[str, object]:
        for entry in self.all():
            if entry["uri"] == uri:
                return entry
        raise ValueError("skill not served")

    def read(self, uri: str) -> dict[str, object]:
        if not uri.startswith("skill://"):
            raise ValueError("not a skill resource")
        path_part = uri[len("skill://"):]
        if not path_part or ".." in Path(path_part).parts:
            raise ValueError("unsafe resource path")
        entry_uri = "skill://" + path_part.split("/", 1)[0] + "/SKILL.md"
        entry = self.get(entry_uri)
        assert isinstance(entry["resources"], list)
        if not any(item["uri"] == uri for item in entry["resources"]):
            raise ValueError("resource not in published manifest")
        path = (self.root / path_part).resolve()
        if not path.is_relative_to(self.root) or not path.is_file():
            raise ValueError("invalid skill path")
        text = path.read_text(encoding="utf-8")
        payload = text.encode("utf-8")
        expected = next(item for item in entry["resources"] if item["uri"] == uri)
        if (
            "sha256:" + hashlib.sha256(payload).hexdigest() != expected["digest"]
            or len(payload) != expected["size"]
        ):
            raise ValueError("skill integrity changed")
        return {
            "contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}],
            "ttlMs": 300000,
            "cacheScope": "public",
        }
