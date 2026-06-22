"""Bounded repository context built from the static AST graph.

The context pack exposes real repository paths and public symbol metadata without
pasting source bodies. It is deterministic, read-only, bounded by both module
count and character budget, and suitable for small local models.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from hex_cortex.memory.cortex_repo_graph import build_repo_graph

_CONTEXT_TYPE = "cortex_bounded_repo_context_v1"
_STOPWORDS = {
    "about",
    "after",
    "again",
    "avec",
    "avant",
    "code",
    "dans",
    "depuis",
    "des",
    "faire",
    "from",
    "pour",
    "that",
    "the",
    "this",
    "une",
    "with",
}


def build_bounded_repo_context(
    root: Path,
    task_text: str,
    *,
    max_modules: int = 10,
    max_chars: int = 12_000,
) -> dict[str, object]:
    """Return a compact, source-grounded context pack for one task."""
    if not task_text.strip():
        raise ValueError("task_text must not be empty")
    if not 1 <= max_modules <= 50:
        raise ValueError("max_modules out of range")
    if not 1_000 <= max_chars <= 100_000:
        raise ValueError("max_chars out of range")

    graph = build_repo_graph(root)
    modules_value = graph.get("modules")
    modules = modules_value if isinstance(modules_value, dict) else {}
    task_tokens = _tokens(task_text)
    ranked: list[tuple[float, str, dict[str, object]]] = []
    for rel, value in modules.items():
        if not isinstance(rel, str) or not isinstance(value, dict):
            continue
        score = _module_score(rel, value, task_tokens)
        if score > 0:
            ranked.append((score, rel, value))

    if not ranked:
        for rel, value in modules.items():
            if not isinstance(rel, str) or not isinstance(value, dict):
                continue
            if any(
                marker in rel
                for marker in (
                    "cortex_cognitive_loop",
                    "cortex_verified_execution",
                    "cortex_self_consistency",
                    "cortex_repo_graph",
                    "cortex_patch_tournament",
                )
            ):
                ranked.append((1.0, rel, value))

    ranked.sort(key=lambda item: (-item[0], item[1]))
    selected: list[dict[str, object]] = []
    selected_paths: list[str] = []
    selected_symbols: set[str] = set()
    for score, rel, info in ranked:
        if len(selected) >= max_modules:
            break
        definitions = [
            {
                "name": str(item.get("name", "")),
                "qualname": str(item.get("qualname", "")),
                "kind": str(item.get("kind", "")),
                "lineno": int(item.get("lineno", 0)),
            }
            for item in info.get("defines", [])
            if isinstance(item, dict) and item.get("name")
        ][:16]
        candidate = {
            "module": rel,
            "score": round(score, 3),
            "is_test": bool(info.get("is_test")),
            "imports": [str(item) for item in info.get("imports", [])][:12],
            "public_definitions": definitions,
        }
        tentative = selected + [candidate]
        preview = _context_text(tentative, [])
        if len(preview) > max_chars and selected:
            break
        selected = tentative
        selected_paths.append(rel)
        selected_symbols.update(item["name"] for item in definitions)

    related_tests: list[str] = []
    for rel, value in sorted(modules.items()):
        if not isinstance(rel, str) or not isinstance(value, dict) or not value.get("is_test"):
            continue
        references = {str(item) for item in value.get("references", [])}
        if selected_symbols.intersection(references):
            related_tests.append(rel)
        if len(related_tests) >= 12:
            break

    text = _context_text(selected, related_tests)
    if len(text) > max_chars:
        text = text[:max_chars]
    allowed_paths = sorted(set(selected_paths + related_tests))
    payload = {
        "context_type": _CONTEXT_TYPE,
        "graph_type": graph.get("graph_type"),
        "module_count": len(selected),
        "related_test_count": len(related_tests),
        "allowed_paths": allowed_paths,
        "selected_modules": selected,
        "related_tests": related_tests,
        "context_text": text,
        "context_chars": len(text),
        "raw_source_persisted": False,
    }
    payload["context_hash"] = _stable_hash(
        {key: value for key, value in payload.items() if key != "context_text"}
    )
    return payload


def _module_score(rel: str, info: dict[str, object], task_tokens: set[str]) -> float:
    path_tokens = _tokens(rel.replace("/", " "))
    definitions = {
        token
        for item in info.get("defines", [])
        if isinstance(item, dict)
        for token in _tokens(str(item.get("name", "")))
    }
    references = {
        token for item in info.get("references", []) for token in _tokens(str(item))
    }
    imports = {
        token for item in info.get("imports", []) for token in _tokens(str(item))
    }
    score = 3.0 * len(task_tokens.intersection(path_tokens))
    score += 5.0 * len(task_tokens.intersection(definitions))
    score += 2.0 * len(task_tokens.intersection(references))
    score += 1.0 * len(task_tokens.intersection(imports))
    if info.get("is_test"):
        score *= 0.75
    return score


def _tokens(text: str) -> set[str]:
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text).replace("_", " ")
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z][A-Za-z0-9]{2,}", expanded)
        if token.lower() not in _STOPWORDS
    }


def _context_text(modules: list[dict[str, object]], related_tests: list[str]) -> str:
    return json.dumps(
        {
            "instruction": (
                "Use only these real repository paths and public symbols. "
                "Do not invent files. State unknown when evidence is insufficient."
            ),
            "modules": modules,
            "related_tests": related_tests,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def _stable_hash(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


__all__ = ["build_bounded_repo_context"]
